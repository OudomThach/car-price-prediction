# car_price_prediction/schemas.py — Pydantic v2 data-validation models for Khmer24 car listings

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator

from car_price_prediction.config import MAX_VEHICLE_YEAR_OFFSET, MIN_VEHICLE_YEAR, SOURCE_UTC_OFFSET_HOURS

# Khmer24 API timestamps are naive Cambodia local time (UTC+07:00, no DST).
_SOURCE_TZ = timezone(timedelta(hours=SOURCE_UTC_OFFSET_HOURS))


class ListingModel(BaseModel):
    """
    Validated record for a single Khmer24 car listing.

    All fields needed for downstream ML modeling are captured here.
    The `raw_specs` dict stores the raw highlight_specs payload so future
    feature engineering can extract additional structured fields without
    re-scraping.

    Timestamp convention: every ``*_at`` field is an ISO-8601 UTC string
    (naive API timestamps are interpreted as Cambodia local time, UTC+07:00).
    """

    listing_id: str
    listing_title: str
    price: float | None = None
    currency: str = "USD"
    discount_price: float | None = None  # never populated by the API (parity with repo)
    is_premium: bool | None = None

    # ── Category ──────────────────────────────────────────────────────────────
    category: str | None = None
    category_slug: str | None = None
    category_id: str | None = None  # API category id (numeric string)

    # ── Location ──────────────────────────────────────────────────────────────
    province: str | None = None
    province_slug: str | None = None
    province_id: str | None = None  # API province id (numeric string)
    district: str | None = None
    location_full: str | None = None
    location_coordinates: dict[str, Any] | None = None  # API map {x, y, z}

    # ── Seller ────────────────────────────────────────────────────────────────
    seller_id: str | None = None
    seller_name: str | None = None
    seller_type: str | None = None  # "individual" | "store"
    seller_username: str | None = None
    seller_avatar_url: str | None = None
    seller_is_verified: bool | None = None  # user.is_verify (trust signal)
    seller_store_id: str | None = None  # storeid (store-level account id)

    # ── Contact ───────────────────────────────────────────────────────────────
    seller_phones: list[str] = Field(default_factory=list)
    seller_telco: str | None = None  # "cellcard" | "smart" | "metfone" | None

    # ── Listing metadata ──────────────────────────────────────────────────────
    view_count: int = 0
    likes_count: int = 0  # total_like (detail page)
    is_like: bool | None = None
    is_saved: bool | None = None
    posted_at: str | None = None  # ISO-8601 UTC
    renewed_at: str | None = None  # ISO-8601 UTC
    thumbnail_url: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    listing_url: str | None = None
    listing_available: bool | None = None  # feed "available"
    listing_status: str | None = None  # feed "status" ("active", ...)
    description: str | None = None  # detail page
    sale_price: float | None = None  # detail discount object
    original_price: float | None = None  # detail discount object
    amount_saved: float | None = None  # detail discount object

    # ── Vehicle-specific fields (parsed from highlight_specs) ─────────────────
    vehicle_model_year: int | None = None  # model year (API field "car-year")
    vehicle_condition: str | None = None  # "used" | "new"
    vehicle_tax_type: str | None = None  # "imported" | "local" | ...
    vehicle_brand: str | None = None
    vehicle_model: str | None = None

    # ── Extra specs extracted from highlight_specs blob ───────────────────────
    vehicle_mileage_km: int | None = None  # odometer reading in km
    vehicle_fuel_type: str | None = None  # "petrol" | "diesel" | "electric" | ...
    vehicle_transmission: str | None = None  # "automatic" | "manual"
    vehicle_engine_cc: int | None = None  # engine displacement in cc
    vehicle_color: str | None = None  # exterior color

    # ── Raw specs dict — full API payload for future extension ────────────────
    raw_specs: dict[str, Any] | None = Field(default=None)

    # ── Raw receipts — verbatim payloads (zero-loss capture) ──────────────────
    detail_specs: dict[str, Any] | None = Field(default=None)  # detail specs[] table
    raw_feed_payload: dict[str, Any] | None = Field(default=None)  # full feed item JSON
    raw_detail_payload: dict[str, Any] | None = Field(default=None)  # full detail post JSON

    # ── Scrape timestamp ──────────────────────────────────────────────────────
    scraped_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("price", "discount_price", "sale_price", "original_price", "amount_saved", mode="before")
    @classmethod
    def clean_price(cls, v: Any) -> float | None:
        """Strip currency symbols and coerce to float; returns None for zero/empty."""
        if v is None or v == "" or v == "0.00":
            return None
        if isinstance(v, (int, float)):
            return float(v) if float(v) > 0 else None
        s = str(v).replace("$", "").replace(",", "").strip()
        try:
            val = float(s)
            return val if val > 0 else None
        except ValueError:
            return None

    @field_validator("seller_is_verified", "is_like", "is_saved", "listing_available", mode="before")
    @classmethod
    def coerce_bool(cls, v: Any) -> bool | None:
        """Coerce API boolean-ish values (1/0, "1"/"0", true/false) to bool."""
        if v is None or v == "":
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v != 0
        s = str(v).strip().lower()
        if s in ("1", "true", "yes", "y"):
            return True
        if s in ("0", "false", "no", "n"):
            return False
        return None

    @field_validator("vehicle_model_year", mode="before")
    @classmethod
    def clean_model_year(cls, v: Any) -> int | None:
        """Coerce model-year strings to int; reject implausible values."""
        if v is None:
            return None
        try:
            year = int(str(v).strip())
            max_year = datetime.now(UTC).year + MAX_VEHICLE_YEAR_OFFSET
            return year if MIN_VEHICLE_YEAR <= year <= max_year else None
        except (ValueError, TypeError):
            return None

    @field_validator("vehicle_mileage_km", "vehicle_engine_cc", mode="before")
    @classmethod
    def clean_int_spec(cls, v: Any) -> int | None:
        """Coerce integer spec values; return None on failure."""
        if v is None:
            return None
        try:
            return int(float(str(v).replace(",", "").strip()))
        except (ValueError, TypeError):
            return None

    @field_validator("posted_at", "renewed_at", mode="before")
    @classmethod
    def to_utc_iso(cls, v: Any) -> str | None:
        """
        Normalize timestamps to ISO-8601 UTC strings.

        Naive values (Khmer24 API format) are interpreted as Cambodia local
        time (UTC+07:00); timezone-aware values are converted to UTC.
        """
        if v is None or v == "":
            return None
        try:
            dt = v if isinstance(v, datetime) else datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_SOURCE_TZ)
            return dt.astimezone(UTC).isoformat()
        except (ValueError, TypeError):
            return None


# ── Data contract for the processed dataset ──────────────────────────────────
# Exactly equivalent to the original repo's 34 processed columns, renamed with
# our conventions. Everything else captured (receipts, GPS, verification,
# discount details, engagement, description) lives in the raw dataset only.
CLEAN_COLUMNS: tuple[str, ...] = (
    "listing_id",
    "listing_title",
    "price",
    "currency",
    "discount_price",
    "is_premium",
    "category",
    "category_slug",
    "province",
    "province_slug",
    "district",
    "location_full",
    "seller_id",
    "seller_name",
    "seller_type",
    "seller_username",
    "seller_phones",
    "view_count",
    "posted_at",
    "renewed_at",
    "thumbnail_url",
    "listing_url",
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
    "raw_specs",
    "scraped_at",
)
