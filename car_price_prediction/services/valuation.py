# car_price_prediction/services/valuation.py — Domain valuation and market analytics services

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from car_price_prediction.config import (
    CLEAN_PARQUET_PATH,
    PRICE_MAX_USD,
    PRICE_MIN_USD,
)

logger = logging.getLogger(__name__)

# Default market prior when brand/model is completely unknown in Cambodia market
_DEFAULT_BASE_PRICE_USD = 22_500.0
_ANNUAL_DEPRECIATION_RATE = 0.065  # 6.5% compound depreciation per year of age


class ValuationService:
    """
    Domain service for real-time Cambodia vehicle price valuation.

    Uses historical clean listing distributions from the Lakehouse layer
    combined with domain feature modifiers (model year age depreciation,
    condition, tax type, and mileage offsets) to produce accurate price
    estimates and confidence intervals.
    """

    def __init__(self, data_path: Path = CLEAN_PARQUET_PATH) -> None:
        self.data_path = data_path
        self._df: pd.DataFrame | None = None
        self._load_data()

    def _load_data(self) -> None:
        if self.data_path.exists():
            try:
                self._df = pd.read_parquet(self.data_path)
                logger.info(f"ValuationService loaded {len(self._df)} historical listings.")
            except Exception as e:
                logger.warning(f"Could not load historical dataset ({e}), falling back to domain priors.")
                self._df = None
        else:
            self._df = None

    def estimate_price(
        self,
        vehicle_brand: str | None = None,
        vehicle_model: str | None = None,
        vehicle_model_year: int | None = None,
        vehicle_condition: str = "used",
        vehicle_tax_type: str = "plate number",
        vehicle_mileage_km: int | None = None,
        vehicle_transmission: str = "automatic",
        vehicle_fuel_type: str = "petrol",
        province: str = "phnom-penh",
    ) -> dict[str, Any]:
        """
        Produce a market valuation, confidence bounds, and explanation metrics.
        """
        current_year = datetime.now(UTC).year
        target_year = vehicle_model_year or (current_year - 5)

        matched_sample_size = 0
        base_price = _DEFAULT_BASE_PRICE_USD
        valuation_basis = "general_cambodia_market_prior"

        if self._df is not None and not self._df.empty and "price" in self._df.columns:
            df = self._df[self._df["price"].notna()]
            brand_norm = vehicle_brand.strip().lower() if vehicle_brand else None
            model_norm = vehicle_model.strip().lower() if vehicle_model else None

            # 1. Exact match: (brand, model, year)
            if brand_norm and model_norm:
                subset = df[
                    (df["vehicle_brand"].str.lower() == brand_norm)
                    & (df["vehicle_model"].str.lower().str.contains(model_norm, regex=False, na=False))
                    & (df["vehicle_model_year"] == target_year)
                ]
                if len(subset) >= 3:
                    base_price = float(subset["price"].median())
                    matched_sample_size = len(subset)
                    valuation_basis = f"exact_match_{brand_norm}_{model_norm}_{target_year}"

            # 2. Match (brand, model) across all years
            if matched_sample_size == 0 and brand_norm and model_norm:
                subset = df[
                    (df["vehicle_brand"].str.lower() == brand_norm)
                    & (df["vehicle_model"].str.lower().str.contains(model_norm, regex=False, na=False))
                ]
                if len(subset) >= 3:
                    median_base = float(subset["price"].median())
                    ref_year = (
                        float(subset["vehicle_model_year"].median())
                        if "vehicle_model_year" in subset
                        else current_year - 5
                    )
                    year_diff = target_year - ref_year
                    base_price = median_base * ((1.0 + _ANNUAL_DEPRECIATION_RATE) ** year_diff)
                    matched_sample_size = len(subset)
                    valuation_basis = f"brand_model_median_{brand_norm}_{model_norm}"

            # 3. Match (brand) across all models
            if matched_sample_size == 0 and brand_norm:
                subset = df[df["vehicle_brand"].str.lower() == brand_norm]
                if len(subset) >= 3:
                    median_base = float(subset["price"].median())
                    ref_year = (
                        float(subset["vehicle_model_year"].median())
                        if "vehicle_model_year" in subset
                        else current_year - 5
                    )
                    year_diff = target_year - ref_year
                    base_price = median_base * ((1.0 + _ANNUAL_DEPRECIATION_RATE) ** year_diff)
                    matched_sample_size = len(subset)
                    valuation_basis = f"brand_median_{brand_norm}"

        # If pure prior, calculate baseline based on target year
        if matched_sample_size == 0:
            age = max(0, current_year - target_year)
            base_price = _DEFAULT_BASE_PRICE_USD * ((1.0 - _ANNUAL_DEPRECIATION_RATE) ** age)

        # Multipliers
        condition_norm = (vehicle_condition or "used").strip().lower()
        condition_multiplier = 1.25 if condition_norm == "new" else 1.0

        tax_norm = (vehicle_tax_type or "plate number").strip().lower()
        tax_multiplier = 1.10 if any(k in tax_norm for k in ("tax paper", "import", "ក្រដាសពន្ធ")) else 1.0

        mileage_adjustment = 0.0
        if vehicle_mileage_km is not None and vehicle_mileage_km > 0:
            expected_km = max(1, current_year - target_year) * 15_000
            diff_km = vehicle_mileage_km - expected_km
            # +/- 1.5% price per 20,000 km deviation from expected
            mileage_adjustment = -(diff_km / 20_000.0) * 0.015
            mileage_adjustment = max(-0.15, min(0.10, mileage_adjustment))

        final_price = base_price * condition_multiplier * tax_multiplier * (1.0 + mileage_adjustment)

        # Clamping within sanity bounds
        final_price = float(max(PRICE_MIN_USD, min(PRICE_MAX_USD, round(final_price, -2))))
        range_low = float(max(PRICE_MIN_USD, round(final_price * 0.88, -2)))
        range_high = float(min(PRICE_MAX_USD, round(final_price * 1.12, -2)))

        age_years = max(0, current_year - target_year)

        return {
            "predicted_price_usd": final_price,
            "price_range_low_usd": range_low,
            "price_range_high_usd": range_high,
            "market_sample_size": matched_sample_size,
            "valuation_basis": valuation_basis,
            "estimated_age_years": age_years,
            "currency": "USD",
        }


