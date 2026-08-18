# tests/test_parsers.py — Unit tests for src/parsers.py

import json

from car_price_prediction.parsers import (
    decode_nuxt_payload,
    derive_telco,
    extract_brand_model,
    extract_detail_post,
    map_detail_specs,
    parse_mileage,
)


class TestExtractBrandModel:
    """Tests for brand/model extraction from listing titles."""

    def test_basic_brand_and_model(self):
        brand, model = extract_brand_model("Toyota Camry used good condition")
        assert brand == "Toyota"
        assert model == "Camry"

    def test_year_not_leaked_into_model(self):
        """Fix #2: year digits must NOT appear in the model field."""
        brand, model = extract_brand_model("Toyota Camry 2019 used")
        assert brand == "Toyota"
        assert model == "Camry"  # NOT "Camry 2019"

    def test_year_only_title(self):
        brand, model = extract_brand_model("Honda 2021 for sale")
        assert brand == "Honda"
        assert model is None  # no model word after year

    def test_khmer_prefix(self):
        """Khmer Unicode characters before the brand should not break parsing."""
        brand, model = extract_brand_model("ឡានHonda Civic 2021")
        assert brand == "Honda"
        assert model == "Civic"

    def test_multi_word_brand(self):
        brand, model = extract_brand_model("Mercedes-Benz E300 2020 for sale")
        assert brand == "Mercedes-Benz"
        assert model == "E300"

    def test_land_rover(self):
        brand, model = extract_brand_model("Land Rover Defender 2022")
        assert brand == "Land Rover"
        assert model == "Defender"

    def test_stop_word_halts_model(self):
        brand, model = extract_brand_model("Kia for sale cheap")
        assert brand == "Kia"
        assert model is None

    def test_keyword_stop_word(self):
        brand, model = extract_brand_model("Mazda automatic 2020")
        assert brand == "Mazda"
        assert model is None  # "automatic" is a stop word

    def test_unknown_brand(self):
        brand, model = extract_brand_model("Car for sale good condition")
        assert brand is None
        assert model is None

    def test_empty_title(self):
        brand, model = extract_brand_model("")
        assert brand is None
        assert model is None

    def test_none_title(self):
        brand, model = extract_brand_model(None)
        assert brand is None
        assert model is None

    def test_case_insensitive(self):
        brand, model = extract_brand_model("TOYOTA CAMRY 2020")
        assert brand == "Toyota"  # canonical casing preserved
        assert model == "CAMRY"

    def test_multi_word_model(self):
        brand, model = extract_brand_model("Toyota Land Cruiser 2022 used")
        assert brand == "Toyota"
        assert model == "Land Cruiser"

    def test_chinese_brand(self):
        brand, model = extract_brand_model("BYD Atto 3 2023")
        assert brand == "BYD"
        assert model == "Atto 3"

    def test_unbranded_corolla_cross(self):
        """Unbranded model titles (e.g. '2024 COROLLA CROSS HEV') infer brand."""
        brand, model = extract_brand_model("2024 COROLLA CROSS HEV")
        assert brand == "Toyota"
        assert model == "Corolla Cross"

    def test_unbranded_prius(self):
        brand, model = extract_brand_model("Prius 2010 Full Option")
        assert brand == "Toyota"
        assert model == "Prius"

    def test_unbranded_rx350(self):
        brand, model = extract_brand_model("2018 RX350 Luxury")
        assert brand == "Lexus"
        assert model == "RX350"

    def test_unbranded_highlander(self):
        brand, model = extract_brand_model("Highlander 2021 Limited")
        assert brand == "Toyota"
        assert model == "Highlander"

    def test_unbranded_morning(self):
        brand, model = extract_brand_model("Kia Morning 2015" if False else "Morning 2015 for sale")
        assert brand == "Kia"
        assert model == "Morning"


class TestParseMileage:
    """Tests for mileage string parsing."""

    def test_plain_integer(self):
        assert parse_mileage("150000") == 150000

    def test_comma_separated(self):
        assert parse_mileage("150,000") == 150000

    def test_with_km_suffix(self):
        assert parse_mileage("150000 km") == 150000

    def test_k_shorthand(self):
        assert parse_mileage("150k") == 150000

    def test_k_shorthand_decimal(self):
        assert parse_mileage("85.5k") == 85500

    def test_none_input(self):
        assert parse_mileage(None) is None

    def test_unparseable_string(self):
        assert parse_mileage("unknown") is None

    def test_integer_input(self):
        assert parse_mileage(80000) == 80000


