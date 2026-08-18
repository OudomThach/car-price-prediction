# tests/test_pipeline.py — Tests for pipeline orchestration helpers

import logging

import pandas as pd
import pytest

from car_price_prediction.pipeline import (
    check_freshness,
    load_existing_ids,
    report_quality,
    save_dataset_samples,
)


@pytest.fixture
def quality_df() -> pd.DataFrame:
    """Full-schema DataFrame with two valid listings."""
    from car_price_prediction.schemas import ListingModel

    template = dict.fromkeys(ListingModel.model_fields)
    rows = [
        {"listing_id": "1", "price": 1000.0, "vehicle_brand": "Toyota"},
        {"listing_id": "2", "price": 2000.0, "vehicle_brand": "Lexus"},
    ]
    return pd.DataFrame([{**template, **row} for row in rows])


class TestLoadExistingIds:
    def test_missing_file_returns_empty_set(self, monkeypatch, tmp_path):
        monkeypatch.setattr("car_price_prediction.pipeline.RAW_PARQUET_PATH", tmp_path / "nope.parquet")
        ids = load_existing_ids()
        assert ids == set()

    def test_existing_file_returns_ids(self, monkeypatch, tmp_path):
        path = tmp_path / "cars.parquet"
        pd.DataFrame({"listing_id": ["1", "2", "3"]}).to_parquet(path, index=False)
        monkeypatch.setattr("car_price_prediction.pipeline.RAW_PARQUET_PATH", path)
        ids = load_existing_ids()
        assert ids == {"1", "2", "3"}


class TestReportQuality:
    def test_reports_summary(self, caplog, quality_df):
        caplog.set_level(logging.INFO)
        report_quality(quality_df)
        assert "Data Quality Summary" in caplog.text

    def test_empty_dataset_is_skipped(self, caplog):
        report_quality(pd.DataFrame())
        assert "no listings in dataset" in caplog.text

    def test_requirements_not_met_warns(self, caplog, quality_df):
        report_quality(quality_df)
        assert "Need ≥2,000 listings" in caplog.text

    def test_constant_column_is_flagged(self, caplog, quality_df):
        caplog.set_level(logging.INFO)
        report_quality(quality_df)
        assert "⚠ constant" in caplog.text


class TestSaveDatasetSamples:
    def test_writes_samples_from_full_dataset(self, tmp_path, quality_df):
        path = tmp_path / "cars.parquet"
        quality_df.to_parquet(path, index=False)
        save_dataset_samples(path, directory=tmp_path)
        assert (tmp_path / "khmer24_cars_sample_30.csv").exists()
        assert (tmp_path / "khmer24_cars_sample_60.csv").exists()

    def test_caps_below_requested_size(self, tmp_path, quality_df):
        path = tmp_path / "cars.parquet"
        quality_df.to_parquet(path, index=False)
        save_dataset_samples(path, directory=tmp_path)
        assert len(pd.read_csv(tmp_path / "khmer24_cars_sample_30.csv")) == 2


class TestCheckFreshness:
    def _df_with_scraped_at(self, scraped_at: str) -> pd.DataFrame:
        return pd.DataFrame({"price": [1000.0], "scraped_at": [scraped_at], "vehicle_brand": ["Toyota"]})

    def test_fresh_data_logs_info(self, caplog):
        caplog.set_level(logging.INFO)
        fresh = pd.Timestamp.now(tz="UTC").isoformat()
        check_freshness(self._df_with_scraped_at(fresh))
        assert "Data freshness:" in caplog.text
        assert "rerun the scraper" not in caplog.text

    def test_stale_data_warns(self, caplog):
        stale = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=30)).isoformat()
        check_freshness(self._df_with_scraped_at(stale))
        assert "days old" in caplog.text

    def test_missing_column_is_ignored(self):
        check_freshness(pd.DataFrame({"price": [1000.0]}))
