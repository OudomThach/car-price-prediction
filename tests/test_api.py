# tests/test_api.py — Unit tests for the FastAPI REST API

import pytest
from fastapi.testclient import TestClient

from car_price_prediction.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_check_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "0.1.0"


class TestPredictEndpoint:
    def test_predict_toyota_camry_success(self, client):
        payload = {
            "vehicle_brand": "Toyota",
            "vehicle_model": "Camry",
            "vehicle_model_year": 2019,
            "vehicle_condition": "used",
            "vehicle_tax_type": "plate number",
            "vehicle_mileage_km": 50000,
            "vehicle_transmission": "automatic",
            "vehicle_fuel_type": "petrol",
            "province": "phnom-penh",
        }
        response = client.post("/api/v1/predict", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "predicted_price_usd" in data
        assert data["predicted_price_usd"] > 500
        assert data["price_range_low_usd"] <= data["predicted_price_usd"]
        assert data["price_range_high_usd"] >= data["predicted_price_usd"]
        assert data["currency"] == "USD"
        assert "market_sample_size" in data
        assert "valuation_basis" in data
        assert data["estimated_age_years"] >= 0

    def test_predict_new_condition_premium(self, client):
        used_payload = {
            "vehicle_brand": "Ford",
            "vehicle_model": "Ranger",
            "vehicle_model_year": 2023,
            "vehicle_condition": "used",
        }
        new_payload = {
            "vehicle_brand": "Ford",
            "vehicle_model": "Ranger",
            "vehicle_model_year": 2023,
            "vehicle_condition": "new",
        }
        res_used = client.post("/api/v1/predict", json=used_payload).json()
        res_new = client.post("/api/v1/predict", json=new_payload).json()
        assert res_new["predicted_price_usd"] > res_used["predicted_price_usd"]

    def test_predict_unknown_brand_fallback(self, client):
        payload = {
            "vehicle_brand": "UnknownBrandXYZ",
            "vehicle_model": "ModelABC",
            "vehicle_model_year": 2020,
        }
        response = client.post("/api/v1/predict", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["predicted_price_usd"] > 0
        assert data["valuation_basis"] == "general_cambodia_market_prior"

    def test_predict_invalid_year_fails_validation(self, client):
        payload = {
            "vehicle_brand": "Toyota",
            "vehicle_model": "Camry",
            "vehicle_model_year": 1950,  # Below MIN_VEHICLE_YEAR (1990)
        }
        response = client.post("/api/v1/predict", json=payload)
        assert response.status_code == 422

    def test_predict_negative_mileage_fails_validation(self, client):
        payload = {
            "vehicle_brand": "Toyota",
            "vehicle_model": "Camry",
            "vehicle_model_year": 2020,
            "vehicle_mileage_km": -5000,
        }
        response = client.post("/api/v1/predict", json=payload)
        assert response.status_code == 422


class TestMarketSummaryEndpoint:
    def test_market_summary_returns_200(self, client):
        response = client.get("/api/v1/market/summary")
        assert response.status_code == 200
        data = response.json()
        assert "total_listings" in data
        assert "median_price_usd" in data
        assert "top_brands" in data
        assert "top_provinces" in data
