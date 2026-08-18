# car_price_prediction/pipeline.py — Orchestration steps for the Khmer24 data pipeline

import logging
from pathlib import Path

import pandas as pd

from car_price_prediction.cleaning import clean_data
from car_price_prediction.client import Khmer24Client
from car_price_prediction.config import (
    CLEAN_PARQUET_PATH,
    CLEAN_SAMPLE_PATH,
    DEFAULT_LANG,
    MAX_FRESHNESS_DAYS,
    MAX_PAGES,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    RAW_PARQUET_PATH,
    SAMPLE_SIZES,
    TARGET_CATEGORY,
    TARGET_PROVINCE,
)
from car_price_prediction.schemas import ListingModel
from car_price_prediction.storage import (
    merge_parquet,
    save_dataframe_sample,
    save_to_parquet,
    write_raw_dataframe,
)

logger = logging.getLogger(__name__)

# Phase 1 data requirements gate
MIN_TOTAL_LISTINGS = 2000
MIN_PRICED_LISTINGS = 1500


def load_existing_ids() -> set[str]:
    """
    Load already-stored listing ids for incremental scraping.

    Returns an empty set when no raw data exists yet.
    """
    path = RAW_PARQUET_PATH
    if not path.exists():
        return set()
    try:
        df = pd.read_parquet(path, columns=["listing_id"])
        ids = set(df["listing_id"].astype(str))
        logger.info(f"  Found {len(ids)} existing listings — running incremental sync.")
        return ids
    except Exception as exc:
        logger.warning(f"  Could not load existing data ({exc}) — running full scrape.")
        return set()


def scrape_new_listings(existing_ids: set[str]) -> list[ListingModel]:
    """Scrape new listings from the Khmer24 feed, skipping stored ids."""
    with Khmer24Client(lang=DEFAULT_LANG) as client:
        return client.scrape_category_listings(
            category_slug=TARGET_CATEGORY,
            province_slug=TARGET_PROVINCE,
            max_pages=MAX_PAGES,
            seen_ids=existing_ids,
        )


def merge_and_save(listings: list[ListingModel], existing_count: int) -> Path:
    """Merge new listings into the raw Parquet (or write it fresh)."""
    if existing_count == 0:
        return save_to_parquet(listings)
    df_new = pd.DataFrame([item.model_dump() for item in listings])
    merged = merge_parquet(RAW_PARQUET_PATH, df_new)
    merged.to_parquet(RAW_PARQUET_PATH, index=False)
    logger.info(f"Merged Parquet: {len(merged)} total rows -> {RAW_PARQUET_PATH}")
    return RAW_PARQUET_PATH


def save_dataset_samples(raw_path: Path, directory: Path | str = RAW_DATA_DIR) -> None:
    """Persist 30- and 60-row CSV samples drawn from the full raw dataset."""
    df = pd.read_parquet(raw_path)
    for n in SAMPLE_SIZES:
        path = save_dataframe_sample(df, n=n, directory=directory)
        logger.info(f"CSV sample -> {path}")


def report_quality(df_total: pd.DataFrame) -> None:
    """Log dataset-level quality and check the Phase 1 requirements gate."""
    if df_total.empty:
        logger.warning("Quality report skipped — no listings in dataset.")
        return

    n = len(df_total)
    n_priced = int(df_total["price"].notna().sum())
    logger.info("── Data Quality Summary (Full Dataset) ───────────────────")
    logger.info(f"  Total listings     : {n}")
    logger.info(f"  With price         : {n_priced}  ({n_priced / n * 100:.1f}%)")

    # Per-column completeness for every schema field
    logger.info("  ── Column completeness ──────────────────────────────────")
    for col in df_total.columns:
        n_non_null = int(df_total[col].notna().sum())
        pct = n_non_null / n * 100
        nunique = df_total[col].nunique(dropna=True)
        flag = "  ⚠ constant" if nunique <= 1 else ""
        logger.info(f"    {col:<24} {n_non_null:>5}/{n} ({pct:5.1f}%){flag}")

    requirements_met = True
    if n < MIN_TOTAL_LISTINGS:
        logger.warning(f"  ⚠  Need ≥{MIN_TOTAL_LISTINGS:,} listings (have {n:,}). Increase MAX_PAGES.")
        requirements_met = False
    if n_priced < MIN_PRICED_LISTINGS:
        logger.warning(f"  ⚠  Need ≥{MIN_PRICED_LISTINGS:,} priced listings (have {n_priced:,}).")
        requirements_met = False
    if requirements_met:
        logger.info("  ✅ Phase 1 data requirements met!")


