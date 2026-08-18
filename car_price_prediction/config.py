# car_price_prediction/config.py — Settings, API base URLs, and scraper constants
# Loads sensitive values from .env; all other values have safe defaults.

import os
import uuid
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

load_dotenv()  # Reads .env file from the project root


def generate_device_id() -> str:
    """Generate a realistic web session device ID or return the configured env value."""
    return os.getenv("KHMER24_DEVICE_ID") or f"web-{uuid.uuid4().hex[:16]}"


# ── Project paths ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

RAW_DATA_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
LOG_DIR = BASE_DIR / "logs"

# ── Data filenames ────────────────────────────────────────────────────────────
RAW_PARQUET_FILENAME = "khmer24_cars.parquet"
CLEAN_PARQUET_FILENAME = "khmer24_cars_clean.parquet"
SAMPLE_CSV_TEMPLATE = "khmer24_cars_sample_{n}.csv"
CLEAN_SAMPLE_FILENAME = "khmer24_cars_clean_sample_60.csv"

RAW_PARQUET_PATH = RAW_DATA_DIR / RAW_PARQUET_FILENAME
CLEAN_PARQUET_PATH = PROCESSED_DATA_DIR / CLEAN_PARQUET_FILENAME
CLEAN_SAMPLE_PATH = PROCESSED_DATA_DIR / CLEAN_SAMPLE_FILENAME
LOG_FILE_PATH = LOG_DIR / "scraper.log"

# ── API Base URLs ─────────────────────────────────────────────────────────────
CORE_API_BASE = "https://api.khmer24.com"
POSTS_API_BASE = "https://api-posts.khmer24.com"

# ── Default HTTP Headers ──────────────────────────────────────────────────────
# Device-Id is generated uniquely per session or read from .env
DEVICE_ID = generate_device_id()

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,km;q=0.8",
    "Device-Id": DEVICE_ID,
    "display-type": "desktop",
    "Origin": "https://www.khmer24.com",
    "Referer": "https://www.khmer24.com/",
    "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
}

# ── Scraper Defaults ──────────────────────────────────────────────────────────
DEFAULT_LANG = "en"
DEFAULT_PAGE_LIMIT = 30  # Items returned per API page
DEFAULT_DELAY_SECONDS = 0.75  # Polite delay between requests (seconds)
DEFAULT_RETRIES = 3  # Max HTTP retry attempts per request
TLS_FINGERPRINT: Literal["chrome120", "chrome124", "chrome"] = "chrome120"  # curl_cffi impersonation target

# ── Scrape Target ─────────────────────────────────────────────────────────────
# Override via environment variables for CI/CD flexibility.
TARGET_CATEGORY = os.getenv("TARGET_CATEGORY", "cars-for-sale")
TARGET_PROVINCE = os.getenv("TARGET_PROVINCE") or None  # None = all provinces
MAX_PAGES = int(os.getenv("MAX_PAGES", "20"))  # 30 items/page → up to 600 listings

# ── Pipeline constants ─────────────────────────────────────────────────────────
RANDOM_SEED = 42  # Reproducible CSV sampling
SAMPLE_SIZES = (30, 60)  # Row counts for CSV samples
MAX_FRESHNESS_DAYS = 7  # Stale-data warning threshold for scrapes

# ── Data-quality thresholds (cleaning rules) ──────────────────────────────────
PRICE_MIN_USD = 500
PRICE_MAX_USD = 300_000
MIN_VEHICLE_YEAR = 1990  # Oldest plausible model year
MAX_VEHICLE_YEAR_OFFSET = 1  # Upper bound = current year + offset

# ── Timestamp conventions ─────────────────────────────────────────────────────
# Khmer24 API timestamps (posted_at / renewed_at) are naive Cambodia local
# time (UTC+07:00, no DST). Source timestamps are normalized to UTC on ingest.
SOURCE_UTC_OFFSET_HOURS = 7

# ── HTTP retry / rate-limit backoff ───────────────────────────────────────────
RETRY_BACKOFF_RATE_LIMITED_SECONDS = 5  # Base sleep on HTTP 429
RETRY_BACKOFF_TRANSIENT_SECONDS = 1.5  # Base sleep on other transient codes
RETRY_BACKOFF_ERROR_SECONDS = 2  # Base sleep on request exceptions
