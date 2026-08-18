# tests/test_storage.py — Persistence round-trip and merge tests

import pandas as pd
import pytest

from car_price_prediction.storage import (
    CSV_SAMPLE_COLUMNS,
    load_from_parquet,
    merge_parquet,
    save_dataframe_sample,
    save_sample_csv,
    save_to_parquet,
)


class TestSaveLoadRoundTrip:
    def test_parquet_round_trip_restores_json_columns(self, tmp_path, make_listing):
        path = save_to_parquet(
            [
                make_listing(
                    "1",
                    seller_phones=["012345"],
                    raw_specs={"car-year": 2020},
                    image_urls=["https://images.khmer24.co/a-b.jpg"],
                    location_coordinates={"x": "11.5", "y": "104.9", "z": 15},
                    raw_feed_payload={"listing_id": 1},
                    detail_specs={"brand": "Toyota"},
                    raw_detail_payload={"listing_id": 1, "title": "Car"},
                ),
                make_listing("2"),
            ],
            directory=tmp_path,
        )
        assert path.exists()

        df = load_from_parquet("khmer24_cars.parquet", directory=tmp_path)
        assert len(df) == 2
        assert df.loc[0, "seller_phones"] == ["012345"]
        assert df.loc[0, "raw_specs"] == {"car-year": 2020}
        assert df.loc[0, "image_urls"] == ["https://images.khmer24.co/a-b.jpg"]
        assert df.loc[0, "location_coordinates"] == {"x": "11.5", "y": "104.9", "z": 15}
        assert df.loc[0, "raw_feed_payload"] == {"listing_id": 1}
        assert df.loc[0, "detail_specs"] == {"brand": "Toyota"}
        assert df.loc[0, "raw_detail_payload"] == {"listing_id": 1, "title": "Car"}

    def test_save_sample_csv_caps_below_requested_size(self, tmp_path, make_listing):
        path = save_sample_csv([make_listing("1"), make_listing("2"), make_listing("3")], directory=tmp_path)
        df = pd.read_csv(path)
        assert len(df) == 3  # fewer listings than n=30

    def test_save_sample_csv_writes_final_columns(self, tmp_path, make_listing):
        path = save_sample_csv([make_listing("1")] * 40, directory=tmp_path)
        df = pd.read_csv(path)
        assert list(df.columns) == CSV_SAMPLE_COLUMNS

    def test_save_sample_csv_rejects_invalid_size(self, tmp_path):
        with pytest.raises(ValueError):
            save_sample_csv([], n=45, directory=tmp_path)

    def test_save_dataframe_sample_uses_full_schema_df(self, tmp_path, raw_listings_df):
        path = save_dataframe_sample(raw_listings_df, n=30, directory=tmp_path)
        df = pd.read_csv(path)
        assert len(df) == 7
        assert list(df.columns) == CSV_SAMPLE_COLUMNS


class TestMergeParquet:
    def test_merge_dedupes_by_id_keeping_latest(self, tmp_path):
        old = pd.DataFrame([{"listing_id": "1", "price": 1000}, {"listing_id": "2", "price": 2000}])
        old_path = tmp_path / "old.parquet"
        old.to_parquet(old_path, index=False)

        new = pd.DataFrame([{"listing_id": "1", "price": 9999}, {"listing_id": "3", "price": 3000}])
        merged = merge_parquet(old_path, new)

        assert len(merged) == 3
        row1 = merged.loc[merged["listing_id"] == "1", "price"].iloc[0]
        assert row1 == 9999  # newest scrape wins on conflict

    def test_merge_reindexes_to_canonical_schema_order(self, tmp_path):
        """Schema-evolved old rows must conform to the canonical column order."""
        from car_price_prediction.schemas import ListingModel

        old = pd.DataFrame([{"listing_id": "1", "price": 1000}])
        old_path = tmp_path / "old.parquet"
        old.to_parquet(old_path, index=False)

        new = pd.DataFrame([ListingModel(listing_id="2", listing_title="Car 2").model_dump()])
        merged = merge_parquet(old_path, new)

        assert list(merged.columns) == list(ListingModel.model_fields)
        assert merged.loc[merged["listing_id"] == "1", "listing_title"].isna().all()  # old row backfilled
