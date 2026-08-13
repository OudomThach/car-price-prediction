# src/parsers.py — JSON & title-parsing helpers for Khmer24 listing data

import re
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Known car brands (sorted longest-first to avoid partial matches) ───────────
_KNOWN_BRANDS: List[str] = sorted(
    [
        "Mercedes-Benz", "Mercedes", "Land Rover", "Rolls-Royce",
        "Aston Martin", "Alfa Romeo",
        "Toyota", "Honda", "Lexus", "BMW", "Hyundai", "Kia", "Mazda",
        "Nissan", "Mitsubishi", "Isuzu", "Suzuki", "Subaru", "Volkswagen",
        "Ford", "Chevrolet", "Jeep", "Dodge", "Cadillac", "Lincoln",
        "Audi", "Porsche", "Volvo", "Peugeot", "Renault", "Citroën",
        "Acura", "Infiniti", "Genesis", "Haval", "MG", "BYD", "Geely",
        "Chery", "JAC", "Foton", "DFSK", "Dongfeng", "BAIC",
    ],
    key=len,
    reverse=True,
)

# Year pattern — used to strip year digits leaking into model tokens
_YEAR_RE = re.compile(r'^(?:19|20)\d{2}$')

# Non-model stop words — stop collecting model tokens when any is hit
_STOP_WORDS = {
    "for", "sale", "used", "new", "good", "condition", "year",
    "km", "manual", "automatic", "auto", "diesel", "petrol",
    "electric", "hybrid", "turbo", "4wd", "awd", "4x4",
    "price", "cheap", "urgent", "negotiable",
}


def extract_brand_model(title: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract the car brand and model name from a listing title string.

    Strategy:
    1. Scan the title for a known brand name (case-insensitive).
    2. Collect up to 3 tokens after the brand as the model name.
    3. Strip tokens that look like a year (e.g. "2019") or stop words.

    Returns (brand, model) — either or both may be None.

    Examples:
        "Toyota Camry 2019 used"          → ("Toyota", "Camry")
        "ឡានToyota Land Cruiser 200"      → ("Toyota", "Land Cruiser 200")
        "Mercedes-Benz E300 2020 for sale" → ("Mercedes-Benz", "E300")
        "Honda Civic 2021 automatic"       → ("Honda", "Civic")
    """
    if not title:
        return None, None

    title_clean = title.strip()

    for brand in _KNOWN_BRANDS:
        pattern = re.compile(re.escape(brand), re.IGNORECASE)
        m = pattern.search(title_clean)
        if m:
            after = title_clean[m.end():].strip()
            tokens = after.split()
            model_tokens = []
            for tok in tokens[:4]:                         # scan up to 4 tokens
                if tok.lower() in _STOP_WORDS:             # stop at stop word
                    break
                if _YEAR_RE.match(tok):                    # skip year digits
                    continue
                model_tokens.append(tok)
                if len(model_tokens) == 3:                 # max 3 model words
                    break
            model = " ".join(model_tokens) if model_tokens else None
            return brand, model                            # canonical casing

    return None, None


def extract_spec_value(specs: Dict[str, Any], *keys: str) -> Optional[str]:
    """
    Return the first non-None value found in `specs` for any of the given keys.
    Normalizes the result to a stripped string.
    """
    for key in keys:
        val = specs.get(key)
        if val is not None:
            return str(val).strip() or None
    return None


def parse_mileage(raw: Any) -> Optional[int]:
    """
    Parse a mileage / odometer value to an integer (km).

    Handles formats like "150,000", "150000 km", "150K km".
    Returns None if unparseable.
    """
    if raw is None:
        return None
    s = str(raw).lower().replace(",", "").replace(" ", "")
    # Handle "150k" shorthand
    if s.endswith("k"):
        try:
            return int(float(s[:-1]) * 1000)
        except ValueError:
            return None
    # Strip trailing "km"
    s = re.sub(r"km$", "", s).strip()
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def flatten_feed_response(raw: Any) -> List[Dict[str, Any]]:
    """
    Safely extract the ``data`` list from a Khmer24 Posts API JSON response.
    Returns an empty list if the response is malformed.
    """
    if not isinstance(raw, dict):
        return []
    return raw.get("data", []) or []


def extract_nuxt_hydration_data(html_content: str) -> Optional[dict]:
    """
    Extract and parse window.__NUXT_DATA__ from a Khmer24 server-rendered page.
    Used as a fallback when the REST API is unavailable.
    """
    match = re.search(
        r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
        html_content,
        re.DOTALL,
    )
    if not match:
        match = re.search(
            r'window\.__NUXT_DATA__\s*=\s*(\[.*?\]);', html_content, re.DOTALL
        )
    if not match:
        logger.debug("No Nuxt hydration data found in page HTML.")
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        logger.warning(f"Failed to decode Nuxt hydration JSON: {exc}")
        return None