def enrich_details(
    raw_path: Path,
    limit: int | None = None,
    delay: float | None = None,
    force: bool = False,
) -> int:
    """
    Fetch detail-page data for listings missing ``raw_detail_payload``.

    One request per listing (throttled via the client delay); the parquet
    file is checkpointed every 50 listings so an interrupted run resumes
    automatically (already-enriched ids are skipped unless ``force``).

    Args:
        raw_path: Raw Parquet file to enrich in place.
        limit:    Max number of listings to process (None = all).
        delay:    Override the inter-request delay (None = client default).
        force:    Re-fetch listings that already have a payload (repairs
                  payloads captured with an older, buggy decoder).

    Returns:
        Number of listings successfully enriched.
    """
    df = pd.read_parquet(raw_path)
    # Parquet may infer all-NaN columns as float64; enrichment writes strings
    # and dicts, so widen everything to object before assigning.
    df = df.astype(object)
    # Legacy rows from earlier enrichment runs stored real booleans — normalize
    # to 1/0 so columns never mix bools with ints (parquet rejects that).
    for column in ("is_like", "is_saved", "listing_available"):
        if column in df.columns:
            df[column] = df[column].map(lambda v: 1 if v is True else (0 if v is False else v))
    if force:
        missing = df["listing_id"].astype(str).tolist()
    else:
        missing = df.loc[df["raw_detail_payload"].isna() | (df["raw_detail_payload"] == ""), "listing_id"]
        missing = missing.astype(str).tolist()
    if limit is not None:
        missing = missing[:limit]
    if not missing:
        logger.info("All listings already enriched.")
        return 0

    enriched = 0
    with Khmer24Client() as client:
        for index, listing_id in enumerate(missing, start=1):
            row = client.fetch_listing_detail(listing_id, delay=delay)
            if row:
                position = df.index[df["listing_id"] == listing_id]
                if len(position):
                    for column, value in row.items():
                        df.at[position[0], column] = value
                    enriched += 1
            if index % 50 == 0:
                write_raw_dataframe(df, raw_path)  # checkpoint — resumable
                logger.info(f"Detail enrichment {index}/{len(missing)} ({enriched} ok)")

    write_raw_dataframe(df, raw_path)
    logger.info(f"Enrichment complete: {enriched}/{len(missing)} listings.")
    return enriched


def save_processed(raw_path: Path) -> None:
    """Clean the full raw dataset and persist the processed outputs."""
    logger.info("Running data cleaning...")
    df_raw_full = pd.read_parquet(raw_path)
    df_clean = clean_data(df_raw_full)

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df_clean.to_parquet(CLEAN_PARQUET_PATH, index=False)
    logger.info(f"Cleaned data -> {CLEAN_PARQUET_PATH}")

    df_clean.head(60).to_csv(CLEAN_SAMPLE_PATH, index=False, encoding="utf-8-sig")
    logger.info(f"Cleaned sample (60 rows) -> {CLEAN_SAMPLE_PATH}")

    report_processed_summary(df_clean)
    check_freshness(df_clean)


def report_processed_summary(df_clean: pd.DataFrame) -> None:
    """Log price distribution and top brands from the cleaned dataset."""
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


def check_freshness(df_clean: pd.DataFrame) -> None:
    """Warn when the newest scrape is older than MAX_FRESHNESS_DAYS."""
    if "scraped_at" not in df_clean.columns or df_clean["scraped_at"].isna().all():
        return
    newest = pd.to_datetime(df_clean["scraped_at"]).max()
    age_days = (pd.Timestamp.now(tz="UTC") - newest).total_seconds() / 86_400
    if age_days > MAX_FRESHNESS_DAYS:
        logger.warning(
            f"  ⚠  Data is {age_days:.0f} days old (newest scrape {newest.date()}) "
            f"— rerun the scraper or trigger the refresh workflow."
        )
    else:
        logger.info(f"Data freshness: newest scrape {newest.date()} ({age_days:.0f} days old).")