class TestDeriveTelco:
    """Tests for Cambodia phone-carrier detection."""

    def test_cellcard_prefix(self):
        assert derive_telco(["012998785"]) == "cellcard"

    def test_smart_prefix(self):
        assert derive_telco(["0964494536"]) == "smart"

    def test_metfone_prefix(self):
        assert derive_telco(["0881234567"]) == "metfone"

    def test_uses_first_phone(self):
        assert derive_telco(["012000000", "096111111"]) == "cellcard"

    def test_strips_spaces_and_dashes(self):
        assert derive_telco(["012 998 785"]) == "cellcard"

    def test_strips_cambodia_country_code(self):
        assert derive_telco(["+855 12 998785"]) == "cellcard"

    def test_empty_list_returns_none(self):
        assert derive_telco([]) is None

    def test_unknown_prefix_returns_none(self):
        assert derive_telco(["011000000"]) is None


class TestDecodeNuxtPayload:
    """Tests for the Nuxt 3 devalue payload resolver."""

    def test_resolves_references(self):
        payload = [
            ["ShallowReactive", 1],
            {"title": 2, "price": 3},
            "Kia Carnival",
            "44800.00",
        ]
        assert decode_nuxt_payload(payload) == [
            ["ShallowReactive", {"title": "Kia Carnival", "price": "44800.00"}],
            {"title": "Kia Carnival", "price": "44800.00"},
            "Kia Carnival",
            "44800.00",
        ]

    def test_inline_literals_kept(self):
        payload = [{"nested": 1}, {"value": 2021}]
        # 1 is in range and points at a dict entry -> resolved reference
        assert decode_nuxt_payload(payload) == [{"nested": {"value": 2021}}, {"value": 2021}]

    def test_out_of_range_int_is_literal(self):
        payload = [{"price": 10800}]
        assert decode_nuxt_payload(payload) == [{"price": 10800}]

    def test_ref_to_int_entry_follows(self):
        """Deduplicated numbers are table entries — refs point at int entries."""
        payload = [{"year": 1}, 2024]
        assert decode_nuxt_payload(payload) == [{"year": 2024}, 2024]

    def test_cycle_does_not_recurse_forever(self):
        payload = [{"self": 0}]
        assert decode_nuxt_payload(payload) == [{"self": {"self": "<cycle>"}}]

    def test_shared_references_memoized(self):
        payload = [{"a": 1, "b": 1}, "shared-value"]
        assert decode_nuxt_payload(payload) == [
            {"a": "shared-value", "b": "shared-value"},
            "shared-value",
        ]


class TestExtractDetailPost:
    """Tests for detail-page payload extraction."""

    def test_extracts_post_from_html(self):
        payload = json.dumps(
            [
                ["ShallowReactive", 1],
                {"data": 2},
                {"id": 3, "title": 4, "price": 5, "specs": 6},
                "13878918",
                "Kia",
                "44800.00",
                [],
            ]
        )
        html = (
            '<html><script type="application/json" data-nuxt-data="nuxt-app" '
            f'data-ssr="true" id="__NUXT_DATA__">{payload}</script></html>'
        )
        post = extract_detail_post(html)
        assert post is not None
        assert post["id"] == "13878918"
        assert post["price"] == "44800.00"

    def test_missing_payload_returns_none(self):
        assert extract_detail_post("<html><body>no data</body></html>") is None


class TestMapDetailSpecs:
    """Tests for specs[] -> vehicle_* column mapping."""

    def test_maps_khmer_titles_and_field_slugs(self):
        specs = [
            {"title": "ម៉ាក", "field": "brand", "value": "Jeep", "display_value": "Jeep", "value_slug": "jeep"},
            {
                "title": "ប្រអប់លេខ",
                "field": "transmission",
                "value": "ស្វ័យប្រវត្តិ",
                "display_value": "Automatic",
                "value_slug": "automatic",
            },
            {"title": "ពណ៌", "field": "color", "value": "ពណ៍ខ្មៅ", "display_value": "Black", "value_slug": "black"},
        ]
        mapped = map_detail_specs(specs)
        assert mapped == {
            "vehicle_brand": "Jeep",
            "vehicle_transmission": "Automatic",
            "vehicle_color": "Black",
        }

    def test_prefers_display_value(self):
        specs = [{"title": "ឆ្នាំ", "field": "car-year", "value": 2024, "display_value": "2024", "value_slug": "2024"}]
        assert map_detail_specs(specs)["vehicle_model_year"] == 2024

    def test_unparseable_int_spec_skipped(self):
        specs = [{"title": "ឆ្នាំ", "field": "car-year", "value": "ក", "display_value": "ក", "value_slug": "ក"}]
        assert map_detail_specs(specs) == {}

    def test_unknown_specs_ignored(self):
        assert map_detail_specs([{"title": "ប្រភេទមេ", "field": "type", "value": "រថយន្ត និង យានយន្ត"}]) == {}
