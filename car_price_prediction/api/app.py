# car_price_prediction/api/app.py — Production FastAPI application

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from car_price_prediction.api.schemas import (
    HealthResponse,
    MarketSummaryResponse,
    PredictionRequest,
    PredictionResponse,
)
from car_price_prediction.services.valuation import (
    MarketAnalyticsService,
    ValuationService,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Cambodia Car Price Prediction API",
    description=(
        "Production REST API for real-time Cambodia car valuation, market intelligence, "
        "and dataset analytics powered by Khmer24 automotive data."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Enable CORS for local testing, frontend clients, and Swagger/Postman
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_valuation_service() -> ValuationService:
    """Dependency injection provider for ValuationService."""
    return ValuationService()


def get_market_service() -> MarketAnalyticsService:
    """Dependency injection provider for MarketAnalyticsService."""
    return MarketAnalyticsService()


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health & Liveness Probe",
    status_code=status.HTTP_200_OK,
)
def health_check() -> HealthResponse:
    """Liveness probe for Docker, Kubernetes, and monitoring healthchecks."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(UTC).isoformat(),
        version="0.1.0",
    )


@app.post(
    "/api/v1/predict",
    response_model=PredictionResponse,
    tags=["Valuation"],
    summary="Real-Time Car Price Valuation",
    status_code=status.HTTP_200_OK,
)
def predict_price(
    request: PredictionRequest,
    valuation_service: Annotated[ValuationService, Depends(get_valuation_service)],
) -> PredictionResponse:
    """
    Estimate the market price of a vehicle in Cambodia based on historical listings,
    model year, condition, tax type, and mileage.
    """
    result = valuation_service.estimate_price(
        vehicle_brand=request.vehicle_brand,
        vehicle_model=request.vehicle_model,
        vehicle_model_year=request.vehicle_model_year,
        vehicle_condition=request.vehicle_condition,
        vehicle_tax_type=request.vehicle_tax_type,
        vehicle_mileage_km=request.vehicle_mileage_km,
        vehicle_transmission=request.vehicle_transmission,
        vehicle_fuel_type=request.vehicle_fuel_type,
        province=request.province,
    )
    return PredictionResponse(**result)


@app.get(
    "/api/v1/market/summary",
    response_model=MarketSummaryResponse,
    tags=["Market Analytics"],
    summary="Automotive Market Summary",
    status_code=status.HTTP_200_OK,
)
def market_summary(
    market_service: Annotated[MarketAnalyticsService, Depends(get_market_service)],
) -> MarketSummaryResponse:
    """
    Retrieve aggregated metrics, median prices, top brands, and data freshness
    from the processed Lakehouse layer.
    """
    summary = market_service.get_market_summary()
    return MarketSummaryResponse(**summary)
