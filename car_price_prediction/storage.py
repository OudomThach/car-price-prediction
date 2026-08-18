# car_price_prediction/storage.py — Parquet & CSV persistence for ListingModel records

import json
import logging
from pathlib import Path

import pandas as pd

from car_price_prediction.config import (
    RANDOM_SEED,
    RAW_DATA_DIR,
    RAW_PARQUET_FILENAME,
    SAMPLE_CSV_TEMPLATE,
    SAMPLE_SIZES,
)
from car_price_prediction.schemas import ListingModel

logger = logging.getLogger(__name__)

# Columns stored as JSON strings inside Parquet (restored on load)
_JSON_COLUMNS = (
    "seller_phones",
    "raw_specs",
    "image_urls",
    "location_coordinates",
    "detail_specs",
    "raw_feed_payload",
    "raw_detail_payload",
)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _serialize_df(df: pd.DataFrame) -> pd.DataFrame:
    """JSON-encode all list/dict cells so the Parquet schema stays flat."""
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x)
    return df


# ── Parquet ────────────────────────────────────────────────────────────────────


def save_to_parquet(
    listings: list[ListingModel],
    filename: str = RAW_PARQUET_FILENAME,
    directory: Path | str = RAW_DATA_DIR,
) -> Path:
    """
    Serialize all ``ListingModel`` records to a Parquet file.

    List/dict columns (``seller_phones``, ``raw_specs``) are JSON-encoded so the
    Parquet schema stays flat and portable across tools.

    Returns the path to the written file.
    """
    path = Path(directory) / filename
    _ensure_dir(path.parent)

    rows = [item.model_dump() for item in listings]
    df = _serialize_df(pd.DataFrame(rows))

    df.to_parquet(path, index=False)
    logger.info(f"Saved {len(df)} records to Parquet -> {path}")
    return path


def load_from_parquet(
    filename: str = RAW_PARQUET_FILENAME,
    directory: Path | str = RAW_DATA_DIR,
) -> pd.DataFrame:
    """
    Load listings from an existing Parquet file, restoring serialized columns.
    """
    path = Path(directory) / filename
    df = pd.read_parquet(path)

    # Restore list/dict columns from JSON strings
    for col in _JSON_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: json.loads(x) if isinstance(x, str) and x.startswith(("[", "{")) else x)
    return df


def merge_parquet(existing_path: Path, new_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge new listings into an existing raw Parquet DataFrame.

    Reads the existing file, appends the serialized new records, and
    deduplicates by listing listing_id keeping the most recent occurrence —
    a re-scraped listing reflects the seller's latest price, so the
    newest scrape wins on conflict.

    The result is reindexed to the canonical ``ListingModel`` column
    order, so schema-evolved data (new columns added later) still
    conforms to the data contract.
    """
    df_old = pd.read_parquet(existing_path)
    df_new = _serialize_df(new_df)
    merged = pd.concat([df_old, df_new], ignore_index=True).drop_duplicates(subset=["listing_id"], keep="last")
    return merged.reindex(columns=list(ListingModel.model_fields))


def write_raw_dataframe(df: pd.DataFrame, path: Path | str) -> Path:
    """
    Persist a raw DataFrame to Parquet with the canonical column order.

    List/dict cells are JSON-encoded (same convention as ``save_to_parquet``)
    and the column order is pinned to the ``ListingModel`` schema so the
    written file always satisfies the data contract.
    """
    path = Path(path)
    _ensure_dir(path.parent)
    df = df.reindex(columns=list(ListingModel.model_fields))
    _serialize_df(df).to_parquet(path, index=False)
    logger.info(f"Saved {len(df)} records to Parquet -> {path}")
    return path


# ── CSV sample ─────────────────────────────────────────────────────────────────

# Columns written to the CSV samples — human-readable subset, no raw blobs
CSV_SAMPLE_COLUMNS = [
    "listing_id",
    "listing_title",
    "price",
    "vehicle_model_year",
    "vehicle_condition",
    "vehicle_tax_type",
    "vehicle_brand",
    "vehicle_model",
    "vehicle_mileage_km",
    "vehicle_fuel_type",
    "vehicle_transmission",
    "vehicle_engine_cc",
    "vehicle_color",
    "province",
    "district",
    "seller_type",
    "view_count",
    "posted_at",
    "scraped_at",
    "is_premium",
    "listing_url",
]


def save_sample_csv(
    listings: list[ListingModel],
    n: int = 30,
    directory: Path | str = RAW_DATA_DIR,
) -> Path:
    """
    Save a random sample of ``n`` listings (30 or 60) to a CSV file.

    Only the human-readable columns are included — large blobs like ``raw_specs``
    and ``seller_phones`` are omitted to keep the CSV clean and easy to open
    in Excel / Google Sheets.

    Args:
        listings: Full list of scraped ``ListingModel`` records.
        n:        Sample size — 30 or 60 (see ``SAMPLE_SIZES`` in config).
        directory: Output directory (default: ``data/raw/``).

    Returns:
        Path to the written CSV file.
    """
    df = pd.DataFrame([item.model_dump() for item in listings])
    return save_dataframe_sample(df, n=n, directory=directory)


def save_dataframe_sample(
    df: pd.DataFrame,
    n: int = 30,
    directory: Path | str = RAW_DATA_DIR,
) -> Path:
    """
    Save a random sample of ``n`` rows from a raw listings DataFrame to CSV.

    Only ``CSV_SAMPLE_COLUMNS`` are written. Sampling is seeded with
    ``RANDOM_SEED`` for reproducibility and capped at the available rows.

    Args:
        df:        Raw DataFrame built from ``ListingModel.model_dump()``.
        n:         Sample size — 30 or 60 (see ``SAMPLE_SIZES`` in config).
        directory: Output directory (default: ``data/raw/``).

    Returns:
        Path to the written CSV file.
    """
    if n not in SAMPLE_SIZES:
        raise ValueError(f"Sample size must be one of {SAMPLE_SIZES}, got {n}")

    directory = Path(directory)
    _ensure_dir(directory)
    filename = SAMPLE_CSV_TEMPLATE.format(n=n)
    path = directory / filename

    # Keep only columns that exist in this DataFrame
    cols = [c for c in CSV_SAMPLE_COLUMNS if c in df.columns]
    df_sample = df[cols]

    # Random sample (seed fixed for reproducibility); cap at total available
    sample_size = min(n, len(df_sample))
    df_sample = df_sample.sample(n=sample_size, random_state=RANDOM_SEED).reset_index(drop=True)

    df_sample.to_csv(path, index=False, encoding="utf-8-sig")  # utf-8-sig for Excel compat
    logger.info(f"Saved {sample_size}-row CSV sample -> {path}")
    return path
