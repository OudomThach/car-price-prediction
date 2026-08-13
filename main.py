# main.py — CLI entry point for the Khmer24 car price data collection pipeline
#
# Saves: Parquet (full data) + CSV samples (30 & 60 rows)
#
# Run:  python main.py
# Run with env override:  MAX_PAGES=5 python main.py

import logging
import sys

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError for Khmer)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import os
import pandas as pd

from src.config import (
    TARGET_CATEGORY, TARGET_PROVINCE, MAX_PAGES,
    PARQUET_FILENAME,
    RAW_DATA_DIR, PROCESSED_DATA_DIR,
)
from src.client import Khmer24Client
from src.storage import save_to_parquet, save_sample_csv
from src.cleaning import clean_data

# ── Logging setup ──────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join("logs", "scraper.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("=" * 65)
    logger.info("Cambodia Car Price Prediction — Data Collection Pipeline")
    logger.info(f"  Category  : {TARGET_CATEGORY}")
    logger.info(f"  Province  : {TARGET_PROVINCE or 'ALL'}")
    logger.info(f"  Max pages : {MAX_PAGES}  ({MAX_PAGES * 30} listings max)")
    logger.info("=" * 65)

    # ── Step 1: Load existing IDs for incremental scraping (Fix #3) ──────────
    existing_parquet = os.path.join(RAW_DATA_DIR, PARQUET_FILENAME)
    seen_ids: set = set()
    existing_count = 0
    if os.path.exists(existing_parquet):
        try:
            df_existing = pd.read_parquet(existing_parquet, columns=["id"])
            seen_ids = set(df_existing["id"].astype(str))
            existing_count = len(seen_ids)
            logger.info(f"  Found {existing_count} existing listings — running incremental sync.")
        except Exception as e:
            logger.warning(f"  Could not load existing data ({e}) — running full scrape.")

    # ── Step 2: Scrape ─────────────────────────────────────────────────────
    with Khmer24Client(lang="en") as client:
        new_listings = client.scrape_category_feed(
            category_slug=TARGET_CATEGORY,
            province_slug=TARGET_PROVINCE,
            max_pages=MAX_PAGES,
            seen_ids=seen_ids,
        )

    if not new_listings:
        logger.info("No new listings found. Storage is up to date.")
        return

    logger.info(f"Collected {len(new_listings)} new listings (had {existing_count} before).")

    # ── Step 3: Save raw data ──────────────────────────────────────────────────
    # Merge new listings with existing ones before saving.
    import json as _json

    def _serialize_df(df: pd.DataFrame) -> pd.DataFrame:
        """JSON-encode all list/dict cells so Parquet schema stays flat."""
        df = df.copy()
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].apply(
                    lambda x: _json.dumps(x) if isinstance(x, (list, dict)) else x
                )
        return df

    if existing_count > 0:
        df_old = pd.read_parquet(existing_parquet)  # raw strings
        df_new = _serialize_df(pd.DataFrame([item.model_dump() for item in new_listings]))
        df_merged = (
            pd.concat([df_old, df_new], ignore_index=True)
            .drop_duplicates(subset=["id"])
        )
        df_merged.to_parquet(existing_parquet, index=False)
        logger.info(f"Merged Parquet: {len(df_merged)} total rows -> {existing_parquet}")
    else:
        parquet_path = save_to_parquet(new_listings, PARQUET_FILENAME, RAW_DATA_DIR)
        logger.info(f"Raw data  -> Parquet : {parquet_path}")

    csv_30_path = save_sample_csv(new_listings, n=30, directory=RAW_DATA_DIR)
    csv_60_path = save_sample_csv(new_listings, n=60, directory=RAW_DATA_DIR)
    logger.info(f"CSV sample-> 30 rows : {csv_30_path}")
    logger.info(f"CSV sample-> 60 rows : {csv_60_path}")

    # ── Step 4: Data quality check ──────────────────────────────────────────────────
    df_raw_new = pd.DataFrame([item.model_dump() for item in new_listings])
    n_with_price = df_raw_new["price"].notna().sum()
    n_with_year  = df_raw_new["car_year"].notna().sum()
    n_with_brand = df_raw_new["vehicle_brand"].notna().sum()
    n_with_prov  = df_raw_new["province"].notna().sum()

    logger.info("── Data Quality Summary (New Scraping Batch) ───────────")
    logger.info(f"  Total listings   : {len(df_raw_new)}")
    logger.info(f"  With price       : {n_with_price}  ({n_with_price/len(df_raw_new)*100:.1f}%)")
    logger.info(f"  With car_year    : {n_with_year}   ({n_with_year/len(df_raw_new)*100:.1f}%)")
    logger.info(f"  With brand       : {n_with_brand}  ({n_with_brand/len(df_raw_new)*100:.1f}%)")
    logger.info(f"  With province    : {n_with_prov}   ({n_with_prov/len(df_raw_new)*100:.1f}%)")

    # Phase 1 minimum data requirements check
    requirements_met = True
    if len(df_raw_new) < 2000:
        logger.warning(f"  ⚠  Need ≥2,000 listings (have {len(df_raw_new)}). Increase MAX_PAGES.")
        requirements_met = False
    if n_with_price < 1500:
        logger.warning(f"  ⚠  Need ≥1,500 priced listings (have {n_with_price}).")
        requirements_met = False
    if requirements_met:
        logger.info("  ✅ Phase 1 data requirements met!")

    # ── Step 5: Clean & save processed data ─────────────────────────────────
    logger.info("Running data cleaning...")
    # Load full raw dataset for cleaning
    df_raw_full = pd.read_parquet(existing_parquet)
    df_clean    = clean_data(df_raw_full)

    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
    clean_parquet_path = os.path.join(PROCESSED_DATA_DIR, "cars_clean.parquet")
    df_clean.to_parquet(clean_parquet_path, index=False)
    logger.info(f"Cleaned data -> {clean_parquet_path}")

    clean_csv_path = os.path.join(PROCESSED_DATA_DIR, "cars_clean_sample.csv")
    df_clean.head(60).to_csv(clean_csv_path, index=False, encoding="utf-8-sig")
    logger.info(f"Cleaned sample (60 rows) -> {clean_csv_path}")

    # ── Step 6: Quick summary stats ──────────────────────────────────────────
    if df_clean["price"].notna().any():
        price_stats = df_clean["price"].describe()
        logger.info("── Price Distribution (USD) ──────────────────────────────")
        logger.info(f"  Median  : ${price_stats['50%']:,.0f}")
        logger.info(f"  Mean    : ${price_stats['mean']:,.0f}")
        logger.info(f"  Min     : ${price_stats['min']:,.0f}")
        logger.info(f"  Max     : ${price_stats['max']:,.0f}")

    if "vehicle_brand" in df_clean.columns:
        logger.info("── Top 10 Brands by Listing Count ───────────────────────")
        for brand, count in df_clean["vehicle_brand"].value_counts().head(10).items():
            logger.info(f"  {brand:<20} {count}")

    logger.info("Done!")


if __name__ == "__main__":
    main()
