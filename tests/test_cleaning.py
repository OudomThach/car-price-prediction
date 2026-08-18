# tests/test_cleaning.py — Tests for clean_data quality rules

import pandas as pd
import pytest

from car_price_prediction.cleaning import clean_data
from car_price_prediction.schemas import CLEAN_COLUMNS


class TestCleanData:
    def test_rules_remove_bad_rows(self, raw_listings_df):
        df = clean_data(raw_listings_df)
        assert len(df) == 2  # ids 6 and 1 survive
        assert list(df["listing_id"]) == ["6", "1"]  # duplicate keeps the newest scrape

    def test_condition_standardized_to_lowercase(self, raw_listings_df):
        df = clean_data(raw_listings_df)
        assert (df["vehicle_condition"] == "used").all()

    def test_string_fields_filled_with_unknown_lowercase(self, raw_listings_df):
        df = clean_data(raw_listings_df)
        for col in ("vehicle_tax_type", "vehicle_brand", "province", "vehicle_transmission", "vehicle_fuel_type"):
            assert (df[col] == "unknown").all()

    def test_null_model_year_allowed_to_pass(self, raw_listings_df):
        df = clean_data(raw_listings_df)
        year = df.loc[df["listing_id"] == "6", "vehicle_model_year"].iloc[0]
        assert pd.isna(year)

    def test_missing_year_column_violates_contract(self, raw_listings_df):
        """A partial frame cannot satisfy the CLEAN_COLUMNS contract — fail loudly."""
        df = raw_listings_df.drop(columns=["vehicle_model_year"])
        with pytest.raises(KeyError):
            clean_data(df)

    def test_duplicate_ids_removed(self, raw_listings_df):
        df = clean_data(raw_listings_df)
        assert df["listing_id"].is_unique

    def test_currency_stays_in_processed(self, raw_listings_df):
        """Parity with the repo — currency is part of the 34 processed columns."""
        df = clean_data(raw_listings_df)
        assert "currency" in df.columns

    def test_extra_raw_columns_excluded_from_processed(self, raw_listings_df):
        df = clean_data(raw_listings_df)
        for col in (
            "raw_feed_payload",
            "location_coordinates",
            "description",
            "seller_telco",
            "image_urls",
            "sale_price",
        ):
            assert col not in df.columns

    def test_output_columns_match_clean_contract(self, raw_listings_df):
        df = clean_data(raw_listings_df)
        assert list(df.columns) == list(CLEAN_COLUMNS)

    def test_fuel_synonyms_collapse_to_petrol(self, raw_listings_df):
        df = raw_listings_df.copy()
        df["vehicle_fuel_type"] = "Gasoline"
        result = clean_data(df)
        assert (result["vehicle_fuel_type"] == "petrol").all()


def test_price_outlier_bounds_are_config_driven():
    """The 500/300k bounds must live in config, not hard-coded literals."""
    import car_price_prediction.cleaning as cleaning
    import car_price_prediction.config as config

    assert cleaning.PRICE_MIN_USD == config.PRICE_MIN_USD
    assert cleaning.PRICE_MAX_USD == config.PRICE_MAX_USD
