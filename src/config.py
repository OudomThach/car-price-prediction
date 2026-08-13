# src/config.py — Settings, API base URLs, and scraper constants
# Loads sensitive values from .env; all other values have safe defaults.

import os
from dotenv import load_dotenv

load_dotenv()  # Reads .env file from the project root

# ── API Base URLs ──────────────────────────────────────────────────────────────
CORE_API_BASE   = "https://api.khmer24.com"
POSTS_API_BASE  = "https://api-posts.khmer24.com"
IMAGES_CDN_BASE = "https://images.khmer24.co"

# ── Default HTTP Headers ───────────────────────────────────────────────────────
# Device-Id is read from .env so it can be rotated without code changes.
DEVICE_ID = os.getenv("KHMER24_DEVICE_ID", "ds-intern-device-f4b8c10a")

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Device-Id": DEVICE_ID,
    "display-type": "desktop",
    "Origin": "https://www.khmer24.com",
    "Referer": "https://www.khmer24.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
}

# ── Scraper Defaults ───────────────────────────────────────────────────────────
DEFAULT_LANG          = "en"
DEFAULT_PAGE_LIMIT    = 30       # Items returned per API page
DEFAULT_DELAY_SECONDS = 0.75     # Polite delay between requests (seconds)
DEFAULT_RETRIES       = 3        # Max HTTP retry attempts per request

# ── Storage Paths ──────────────────────────────────────────────────────────────
RAW_DATA_DIR       = os.path.join("data", "raw")
PROCESSED_DATA_DIR = os.path.join("data", "processed")

PARQUET_FILENAME   = "khmer24_cars.parquet"

# ── Scrape Target ──────────────────────────────────────────────────────────────
# Override via environment variables for CI/CD flexibility.
TARGET_CATEGORY = os.getenv("TARGET_CATEGORY", "cars-for-sale")
TARGET_PROVINCE = os.getenv("TARGET_PROVINCE") or None   # None = all provinces
MAX_PAGES       = int(os.getenv("MAX_PAGES", "20"))       # 30 items/page → up to 600 listings
