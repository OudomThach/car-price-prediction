# car_price_prediction/parsers.py — JSON & title-parsing helpers for Khmer24 listing data

import json
import re
from typing import Any

# ── Known car brands (sorted longest-first to avoid partial matches) ───────────
_KNOWN_BRANDS: list[str] = sorted(
    [
        "Mercedes-Benz",
        "Mercedes",
        "Land Rover",
        "Rolls-Royce",
        "Aston Martin",
        "Alfa Romeo",
        "Toyota",
        "Honda",
        "Lexus",
        "BMW",
        "Hyundai",
        "Kia",
        "Mazda",
        "Nissan",
        "Mitsubishi",
        "Isuzu",
        "Suzuki",
        "Subaru",
        "Volkswagen",
        "Ford",
        "Chevrolet",
        "Jeep",
        "Dodge",
        "Cadillac",
        "Lincoln",
        "Audi",
        "Porsche",
        "Volvo",
        "Peugeot",
        "Renault",
        "Citroën",
        "Acura",
        "Infiniti",
        "Genesis",
        "Haval",
        "MG",
        "BYD",
        "Geely",
        "Chery",
        "JAC",
        "Foton",
        "DFSK",
        "Dongfeng",
        "BAIC",
    ],
    key=len,
    reverse=True,
)

# ── Inverted model-to-brand lookup (resolves unbranded titles like "2024 COROLLA CROSS") ──
_MODEL_TO_BRAND: dict[str, str] = {
    # Toyota
    "Corolla Cross": "Toyota",
    "Land Cruiser": "Toyota",
    "Hilux Revo": "Toyota",
    "Corolla": "Toyota",
    "Camry": "Toyota",
    "Prius": "Toyota",
    "RAV4": "Toyota",
    "Highlander": "Toyota",
    "Tacoma": "Toyota",
    "Tundra": "Toyota",
    "Hilux": "Toyota",
    "Fortuner": "Toyota",
    "Alphard": "Toyota",
    "Vellfire": "Toyota",
    "Yaris": "Toyota",
    "Vitz": "Toyota",
    "Sienna": "Toyota",
    "4Runner": "Toyota",
    "Avanza": "Toyota",
    "Raize": "Toyota",
    "Rush": "Toyota",
    "Crown": "Toyota",
    "Revo": "Toyota",
    "Vios": "Toyota",
    "HiAce": "Toyota",
    "Aqua": "Toyota",
    # Lexus
    "RX300": "Lexus",
    "RX330": "Lexus",
    "RX350": "Lexus",
    "RX450h": "Lexus",
    "RX400h": "Lexus",
    "LX470": "Lexus",
    "LX570": "Lexus",
    "LX600": "Lexus",
    "GX460": "Lexus",
    "GX470": "Lexus",
    "NX200t": "Lexus",
    "NX300": "Lexus",
    "ES300": "Lexus",
    "ES350": "Lexus",
    "ES300h": "Lexus",
    "IS250": "Lexus",
    "IS300": "Lexus",
    "IS350": "Lexus",
    "GS300": "Lexus",
    "GS350": "Lexus",
    "CT200h": "Lexus",
    # Honda
    "CR-V": "Honda",
    "CRV": "Honda",
    "Civic": "Honda",
    "City": "Honda",
    "HR-V": "Honda",
    "HRV": "Honda",
    "Accord": "Honda",
    "Fit": "Honda",
    "Odyssey": "Honda",
    "Insight": "Honda",
    "Jazz": "Honda",
    # Ford
    "Ranger Raptor": "Ford",
    "Ranger Wildtrak": "Ford",
    "Ranger": "Ford",
    "Raptor": "Ford",
    "Everest": "Ford",
    "F-150": "Ford",
    "F150": "Ford",
    "Explorer": "Ford",
    "Mustang": "Ford",
    "Territory": "Ford",
    "Transit": "Ford",
    "EcoSport": "Ford",
    # Hyundai
    "Santa Fe": "Hyundai",
    "Grand Starex": "Hyundai",
    "Starex": "Hyundai",
    "H-1": "Hyundai",
    "H1": "Hyundai",
    "Tucson": "Hyundai",
    "Palisade": "Hyundai",
    "Elantra": "Hyundai",
    "Creta": "Hyundai",
    "Staria": "Hyundai",
    "Accent": "Hyundai",
    "Custin": "Hyundai",
    "Venue": "Hyundai",
    "Kona": "Hyundai",
    "Ioniq": "Hyundai",
    # Kia
    "Morning": "Kia",
    "Carnival": "Kia",
    "Grand Carnival": "Kia",
    "Sorento": "Kia",
    "Sportage": "Kia",
    "K5": "Kia",
    "K3": "Kia",
    "Picanto": "Kia",
    "Sonet": "Kia",
    "Seltos": "Kia",
    "Ray": "Kia",
    "Stinger": "Kia",
    # Mazda
    "Mazda 2": "Mazda",
    "Mazda 3": "Mazda",
    "Mazda 6": "Mazda",
    "Mazda2": "Mazda",
    "Mazda3": "Mazda",
    "Mazda6": "Mazda",
    "CX-3": "Mazda",
    "CX-30": "Mazda",
    "CX-5": "Mazda",
    "CX-8": "Mazda",
    "CX-9": "Mazda",
    "CX-60": "Mazda",
    "CX-90": "Mazda",
    "BT-50": "Mazda",
    # Land Rover
    "Range Rover Sport": "Land Rover",
    "Range Rover Vogue": "Land Rover",
    "Range Rover Evoque": "Land Rover",
    "Range Rover Velar": "Land Rover",
    "Range Rover": "Land Rover",
    "Defender": "Land Rover",
    "Discovery Sport": "Land Rover",
    "Discovery": "Land Rover",
    "Evoque": "Land Rover",
    "Velar": "Land Rover",
    # Nissan
    "Navara": "Nissan",
    "Patrol": "Nissan",
    "X-Trail": "Nissan",
    "Xtrail": "Nissan",
    "Kicks": "Nissan",
    "Terra": "Nissan",
    "Juke": "Nissan",
    "March": "Nissan",
    "Sunny": "Nissan",
    "Urvan": "Nissan",
    "Leaf": "Nissan",
    # Mitsubishi
    "Pajero Sport": "Mitsubishi",
    "Pajero": "Mitsubishi",
    "Triton": "Mitsubishi",
    "Xpander": "Mitsubishi",
    "Outlander": "Mitsubishi",
    "Attrage": "Mitsubishi",
    "Mirage": "Mitsubishi",
    "Eclipse Cross": "Mitsubishi",
    # BMW
    "X1": "BMW",
    "X3": "BMW",
    "X4": "BMW",
    "X5": "BMW",
    "X6": "BMW",
    "X7": "BMW",
    "i3": "BMW",
    "i4": "BMW",
    "i7": "BMW",
    "iX3": "BMW",
    # Mercedes-Benz
    "G63 AMG": "Mercedes-Benz",
    "G63": "Mercedes-Benz",
    "G500": "Mercedes-Benz",
    "C200": "Mercedes-Benz",
    "C300": "Mercedes-Benz",
    "C250": "Mercedes-Benz",
    "E200": "Mercedes-Benz",
    "E250": "Mercedes-Benz",
    "E300": "Mercedes-Benz",
    "E350": "Mercedes-Benz",
    "S400": "Mercedes-Benz",
    "S450": "Mercedes-Benz",
    "S500": "Mercedes-Benz",
    "S550": "Mercedes-Benz",
    "GLC200": "Mercedes-Benz",
    "GLC300": "Mercedes-Benz",
    "GLE450": "Mercedes-Benz",
    "GLS450": "Mercedes-Benz",
    "GLS500": "Mercedes-Benz",
    "GLS600": "Mercedes-Benz",
    "CLA250": "Mercedes-Benz",
    "GLA250": "Mercedes-Benz",
}

