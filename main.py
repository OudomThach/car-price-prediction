# main.py — CLI entry point for the Khmer24 car price data collection pipeline & REST API
#
# Saves: Parquet (full data) + CSV samples (30 & 60 rows)
#
# Run Pipeline:  python main.py
# Run REST API:  python main.py --serve
# Run with env:  MAX_PAGES=5 python main.py

import argparse
import logging
import sys

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError for Khmer)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd

from car_price_prediction import pipeline
from car_price_prediction.config import LOG_DIR, LOG_FILE_PATH, MAX_PAGES, TARGET_CATEGORY, TARGET_PROVINCE

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  [%(levelname)-8s]  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_FILE_PATH, encoding="utf-8"),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Cambodia Car Price Prediction Pipeline & API")
    parser.add_argument("--serve", action="store_true", help="Start the FastAPI REST API server")
    parser.add_argument("--host", default="127.0.0.1", help="API host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="API port (default: 8000)")
    args = parser.parse_args()

    if args.serve:
        import uvicorn

        logger.info(
            f"Starting FastAPI server at http://{args.host}:{args.port} (Swagger docs: http://{args.host}:{args.port}/docs)"
        )
        uvicorn.run("car_price_prediction.api.app:app", host=args.host, port=args.port, reload=False)
        return

    logger.info("=" * 65)
    logger.info("Cambodia Car Price Prediction — Data Collection Pipeline")
    logger.info(f"  Category  : {TARGET_CATEGORY}")
    logger.info(f"  Province  : {TARGET_PROVINCE or 'ALL'}")
    logger.info(f"  Max pages : {MAX_PAGES}  ({MAX_PAGES * 30} listings max)")
    logger.info("=" * 65)

    # ── Step 1: Load existing ids for incremental scraping ───────────────────
    existing_ids = pipeline.load_existing_ids()
    existing_count = len(existing_ids)

    # ── Step 2: Scrape ────────────────────────────────────────────────────────
    new_listings = pipeline.scrape_new_listings(existing_ids)

    if not new_listings:
        logger.info("No new listings found. Storage is up to date.")
        return

    logger.info(f"Collected {len(new_listings)} new listings (had {existing_count} before).")

    # ── Step 3: Merge raw data ────────────────────────────────────────────────
    raw_path = pipeline.merge_and_save(new_listings, existing_count)

    # ── Step 4: Data quality check (full dataset) ─────────────────────────────
    df_total = pd.read_parquet(raw_path)
    pipeline.report_quality(df_total)

    # ── Step 5: CSV samples (drawn from the full dataset) ─────────────────────
    pipeline.save_dataset_samples(raw_path)

    # ── Step 6: Clean & save processed data ───────────────────────────────────
    pipeline.save_processed(raw_path)

    logger.info("Done!")


if __name__ == "__main__":
    setup_logging()
    main()
