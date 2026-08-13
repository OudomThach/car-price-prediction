# tests/test_parsers.py — Unit tests for src/parsers.py

import pytest
from src.parsers import extract_brand_model, parse_mileage


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
        assert model == "Camry"          # NOT "Camry 2019"

    def test_year_only_title(self):
        brand, model = extract_brand_model("Honda 2021 for sale")
        assert brand == "Honda"
        assert model is None             # no model word after year

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
        assert model is None             # "automatic" is a stop word

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
        assert brand == "Toyota"         # canonical casing preserved
        assert model == "CAMRY"

    def test_multi_word_model(self):
        brand, model = extract_brand_model("Toyota Land Cruiser 2022 used")
        assert brand == "Toyota"
        assert model == "Land Cruiser"

    def test_chinese_brand(self):
        brand, model = extract_brand_model("BYD Atto 3 2023 new")
        assert brand == "BYD"
        assert model == "Atto 3"         # "Atto 3" is the full model name


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