_KNOWN_MODELS_SORTED: list[str] = sorted(
    _MODEL_TO_BRAND.keys(),
    key=len,
    reverse=True,
)

# Year pattern — used to strip year digits leaking into model tokens
_YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")

# Non-model stop words — stop collecting model tokens when any is hit
_STOP_WORDS = {
    "for",
    "sale",
    "used",
    "new",
    "good",
    "condition",
    "year",
    "km",
    "manual",
    "automatic",
    "auto",
    "diesel",
    "petrol",
    "electric",
    "hybrid",
    "turbo",
    "4wd",
    "awd",
    "4x4",
    "price",
    "cheap",
    "urgent",
    "negotiable",
    "full",
    "option",
    "tax",
    "paper",
}


def extract_brand_model(title: str | None) -> tuple[str | None, str | None]:
    """
    Extract the car brand and model name from a listing title string.

    Strategy:
    1. Scan the title for a known brand name (case-insensitive).
       If found, collect up to 3 tokens after the brand as the model name.
    2. If no brand matched, scan for known car models (e.g. "COROLLA CROSS",
       "Prius", "RX350", "Morning") and infer the brand.
    3. Strip tokens that look like a year (e.g. "2019") or stop words.

    Returns (brand, model) — either or both may be None.

    Examples:
        "Toyota Camry 2019 used"          → ("Toyota", "Camry")
        "2024 COROLLA CROSS HEV"          → ("Toyota", "Corolla Cross")
        "Prius 2010 Full Option"          → ("Toyota", "Prius")
        "ឡានToyota Land Cruiser 200"      → ("Toyota", "Land Cruiser 200")
        "Mercedes-Benz E300 2020 for sale" → ("Mercedes-Benz", "E300")
        "Lexus RX350 2018"                → ("Lexus", "RX350")
    """
    if not title:
        return None, None

    title_clean = title.strip()

    # Step 1: Scan for explicit brand
    for brand in _KNOWN_BRANDS:
        pattern = re.compile(r"\b" + re.escape(brand) + r"\b|" + re.escape(brand), re.IGNORECASE)
        match = pattern.search(title_clean)
        if match:
            canonical_brand = "Mercedes-Benz" if brand == "Mercedes" else brand
            after = title_clean[match.end() :].strip()
            tokens = after.split()
            model_tokens = []
            for tok in tokens[:4]:  # scan up to 4 tokens
                if tok.lower() in _STOP_WORDS:  # stop at stop word
                    break
                if _YEAR_RE.match(tok):  # skip year digits
                    continue
                model_tokens.append(tok)
                if len(model_tokens) == 3:  # max 3 model words
                    break
            model = " ".join(model_tokens) if model_tokens else None
            return canonical_brand, model

    # Step 2: Scan for known model names when brand is omitted from title
    for model_name in _KNOWN_MODELS_SORTED:
        pattern = re.compile(r"\b" + re.escape(model_name) + r"\b", re.IGNORECASE)
        if pattern.search(title_clean):
            inferred_brand = _MODEL_TO_BRAND[model_name]
            return inferred_brand, model_name
    return None, None


