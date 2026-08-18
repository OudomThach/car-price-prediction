# tests/conftest.py — shared fixtures

import pandas as pd
import pytest

from car_price_prediction.schemas import ListingModel

# Full raw schema (every field the model captures)
ALL_RAW_COLUMNS = tuple(ListingModel.model_fields)


@pytest.fixture
def make_listing():
    """Factory for minimal valid ListingModel records."""

    def _make(rid: str, price: float | None = 1000.0, **overrides) -> ListingModel:
        data = {"listing_id": rid, "listing_title": f"Car {rid}", "price": price}
        data.update(overrides)
        return ListingModel(**data)

    return _make


@pytest.fixture
def sample_api_listing() -> dict:
    """A minimal realistic Khmer24 Posts API payload item (fields=all shape)."""
    return {
        "id": 13784836,
        "title": "2024 COROLLA CROSS HEV",
        "price": "40900.00",
        "category": {"id": "67", "en_name": "Cars for Sale", "slug": "cars-for-sale"},
        "location": {
            "id": "32",
            "en_name": "Phnom Penh",
            "slug": "phnom-penh",
            "en_name2": "Ruessei Kaev, Phnom Penh",
            "en_name3": "Tuol Sangkae 1, Ruessei Kaev, Phnom Penh",
            "map": {"x": "11.56245", "y": "104.91601", "z": 15},
        },
        "user": {
            "id": 519591,
            "name": "Tang",
            "username": "TangMengSrunAuto",
            "user_type": "2",
            "photo": "https://images.khmer24.co/store/avatar.jpg",
            "is_verify": "1",
        },
        "storeid": "88321",
        "available": 1,
        "status": "active",
        "phone": ["012998785", "098729999"],
        "highlight_specs": [
            {"field": "car-year", "value": 2024},
            {"field": "tax-type", "value": "Plate Number"},
        ],
        "photos": [
            "https://images.khmer24.co/26-08-12/car-b.jpg",
            "https://images.khmer24.co/26-08-12/car-c.jpg",
        ],
        "posted_date": "2026-07-18 20:58:52",
        "views": 0,
    }


@pytest.fixture
def raw_listings_df() -> pd.DataFrame:
    """A full-schema raw DataFrame spanning the clean_data quality rules."""
    template = dict.fromkeys(ALL_RAW_COLUMNS)
    rows = [
        {"listing_id": "1", "price": 12000, "vehicle_model_year": 2019, "vehicle_condition": "Used"},
        {"listing_id": "2", "price": None, "vehicle_model_year": 2015, "vehicle_condition": "Used"},
        {"listing_id": "3", "price": 100, "vehicle_model_year": 2020, "vehicle_condition": "Used"},
        {"listing_id": "4", "price": 400000, "vehicle_model_year": 2021, "vehicle_condition": "Used"},
        {"listing_id": "5", "price": 20000, "vehicle_model_year": 1970, "vehicle_condition": "New"},
        {"listing_id": "6", "price": 20000, "vehicle_model_year": None, "vehicle_condition": "Used"},
        {"listing_id": "1", "price": 12000, "vehicle_model_year": 2019, "vehicle_condition": "Used"},
    ]
    return pd.DataFrame([{**template, **row} for row in rows])
