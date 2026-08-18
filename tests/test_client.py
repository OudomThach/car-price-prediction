# tests/test_client.py — Tests for Khmer24Client._parse_listing

import json

from car_price_prediction.client import Khmer24Client


def _detail_html() -> str:
    payload = json.dumps(
        [
            ["ShallowReactive", 1],
            {"data": 2},
            {
                "id": 3,
                "title": 4,
                "price": 5,
                "description": 6,
                "total_like": 7,
                "is_like": 8,
                "is_saved": 9,
                "specs": 10,
                "discount": 11,
            },
            "13866254",
            "Prius 2009",
            "10800.00",
            "One owner",
            "12",
            "1",
            "0",
            [
                {"title": 12, "field": 13, "value": 14, "display_value": 15, "value_slug": 16},
                {"title": 17, "field": 18, "value": 19, "display_value": 20, "value_slug": 21},
            ],
            {"sale_price": 22, "original_price": 23, "amount_saved": 24},
            "ម៉ាក",
            "brand",
            "Toyota",
            "Toyota",
            "toyota",
            "ប្រអប់លេខ",
            "transmission",
            "ស្វ័យប្រវត្តិ",
            "Automatic",
            "automatic",
            "11500.00",
            "11500.00",
            "700.00",
        ]
    )
    return (
        '<html><script type="application/json" data-nuxt-data="nuxt-app" '
        f'data-ssr="true" id="__NUXT_DATA__">{payload}</script></html>'
    )


class TestParseListing:
    def test_parse_full_listing(self, sample_api_listing):
        client = Khmer24Client()
        listing = client._parse_listing(sample_api_listing)

        assert listing is not None
        assert listing.listing_id == "13784836"
        assert listing.listing_title == "2024 COROLLA CROSS HEV"
        assert listing.price == 40900.0
        assert listing.category == "Cars for Sale"
        assert listing.category_slug == "cars-for-sale"
        assert listing.category_id == "67"
        assert listing.province == "Phnom Penh"
        assert listing.province_slug == "phnom-penh"
        assert listing.province_id == "32"
        assert listing.district == "Ruessei Kaev"
        assert listing.location_full == "Tuol Sangkae 1, Ruessei Kaev, Phnom Penh"
        assert listing.location_coordinates == {"x": "11.56245", "y": "104.91601", "z": 15}
        assert listing.seller_id == "519591"
        assert listing.seller_type == "store"
        assert listing.seller_username == "TangMengSrunAuto"
        assert listing.seller_avatar_url == "https://images.khmer24.co/store/avatar.jpg"
        assert listing.seller_is_verified is True
        assert listing.seller_store_id == "88321"
        assert listing.seller_phones == ["012998785", "098729999"]
        assert listing.seller_telco == "cellcard"  # 012 prefix
        assert listing.image_urls == [
            "https://images.khmer24.co/26-08-12/car-b.jpg",
            "https://images.khmer24.co/26-08-12/car-c.jpg",
        ]
        assert listing.listing_available is True
        assert listing.listing_status == "active"
        assert listing.raw_feed_payload["id"] == 13784836  # verbatim receipt
        assert listing.vehicle_model_year == 2024
        assert listing.vehicle_tax_type == "Plate Number"
        assert listing.posted_at == "2026-07-18T13:58:52+00:00"  # 20:58:52 +07:00 → UTC
        assert listing.raw_specs == {"car-year": 2024, "tax-type": "Plate Number"}

    def test_parse_missing_specs_yields_none_fields(self, sample_api_listing):
        """Mileage/fuel/transmission are absent from the API payload — stay None."""
        client = Khmer24Client()
        listing = client._parse_listing(sample_api_listing)

        assert listing.vehicle_mileage_km is None
        assert listing.vehicle_fuel_type is None
        assert listing.vehicle_transmission is None
        assert listing.vehicle_engine_cc is None
        assert listing.vehicle_color is None

    def test_parse_missing_id_returns_none(self, sample_api_listing):
        client = Khmer24Client()
        bad = dict(sample_api_listing)
        del bad["id"]
        assert client._parse_listing(bad) is None

    def test_parse_title_infers_brand_from_known_model(self, sample_api_listing):
        """COROLLA CROSS title without explicit Toyota keyword correctly infers Toyota."""
        client = Khmer24Client()
        listing = client._parse_listing(sample_api_listing)
        assert listing is not None
        assert listing.vehicle_brand == "Toyota"
        assert listing.vehicle_model == "Corolla Cross"

    def test_parse_title_truly_unknown_brand_yields_none(self, sample_api_listing):
        """Generic titles with no brand or model yield None."""
        client = Khmer24Client()
        data = dict(sample_api_listing)
        data["title"] = "Urgent car for sale good condition"
        listing = client._parse_listing(data)
        assert listing is not None
        assert listing.vehicle_brand is None
        assert listing.vehicle_model is None

    def test_missing_optional_fields_yield_defaults(self, sample_api_listing):
        """Absent photos/avatar/ids still parse — defaults apply."""
        client = Khmer24Client()
        bad = dict(sample_api_listing)
        del bad["photos"]
        del bad["category"]
        del bad["location"]
        bad["user"] = {"listing_id": 1, "name": "X", "user_type": "1"}
        listing = client._parse_listing(bad)
        assert listing is not None
        assert listing.image_urls == []
        assert listing.seller_avatar_url is None
        assert listing.category_id is None
        assert listing.province_id is None

    def test_image_object_fields_normalized_to_url(self, sample_api_listing):
        """Live API sometimes returns {url,width,height} objects for images."""
        client = Khmer24Client()
        obj = dict(sample_api_listing)
        obj["user"] = {
            **obj["user"],
            "photo": {"url": "https://images.khmer24.co/avatar.jpg", "width": 200, "height": 200},
        }
        obj["photos"] = [
            {"url": "https://images.khmer24.co/26-08-12/car-b.jpg", "width": 200},
            "https://images.khmer24.co/26-08-12/car-c.jpg",
        ]
        listing = client._parse_listing(obj)
        assert listing.seller_avatar_url == "https://images.khmer24.co/avatar.jpg"
        assert listing.image_urls == [
            "https://images.khmer24.co/26-08-12/car-b.jpg",
            "https://images.khmer24.co/26-08-12/car-c.jpg",
        ]


class TestFetchListingDetail:
    """Tests for detail-page enrichment (HTML mocked)."""

    def test_maps_detail_page_to_columns(self, monkeypatch):
        client = Khmer24Client()
        monkeypatch.setattr(client, "_get_html", lambda url: _detail_html())
        row = client.fetch_listing_detail("13866254", delay=0)
        assert row is not None
        assert row["description"] == "One owner"
        assert row["likes_count"] == 12
        assert row["is_like"] == 1
        assert row["is_saved"] == 0
        assert row["sale_price"] == 11500.0
        assert row["original_price"] == 11500.0
        assert row["amount_saved"] == 700.0
        assert row["vehicle_brand"] == "Toyota"
        assert row["vehicle_transmission"] == "Automatic"
        assert row["detail_specs"]["brand"] == "Toyota"
        assert row["raw_detail_payload"]["id"] == "13866254"

    def test_unfetchable_page_returns_none(self, monkeypatch):
        client = Khmer24Client()
        monkeypatch.setattr(client, "_get_html", lambda url: None)
        assert client.fetch_listing_detail("999999", delay=0) is None