def extract_spec_value(specs: dict[str, Any], *keys: str) -> str | None:
    """
    Return the first non-None value found in `specs` for any of the given keys.
    Normalizes the result to a stripped string.
    """
    for key in keys:
        val = specs.get(key)
        if val is not None:
            return str(val).strip() or None
    return None


def extract_image_url(value: Any) -> str | None:
    """
    Extract a URL string from a Khmer24 image field.

    Image fields appear either as plain URL strings or as objects like
    ``{"url": "...", "width": ..., "height": ...}``; both are normalized
    to the bare URL. Returns None for absent or unusable values.
    """
    if isinstance(value, dict):
        value = value.get("url")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def parse_mileage(raw: Any) -> int | None:
    """
    Parse a mileage / odometer value to an integer (km).

    Handles formats like "150,000", "150000 km", "150K km".
    Returns None if unparseable.
    """
    if raw is None:
        return None
    cleaned = str(raw).lower().replace(",", "").replace(" ", "")
    # Handle "150k" shorthand
    if cleaned.endswith("k"):
        try:
            return int(float(cleaned[:-1]) * 1000)
        except ValueError:
            return None
    # Strip trailing "km"
    cleaned = re.sub(r"km$", "", cleaned).strip()
    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None


# ── Phone carrier detection (Cambodia prefixes) ───────────────────────────────
_TELCO_PREFIXES: dict[str, tuple[str, ...]] = {
    "cellcard": ("012", "017", "077", "078", "089", "092", "095", "099"),
    "smart": ("010", "015", "016", "069", "070", "081", "086", "087", "093", "096", "098"),
    "metfone": ("088", "097", "071", "031"),
}
_CAMBODIA_COUNTRY_CODE = "855"


def derive_telco(phones: list[str]) -> str | None:
    """
    Return the carrier for the first phone number, or None when unknown.

    Cambodia prefix rules (per the Khmer24 playbook): 012/017/077/078/089/
    092/095/099 -> cellcard; 010/015/016/069/070/081/086/087/093/096/098 ->
    smart; 088/097/071/031 -> metfone. A leading "+855" country code is
    stripped before matching.
    """
    if not phones:
        return None
    digits = re.sub(r"\D", "", phones[0])
    if digits.startswith(_CAMBODIA_COUNTRY_CODE):
        # International format drops the leading zero ("+855 12..." -> "12...")
        digits = "0" + digits[len(_CAMBODIA_COUNTRY_CODE) :]
    for carrier, prefixes in _TELCO_PREFIXES.items():
        if digits.startswith(prefixes):
            return carrier
    return None


# ── Nuxt SSR payload decoding (detail pages) ─────────────────────────────────
# Khmer24 listing pages embed their data in a `__NUXT_DATA__` JSON script using
# Nuxt 3's devalue format: an index-referenced array where integers inside
# objects/lists point at other array entries. Numbers are deduplicated into the
# table as integer entries, so a reference resolves to its entry — and when the
# entry is itself an integer, that integer is the final literal value (never
# followed as another reference). Out-of-range integers are inline literals.

