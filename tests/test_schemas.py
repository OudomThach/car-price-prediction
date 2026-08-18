# tests/test_schemas.py — Schema tests guarding the canonical column set

from car_price_prediction.schemas import CLEAN_COLUMNS, ListingModel

CANONICAL_COLUMNS = [
    "listing_id",
    "listing_title",
    "price",
    "currency",
    "discount_price",
    "is_premium",
    "category",
    "category_slug",
    "category_id",
    "province",
    "province_slug",
    "province_id",
    "district",
    "location_full",
    "location_coordinates",
    "seller_id",
    "seller_name",
    "seller_type",
    "seller_username",
    "seller_avatar_url",
    "seller_is_verified",
    "seller_store_id",
    "seller_phones",
    "seller_telco",
    "view_count",
    "likes_count",
    "is_like",
    "is_saved",
    "posted_at",
    "renewed_at",
    "thumbnail_url",
    "image_urls",
    "listing_url",
    "listing_available",
    "listing_status",
    "description",
    "sale_price",
    "original_price",
    "amount_saved",
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
    "detail_specs",
    "raw_feed_payload",
    "raw_detail_payload",
    "scraped_at",
]


class TestListingModelSchema:
    def test_model_dump_columns_match_canonical_set(self):
        listing = ListingModel(listing_id="1", listing_title="Toyota Camry")
        assert list(listing.model_dump().keys()) == CANONICAL_COLUMNS

    def test_seller_phones_defaults_to_empty_list(self):
        listing = ListingModel(listing_id="1", listing_title="Toyota Camry")
        assert listing.seller_phones == []

    def test_price_validator_strips_currency_symbols(self):
        listing = ListingModel(listing_id="1", listing_title="Honda Civic", price="$12,500")
        assert listing.price == 12500.0

    def test_price_validator_rejects_zero(self):
        listing = ListingModel(listing_id="1", listing_title="Honda Civic", price="0")
        assert listing.price is None

    def test_model_year_validator_rejects_implausible(self):
        listing = ListingModel(listing_id="1", listing_title="Old car", vehicle_model_year=1975)
        assert listing.vehicle_model_year is None

    def test_model_year_validator_coerces_strings(self):
        listing = ListingModel(listing_id="1", listing_title="New car", vehicle_model_year="2024")
        assert listing.vehicle_model_year == 2024

    def test_vehicle_mileage_validator_handles_comma_separated(self):
        listing = ListingModel(listing_id="1", listing_title="Toyota Camry", vehicle_mileage_km="150,000")
        assert listing.vehicle_mileage_km == 150000

    def test_bool_validator_coerces_api_values(self):
        listing = ListingModel(
            listing_id="1",
            listing_title="Car",
            seller_is_verified="1",
            is_like=0,
            is_saved="true",
            listing_available=True,
        )
        assert listing.seller_is_verified is True
        assert listing.is_like is False
        assert listing.is_saved is True
        assert listing.listing_available is True

    def test_discount_prices_reuse_price_cleaner(self):
        listing = ListingModel(
            listing_id="1",
            listing_title="Car",
            sale_price="$11,500",
            original_price="11500.00",
            amount_saved=700,
        )
        assert listing.sale_price == 11500.0
        assert listing.original_price == 11500.0
        assert listing.amount_saved == 700.0

    def test_raw_receipts_accept_dicts(self):
        listing = ListingModel(listing_id="1", listing_title="Car", raw_feed_payload={"listing_id": 1})
        assert listing.raw_feed_payload == {"listing_id": 1}


class TestTimestampNormalization:
    """posted_at / renewed_at must normalize to ISO-8601 UTC strings."""

    def test_naive_timestamp_assumes_cambodia_local_time(self):
        listing = ListingModel(listing_id="1", listing_title="Car", posted_at="2026-08-13 16:39:12")
        assert listing.posted_at == "2026-08-13T09:39:12+00:00"

    def test_aware_timestamp_converted_to_utc(self):
        listing = ListingModel(listing_id="1", listing_title="Car", renewed_at="2026-08-13T10:00:00+02:00")
        assert listing.renewed_at == "2026-08-13T08:00:00+00:00"

    def test_iso_string_with_z_suffix(self):
        listing = ListingModel(listing_id="1", listing_title="Car", posted_at="2026-08-13T09:39:12Z")
        assert listing.posted_at == "2026-08-13T09:39:12+00:00"

    def test_none_and_empty_stay_none(self):
        listing = ListingModel(listing_id="1", listing_title="Car", posted_at="", renewed_at=None)
        assert listing.posted_at is None
        assert listing.renewed_at is None


class TestCleanColumnsContract:
    """The processed dataset must match the repo-equivalent 34 columns."""

    REPO_EQUIVALENT = [
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
    ]

    def test_clean_columns_match_repo_equivalent_34(self):
        assert list(CLEAN_COLUMNS) == self.REPO_EQUIVALENT

    def test_clean_columns_are_subset_of_schema(self):
        assert all(col in CANONICAL_COLUMNS for col in CLEAN_COLUMNS)

    def test_extra_raw_columns_stay_out_of_processed(self):
        raw_only = [
            "category_id",
            "province_id",
            "location_coordinates",
            "seller_avatar_url",
            "seller_is_verified",
            "seller_store_id",
            "seller_telco",
            "image_urls",
            "likes_count",
            "is_like",
            "is_saved",
            "listing_available",
            "listing_status",
            "description",
            "sale_price",
            "original_price",
            "amount_saved",
            "detail_specs",
            "raw_feed_payload",
            "raw_detail_payload",
        ]
        assert all(col not in CLEAN_COLUMNS for col in raw_only)
