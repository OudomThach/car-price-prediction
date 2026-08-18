# car_price_prediction/cleaning.py — Data cleaning for raw Khmer24 car listings
#
# Takes a raw scraped DataFrame and applies quality rules to produce
# a clean, analysis-ready dataset. Feature engineering lives separately
# in a future transform module (Phase 2+).

import logging
from datetime import UTC, datetime

import pandas as pd

from car_price_prediction.config import (
    MAX_VEHICLE_YEAR_OFFSET,
    MIN_VEHICLE_YEAR,
    PRICE_MAX_USD,
    PRICE_MIN_USD,
)
from car_price_prediction.schemas import CLEAN_COLUMNS

logger = logging.getLogger(__name__)

# Categorical standardization policy:
# - Values are lowercased and stripped (e.g. "Used" -> "used")
# - Missing values become the lowercase sentinel "unknown"
# - Known synonyms collapse onto a single canonical value
_UNKNOWN = "unknown"
_CATEGORICAL_COLUMNS = (
    "vehicle_condition",
    "vehicle_tax_type",
    "vehicle_brand",
    "province",
    "vehicle_transmission",
    "vehicle_fuel_type",
)
_SYNONYMS: dict[str, dict[str, str]] = {
    "vehicle_fuel_type": {"gasoline": "petrol", "gas": "petrol"},
    "vehicle_transmission": {"auto": "automatic"},
    "vehicle_condition": {"second hand": "used", "pre-owned": "used"},
}


def _current_year() -> int:
    """Current calendar year — the model-year bound must track time."""
    return datetime.now(UTC).year


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply data-quality rules to the raw scraped DataFrame.

    Rules
    -----
    1. Drop rows with no price (target variable is required for modeling).
    2. Remove price outliers outside $500 – $300,000.
    3. Drop rows with impossible model years (keep 1990 – current year + 1).
    4. Select the processed columns (``CLEAN_COLUMNS`` — the repo-equivalent
       34-column contract); all other raw columns stay in the raw dataset.
    5. Standardize categorical columns: lowercase + fill missing -> "unknown".
    6. Deduplicate by listing ``listing_id`` (keep the most recent occurrence).

    Ends with integrity assertions on the result so downstream stages never
    consume a dataset that violates the core invariants, including the
    ``CLEAN_COLUMNS`` data contract from ``car_price_prediction.schemas``.

    Parameters
    ----------
    df : pd.DataFrame
        Raw DataFrame built from ``ListingModel.model_dump()`` records.

    Returns
    -------
    pd.DataFrame
        Cleaned DataFrame with reset index.
    """
    df = df.copy()
    initial = len(df)

    # Rule 1 — price must exist
    df = df.dropna(subset=["price"])
    logger.info(f"Rule 1 (no price)          : removed {initial - len(df):>4}  | remaining {len(df)}")

    # Rule 2 — price sanity bounds
    before = len(df)
    df = df[(df["price"] >= PRICE_MIN_USD) & (df["price"] <= PRICE_MAX_USD)]
    logger.info(f"Rule 2 (price bounds)      : removed {before - len(df):>4}  | remaining {len(df)}")

    # Rule 3 — model-year sanity bounds (allow null years to pass through)
    year_col = "vehicle_model_year"
    if year_col in df.columns:
        before = len(df)
        max_year = _current_year() + MAX_VEHICLE_YEAR_OFFSET
        df = df[df[year_col].between(MIN_VEHICLE_YEAR, max_year, inclusive="both") | df[year_col].isna()]
        logger.info(f"Rule 3 (year bounds)       : removed {before - len(df):>4}  | remaining {len(df)}")

    # Rule 4 — select the processed columns (repo-equivalent 34-column contract)
    df = df[list(CLEAN_COLUMNS)]
    logger.info(f"Rule 4 (processed columns) : selected {len(CLEAN_COLUMNS)} columns (CLEAN_COLUMNS)")

    # Rule 5 — standardize categorical columns (lowercase + "unknown")
    _fill_str(df, _CATEGORICAL_COLUMNS, default=_UNKNOWN)

    # Rule 6 — remove duplicates (keep most recent occurrence)
    before = len(df)
    df = df.drop_duplicates(subset=["listing_id"], keep="last")
    logger.info(f"Rule 6 (duplicates)        : removed {before - len(df):>4}  | remaining {len(df)}")

    logger.info(f"Cleaning complete: {initial} -> {len(df)} rows ({initial - len(df)} removed total)")
    df = df.reset_index(drop=True)

    # ── Integrity assertions (fail loudly, never silently pass bad data) ───────
    assert list(df.columns) == list(CLEAN_COLUMNS), "Clean columns violate CLEAN_COLUMNS contract"
    assert df["listing_id"].notna().all(), "Missing listing ids"
    assert df["listing_id"].is_unique, "Duplicate listing ids"
    assert (df["price"] >= PRICE_MIN_USD).all() and (df["price"] <= PRICE_MAX_USD).all(), "Price outside bounds"
    if year_col in df.columns:
        max_year = _current_year() + MAX_VEHICLE_YEAR_OFFSET
        year_ok = df[year_col].isna() | df[year_col].between(MIN_VEHICLE_YEAR, max_year, inclusive="both")
        assert year_ok.all(), "vehicle_model_year outside bounds"

    return df


# ── Helpers ────────────────────────────────────────────────────────────────────


def _fill_str(df: pd.DataFrame, cols: tuple[str, ...], default: str) -> None:
    """In-place: lowercase, collapse synonyms, and fill missing values."""
    for col in cols:
        if col not in df.columns:
            continue
        df[col] = df[col].astype("string").str.strip().str.lower()
        synonyms = _SYNONYMS.get(col, {})
        if synonyms:
            df[col] = df[col].replace(synonyms)
        df[col] = df[col].fillna(default)
