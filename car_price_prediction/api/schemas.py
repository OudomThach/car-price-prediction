# car_price_prediction/api/schemas.py — Request & Response DTOs for the REST API

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from car_price_prediction.config import MAX_VEHICLE_YEAR_OFFSET, MIN_VEHICLE_YEAR


class PredictionRequest(BaseModel):
    """
    Input contract for car price estimation.
    """

    vehicle_brand: str = Field(..., description="Car make/brand (e.g. 'Toyota', 'Lexus', 'Ford')", examples=["Toyota"])
    vehicle_model: str = Field(..., description="Car model name (e.g. 'Camry', 'RX350', 'Prius')", examples=["Camry"])
    vehicle_model_year: int = Field(..., description="Manufacture/model year (e.g. 2019)", examples=[2019])
    vehicle_condition: str = Field(default="used", description="'used' or 'new'", examples=["used"])
    vehicle_tax_type: str = Field(
        default="plate number", description="'plate number', 'tax paper', 'imported'", examples=["plate number"]
    )
    vehicle_mileage_km: int | None = Field(default=None, description="Odometer reading in kilometers", examples=[65000])
    vehicle_transmission: str = Field(
        default="automatic", description="'automatic' or 'manual'", examples=["automatic"]
    )
    vehicle_fuel_type: str = Field(
        default="petrol", description="'petrol', 'diesel', 'hybrid', 'electric'", examples=["petrol"]
    )
    province: str = Field(
        default="phnom-penh",
        description="Location province slug (e.g. 'phnom-penh', 'siem-reap')",
        examples=["phnom-penh"],
    )

    @field_validator("vehicle_model_year")
    @classmethod
    def validate_year(cls, v: int) -> int:
        max_year = datetime.now(UTC).year + MAX_VEHICLE_YEAR_OFFSET
        if not (MIN_VEHICLE_YEAR <= v <= max_year):
            raise ValueError(f"vehicle_model_year must be between {MIN_VEHICLE_YEAR} and {max_year}, got {v}")
        return v

    @field_validator("vehicle_mileage_km")
    @classmethod
    def validate_mileage(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("vehicle_mileage_km cannot be negative")
        return v


class PredictionResponse(BaseModel):
    """
    Valuation output with price estimation and confidence bounds.
    """

    predicted_price_usd: float = Field(..., description="Estimated market price in USD")
    price_range_low_usd: float = Field(..., description="Lower 80% confidence bound in USD")
    price_range_high_usd: float = Field(..., description="Upper 80% confidence bound in USD")
    currency: str = Field(default="USD")
    market_sample_size: int = Field(..., description="Number of historical listings matching this slice")
    valuation_basis: str = Field(..., description="Model/market slice rationale used for estimation")
    estimated_age_years: int = Field(..., description="Calculated vehicle age from model year")


class MarketSummaryResponse(BaseModel):
    """
    Aggregated automotive market summary.
    """

    total_listings: int
    median_price_usd: float | None
    mean_price_usd: float | None
    min_price_usd: float | None
    max_price_usd: float | None
    top_brands: dict[str, Any]
    top_provinces: dict[str, int]
    freshness_days: float | None


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