_NUXT_SCRIPT_RE = re.compile(
    r'<script[^>]*data-nuxt-data="nuxt-app"[^>]*id="__NUXT_DATA__">(.*?)</script>',
    re.DOTALL,
)
_MAX_DECODE_DEPTH = 60


def decode_nuxt_payload(payload: list[Any]) -> Any:
    """Resolve a Nuxt 3 ``__NUXT_DATA__`` devalue payload into plain data."""
    resolved: dict[int, Any] = {}

    def resolve(value: Any, depth: int = 0) -> Any:
        if depth > _MAX_DECODE_DEPTH:
            return None
        if isinstance(value, int) and 0 <= value < len(payload):
            target = payload[value]
            if isinstance(target, int):
                return target  # table entry holding a literal int
            if value in resolved:
                return resolved[value]  # memoized (cycle-safe)
            resolved[value] = "<cycle>"
            resolved[value] = resolve(target, depth + 1)
            return resolved[value]
        if isinstance(value, list):
            if value and isinstance(value[0], str):
                return [value[0]] + [resolve(x, depth + 1) for x in value[1:]]
            return [resolve(x, depth + 1) for x in value]
        if isinstance(value, dict):
            return {k: resolve(v, depth + 1) for k, v in value.items()}
        return value

    return resolve(payload)


def extract_detail_post(html: str) -> dict[str, Any] | None:
    """
    Extract the listing post object from a Khmer24 detail-page HTML string.

    Finds the ``__NUXT_DATA__`` payload, decodes it, and returns the post
    dict (the node carrying ``specs`` + ``title`` + ``price``). Returns None
    when the page has no usable payload.
    """
    match = _NUXT_SCRIPT_RE.search(html)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return _find_post(decode_nuxt_payload(payload))


def _find_post(obj: Any) -> dict[str, Any] | None:
    """Locate the post object (has specs/title/price) anywhere in the tree."""
    if isinstance(obj, dict):
        if "specs" in obj and "title" in obj and "price" in obj:
            return obj
        for value in obj.values():
            found = _find_post(value)
            if found:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _find_post(value)
            if found:
                return found
    return None


# ── Detail specs table → typed vehicle columns ───────────────────────────────
# The detail page's specs[] tuples carry a "field" slug (e.g. "car-year") and
# a Khmer title; both are mapped onto our vehicle_* columns. Values prefer the
# human-readable display_value, falling back to value / value_slug.

_SPEC_FIELD_MAP: dict[str, str] = {
    "car-year": "vehicle_model_year",
    "condition": "vehicle_condition",
    "tax-type": "vehicle_tax_type",
    "transmission": "vehicle_transmission",
    "color": "vehicle_color",
    "fuel": "vehicle_fuel_type",
    "engine-type": "vehicle_fuel_type",  # site's fuel-ish field ("electric", ...)
    "mileage": "vehicle_mileage_km",
    "odometer": "vehicle_mileage_km",
    "km": "vehicle_mileage_km",
    "brand": "vehicle_brand",
    "model": "vehicle_model",
}
_SPEC_TITLE_MAP: dict[str, str] = {
    "ម៉ាក": "vehicle_brand",
    "ម៉ូដែល": "vehicle_model",
    "ឆ្នាំ": "vehicle_model_year",
    "លក្ខខណ្ឌ": "vehicle_condition",
    "ប្រភេទពន្ធ": "vehicle_tax_type",
    "ប្រអប់លេខ": "vehicle_transmission",
    "ពណ៌": "vehicle_color",
    "ចម្ងាយ": "vehicle_mileage_km",
    "ម៉ាស៊ីន": "vehicle_fuel_type",
}


def map_detail_specs(specs: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Map a detail-page ``specs[]`` table onto our ``vehicle_*`` columns.

    Returns only the columns present in the table; absent specs are omitted
    so existing values are preserved during enrichment. Integer columns
    (year, mileage, engine) are coerced to ints; unparseable values are
    skipped.
    """
    mapped: dict[str, Any] = {}
    for spec in specs:
        column = _SPEC_FIELD_MAP.get(str(spec.get("field") or "")) or _SPEC_TITLE_MAP.get(str(spec.get("title") or ""))
        if column is None:
            continue
        value = spec.get("display_value")
        if value is None:
            value = spec.get("value")
        if value is None:
            value = spec.get("value_slug")
        if value is None:
            continue
        value = str(value).strip()
        if column == "vehicle_mileage_km":
            parsed = parse_mileage(value)
            if parsed is None:
                continue
            value = parsed
        elif column in ("vehicle_engine_cc", "vehicle_model_year"):
            digits = re.sub(r"\D", "", value)
            if not digits:
                continue
            value = int(digits)
        mapped[column] = value
    return mapped