class MarketAnalyticsService:
    """
    Domain service providing Cambodia automotive market intelligence summaries.
    """

    def __init__(self, data_path: Path = CLEAN_PARQUET_PATH) -> None:
        self.data_path = data_path

    def get_market_summary(self) -> dict[str, Any]:
        """
        Aggregate market statistics from the clean Parquet layer.
        """
        if not self.data_path.exists():
            return {
                "total_listings": 0,
                "median_price_usd": None,
                "mean_price_usd": None,
                "min_price_usd": None,
                "max_price_usd": None,
                "top_brands": {},
                "top_provinces": {},
                "freshness_days": None,
            }

        df = pd.read_parquet(self.data_path)
        if df.empty or "price" not in df.columns:
            return {
                "total_listings": len(df),
                "median_price_usd": None,
                "mean_price_usd": None,
                "min_price_usd": None,
                "max_price_usd": None,
                "top_brands": {},
                "top_provinces": {},
                "freshness_days": None,
            }

        stats = df["price"].describe()

        top_brands: dict[str, Any] = {}
        if "vehicle_brand" in df.columns:
            brand_counts = df["vehicle_brand"].value_counts().head(8)
            for brand, count in brand_counts.items():
                brand_df = df[df["vehicle_brand"] == brand]
                top_brands[str(brand)] = {
                    "count": int(count),
                    "median_price_usd": float(brand_df["price"].median()) if not brand_df.empty else None,
                }

        top_provinces: dict[str, int] = {}
        if "province" in df.columns:
            for prov, count in df["province"].value_counts().head(5).items():
                top_provinces[str(prov)] = int(count)

        freshness_days: float | None = None
        if "scraped_at" in df.columns and df["scraped_at"].notna().any():
            newest = pd.to_datetime(df["scraped_at"]).max()
            freshness_days = round((pd.Timestamp.now(tz="UTC") - newest).total_seconds() / 86_400, 1)

        return {
            "total_listings": int(stats["count"]),
            "median_price_usd": float(stats["50%"]),
            "mean_price_usd": round(float(stats["mean"]), 2),
            "min_price_usd": float(stats["min"]),
            "max_price_usd": float(stats["max"]),
            "top_brands": top_brands,
            "top_provinces": top_provinces,
            "freshness_days": freshness_days,
        }
