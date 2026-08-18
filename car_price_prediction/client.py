# car_price_prediction/client.py — Robust HTTP client for the Khmer24 public APIs
# Uses curl_cffi to impersonate Chrome's TLS fingerprint,
# bypassing Cloudflare Bot Management without Playwright/Selenium.

import contextlib
import logging
import os
import random
import time
from typing import Any

from curl_cffi import requests as cf_requests

from car_price_prediction.config import (
    DEFAULT_DELAY_SECONDS,
    DEFAULT_HEADERS,
    DEFAULT_LANG,
    DEFAULT_PAGE_LIMIT,
    DEFAULT_RETRIES,
    POSTS_API_BASE,
    RETRY_BACKOFF_ERROR_SECONDS,
    RETRY_BACKOFF_RATE_LIMITED_SECONDS,
    RETRY_BACKOFF_TRANSIENT_SECONDS,
    TLS_FINGERPRINT,
    generate_device_id,
)
from car_price_prediction.parsers import (
    derive_telco,
    extract_brand_model,
    extract_detail_post,
    extract_image_url,
    extract_spec_value,
    map_detail_specs,
    parse_mileage,
)
from car_price_prediction.schemas import ListingModel

logger = logging.getLogger(__name__)


def _parse_retry_after(res: Any) -> float | None:
    """
    Parse the HTTP ``Retry-After`` header (seconds or HTTP-date) into a sleep.

    Returns None when the header is absent or unparseable, letting callers
    fall back to their own backoff schedule.
    """
    header = res.headers.get("Retry-After")
    if not header:
        return None
    try:
        return float(header)
    except (TypeError, ValueError):
        try:
            from datetime import UTC, datetime
            from email.utils import parsedate_to_datetime

            retry_at = parsedate_to_datetime(header)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
            return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


class Khmer24Client:
    """
    Synchronous HTTP client for the Khmer24 public APIs.

    Responsibilities:
    - Paginate the Posts API feed for the ``cars-for-sale`` category.
    - Parse each raw API item into a validated ``ListingModel``.
    - Handle rate-limiting (HTTP 429) & anti-bot blocks (HTTP 403) with exponential back-off and Device-Id rotation.
    - Extract brand & model from listing titles for ML feature use.

    Usage::

        with Khmer24Client() as client:
            listings = client.scrape_category_listings(
                category_slug="cars-for-sale",
                max_pages=20,
            )
    """

    def __init__(
        self,
        lang: str = DEFAULT_LANG,
        delay: float = DEFAULT_DELAY_SECONDS,
        proxy: str | None = None,
    ):
        self.lang = lang
        self.delay = delay
        self.proxy = proxy or os.getenv("KHMER24_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None

        self._session = cf_requests.Session(
            impersonate=TLS_FINGERPRINT, timeout=20, proxies=proxies  # type: ignore[arg-type]
        )
        self._session.headers.update(DEFAULT_HEADERS)

        # Browser-flavored session for HTML detail pages
        self._web_session = cf_requests.Session(
            impersonate=TLS_FINGERPRINT, timeout=20, proxies=proxies  # type: ignore[arg-type]
        )
        self._web_session.headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,km;q=0.8",
                "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
            }
        )

    # ── Internal HTTP helper ───────────────────────────────────────────────────

    def _get(
        self,
        url: str,
        params: dict[str, Any],
        retries: int = DEFAULT_RETRIES,
    ) -> Any | None:
        """
        Perform a GET request with exponential back-off on transient failures.

        Returns the ``curl_cffi`` response object on HTTP 200, or None if all
        retries are exhausted or a non-recoverable status code is received.
        """
        for attempt in range(1, retries + 1):
            try:
                res = self._session.get(url, params=params)
                if res.status_code == 200:
                    return res
                if res.status_code == 429:
                    wait = _parse_retry_after(res) or attempt * RETRY_BACKOFF_RATE_LIMITED_SECONDS
                    jitter = random.uniform(0.2, 0.6)
                    logger.warning(f"Rate-limited (429). Sleeping {wait + jitter:.1f}s… (attempt {attempt}/{retries})")
                    time.sleep(wait + jitter)
                elif res.status_code == 403:
                    new_device_id = generate_device_id()
                    self._session.headers["Device-Id"] = new_device_id
                    wait = attempt * RETRY_BACKOFF_RATE_LIMITED_SECONDS + random.uniform(0.3, 0.8)
                    logger.warning(
                        f"HTTP 403 Forbidden for {url} (attempt {attempt}/{retries}) "
                        f"— rotated Device-Id to {new_device_id[:12]}… and sleeping {wait:.1f}s."
                    )
                    time.sleep(wait)
                elif res.status_code == 404:
                    logger.error(f"HTTP 404 for {url} — resource not found, stopping.")
                    break
                else:
                    wait = attempt * RETRY_BACKOFF_TRANSIENT_SECONDS + random.uniform(0.1, 0.3)
                    logger.warning(
                        f"HTTP {res.status_code} for {url} (attempt {attempt}/{retries}) — sleeping {wait:.1f}s"
                    )
                    time.sleep(wait)
            except Exception as exc:
                wait = attempt * RETRY_BACKOFF_ERROR_SECONDS + random.uniform(0.1, 0.3)
                logger.error(f"Request error on attempt {attempt}: {exc} — sleeping {wait:.1f}s")
                time.sleep(wait)
        return None

    # ── Main scraping method ───────────────────────────────────────────────────

    def scrape_category_listings(
        self,
        category_slug: str,
        province_slug: str | None = None,
        max_pages: int = 10,
        seen_ids: set[str] | None = None,
    ) -> list[ListingModel]:
        """
        Paginate through the Posts API feed for a given category.

        Uses ``fields=all`` to retrieve the complete listing payload, including
        location, user/seller info, phone numbers, and vehicle highlight_specs.

        Args:
            category_slug:  e.g. ``'cars-for-sale'``
            province_slug:  e.g. ``'phnom-penh'``; ``None`` = all provinces
            max_pages:      Maximum number of pages to fetch (30 items each)
            seen_ids:       Set of listing IDs already in storage. When provided,
                            pagination stops as soon as a full page of already-seen
                            IDs is encountered (incremental / delta scraping).

        Returns:
            List of validated ``ListingModel`` records (new ones only).
        """
        url = f"{POSTS_API_BASE}/feed"
        records: list[ListingModel] = []
        seen_ids = seen_ids or set()
        offset = 0
        limit = DEFAULT_PAGE_LIMIT
        total_available: int | None = None

        for page in range(1, max_pages + 1):
            params: dict[str, Any] = {
                "category": category_slug,
                "offset": offset,
                "limit": limit,
                "lang": self.lang,
                "sort": "recent",
                "fields": "all",  # ← enables full nested payload
            }
            if province_slug:
                params["province"] = province_slug

            logger.info(
                f"[{category_slug}] Page {page}/{max_pages}  "
                f"offset={offset}  collected={len(records)}" + (f"  total={total_available}" if total_available else "")
            )

            res = self._get(url, params=params)
            if not res:
                logger.warning("No response — stopping pagination.")
                break

            payload = res.json()
            if total_available is None:
                total_available = payload.get("total")

            raw_listings: list[dict[str, Any]] = payload.get("data", []) or []
            if not raw_listings:
                logger.info("Empty page — reached end of feed.")
                break

            new_on_page = 0
            for payload_item in raw_listings:
                listing = payload_item.get("data", payload_item) if isinstance(payload_item, dict) else payload_item
                listing_id = str(listing.get("id", ""))
                if listing_id in seen_ids:
                    continue  # skip already-stored listing
                parsed = self._parse_listing(listing)
                if parsed:
                    records.append(parsed)
                    seen_ids.add(listing_id)
                    new_on_page += 1

            # If the entire page was already known, we've caught up — stop.
            if seen_ids and new_on_page == 0:
                logger.info("Full page already in storage — incremental sync complete.")
                break

            # Early exit once all available listings have been collected
            if total_available and len(records) >= total_available:
                logger.info(f"All {total_available} listings collected.")
                break

            offset += limit
            time.sleep(self.delay + random.uniform(0.05, 0.25))

        logger.info(f"Scrape complete. New records: {len(records)}")
        return records

    # Backwards-compatible alias
    scrape_category_feed = scrape_category_listings

    # ── Listing parser ─────────────────────────────────────────────────────────

    def _parse_listing(self, listing: dict[str, Any]) -> ListingModel | None:
        """
        Map a raw API ``data`` dict (from a ``fields=all`` response) to a
        validated ``ListingModel``.

        Handles all known nesting patterns including:
        - Nested location / category / user objects
        - highlight_specs and object_highlight_specs variants
        - Legacy flat field names (phone_number_1, province, etc.)
        """
        try:
            # ── Category ─────────────────────────────────────────────────────
            cat = listing.get("category") or {}
            category_name = cat.get("en_name") if isinstance(cat, dict) else str(cat)
            category_slug = cat.get("slug") if isinstance(cat, dict) else None
            category_id = cat.get("id") if isinstance(cat, dict) else None

            # ── Location ─────────────────────────────────────────────────────
            loc = listing.get("location") or {}
            province = loc.get("en_name") if isinstance(loc, dict) else listing.get("province")
            province_slug = loc.get("slug") if isinstance(loc, dict) else None
            province_id = loc.get("id") if isinstance(loc, dict) else None
            location_coordinates = loc.get("map") if isinstance(loc, dict) else None
            district: str | None = None
            location_full: str | None = None
            if isinstance(loc, dict):
                location_full = loc.get("en_name3") or loc.get("long_location") or loc.get("en_name2")
                name2 = loc.get("en_name2", "")
                if name2 and "," in name2:
                    district = name2.split(",")[0].strip()

            # ── User / Seller ─────────────────────────────────────────────────
            user = listing.get("user") or {}
            seller_id = str(user.get("id", "")) if isinstance(user, dict) else str(listing.get("userid", ""))
            seller_name = user.get("name") if isinstance(user, dict) else None
            seller_username = user.get("username") if isinstance(user, dict) else None
            seller_avatar_url = extract_image_url(user.get("photo")) if isinstance(user, dict) else None
            seller_is_verified = user.get("is_verify") if isinstance(user, dict) else None
            seller_store_id = listing.get("storeid")
            raw_user_type = user.get("user_type", "1") if isinstance(user, dict) else "1"
            seller_type = "store" if str(raw_user_type) == "2" else "individual"

            # ── Phone numbers ─────────────────────────────────────────────────
            seller_phones: list[str] = []
            phone_field = listing.get("phone")
            if isinstance(phone_field, list):
                seller_phones = [str(p).strip() for p in phone_field if p]
            elif isinstance(phone_field, str) and phone_field.strip():
                seller_phones = [phone_field.strip()]
            else:
                # Legacy numbered fields
                for i in range(1, 4):
                    p = listing.get(f"phone_number_{i}") or listing.get(f"phone_{i}")
                    if p and str(p).strip():
                        seller_phones.append(str(p).strip())
            seller_telco = derive_telco(seller_phones)

            # ── Vehicle specs from highlight_specs ────────────────────────────
            specs: dict[str, Any] = {}
            vehicle_model_year: int | None = None
            vehicle_tax_type: str | None = None

            for spec in listing.get("highlight_specs", []):
                field = spec.get("field", "")
                val = spec.get("value")
                specs[field] = val
                if field == "car-year" and val:
                    with contextlib.suppress(ValueError, TypeError):
                        vehicle_model_year = int(val)
                elif field == "tax-type":
                    vehicle_tax_type = str(val) if val else None

            # Also handle pre-indexed object_highlight_specs dict
            obj_specs = listing.get("object_highlight_specs", {})
            if isinstance(obj_specs, dict):
                for k, v in obj_specs.items():
                    if isinstance(v, dict):
                        specs[k] = v.get("value")
                if vehicle_model_year is None and "car-year" in obj_specs:
                    with contextlib.suppress(ValueError, TypeError):
                        vehicle_model_year = int(obj_specs["car-year"].get("value", 0))

            # ── Extract structured fields from specs blob ────────────────────
            vehicle_mileage_km = parse_mileage(extract_spec_value(specs, "mileage", "km", "odometer", "car-mileage"))
            vehicle_fuel_type = extract_spec_value(specs, "fuel-type", "fuel_type", "fuel")
            vehicle_transmission = extract_spec_value(specs, "transmission", "gearbox", "gear-type")
            raw_engine = extract_spec_value(specs, "engine-size", "engine_size", "engine-cc", "displacement")
            vehicle_engine_cc: int | None = None
            if raw_engine:
                with contextlib.suppress(ValueError, TypeError):
                    vehicle_engine_cc = int(float(str(raw_engine).replace(",", "").strip()))
            vehicle_color = extract_spec_value(specs, "color", "exterior-color", "colour")

            # ── Condition ─────────────────────────────────────────────────────
            cond_raw = listing.get("condition")
            vehicle_condition = cond_raw.get("value") if isinstance(cond_raw, dict) else None

            # ── Brand / Model from title ──────────────────────────────────────
            listing_title = str(listing.get("title", "")).strip()
            vehicle_brand, vehicle_model = extract_brand_model(listing_title)

            # ── Thumbnail, images & link ──────────────────────────────────────
            thumbnail_url = extract_image_url(listing.get("thumbnail") or listing.get("photo"))
            image_urls: list[str] = []
            image_field = listing.get("photos") or listing.get("images")
            if isinstance(image_field, list):
                image_urls = [u for u in (extract_image_url(i) for i in image_field) if u]
            elif isinstance(image_field, dict) or (isinstance(image_field, str) and image_field.strip()):
                single = extract_image_url(image_field)
                if single:
                    image_urls = [single]
            listing_url = (
                listing.get("link")
                or listing.get("short_link")
                or f"https://www.khmer24.com/post-adid-{listing.get('id')}"
            )

            return ListingModel(
                listing_id=str(listing["id"]),
                listing_title=listing_title,
                price=listing.get("price"),
                currency="USD",
                is_premium=listing.get("is_premium"),
                category=category_name,
                category_slug=category_slug,
                category_id=category_id,
                province=province,
                province_slug=province_slug,
                province_id=province_id,
                district=district,
                location_full=location_full,
                location_coordinates=location_coordinates,
                seller_id=seller_id or None,
                seller_name=seller_name,
                seller_type=seller_type,
                seller_username=seller_username,
                seller_avatar_url=seller_avatar_url,
                seller_is_verified=seller_is_verified,
                seller_store_id=seller_store_id,
                seller_phones=seller_phones,
                seller_telco=seller_telco,
                view_count=int(listing.get("views") or 0),
                posted_at=listing.get("posted_date") or listing.get("created_at"),
                renewed_at=listing.get("renew_date"),
                thumbnail_url=thumbnail_url,
                image_urls=image_urls,
                listing_url=listing_url,
                listing_available=listing.get("available"),
                listing_status=listing.get("status"),
                raw_feed_payload=listing,
                vehicle_model_year=vehicle_model_year,
                vehicle_condition=vehicle_condition,
                vehicle_tax_type=vehicle_tax_type,
                vehicle_brand=vehicle_brand,
                vehicle_model=vehicle_model,
                vehicle_mileage_km=vehicle_mileage_km,
                vehicle_fuel_type=vehicle_fuel_type,
                vehicle_transmission=vehicle_transmission,
                vehicle_engine_cc=vehicle_engine_cc,
                vehicle_color=vehicle_color,
                raw_specs=specs if specs else None,
            )

        except Exception as exc:
            logger.warning(f"Skipping listing id={listing.get('id')}: {exc}")
            return None

    # ── Detail-page fetching ───────────────────────────────────────────────────

    def _get_html(self, url: str) -> str | None:
        """
        Fetch an HTML page with retry/backoff, returning its text on success.
        """
        for attempt in range(1, DEFAULT_RETRIES + 1):
            try:
                res = self._web_session.get(url)
                if res.status_code == 200 and "__NUXT_DATA__" in res.text:
                    return res.text
                if res.status_code == 429:
                    wait = _parse_retry_after(res) or attempt * RETRY_BACKOFF_RATE_LIMITED_SECONDS
                    jitter = random.uniform(0.2, 0.6)
                    logger.warning(
                        f"Rate-limited (429). Sleeping {wait + jitter:.1f}s… (attempt {attempt}/{DEFAULT_RETRIES})"
                    )
                    time.sleep(wait + jitter)
                elif res.status_code == 403:
                    wait = attempt * RETRY_BACKOFF_RATE_LIMITED_SECONDS + random.uniform(0.3, 0.8)
                    logger.warning(
                        f"HTTP 403 for {url} (attempt {attempt}/{DEFAULT_RETRIES}) — backing off {wait:.1f}s."
                    )
                    time.sleep(wait)
                elif res.status_code in (404, 500):
                    logger.error(f"HTTP {res.status_code} for {url} — non-recoverable, stopping.")
                    break
            except Exception as exc:
                wait = attempt * RETRY_BACKOFF_ERROR_SECONDS + random.uniform(0.1, 0.3)
                logger.error(f"Request error on attempt {attempt}: {exc} — sleeping {wait:.1f}s")
                time.sleep(wait)
        return None

    def fetch_listing_detail(self, listing_id: str, delay: float | None = None) -> dict[str, Any] | None:
        """
        Fetch one listing's detail page and map it onto enrichment columns.

        Returns a dict of column updates (description, discount prices,
        engagement, vehicle specs, and the verbatim ``raw_detail_payload``),
        or None when the page cannot be fetched or parsed.

        The caller decides whether to sleep between calls (``delay`` overrides
        the client default, 0 disables sleeping).
        """
        url = f"https://www.khmer24.com/post-adid-{listing_id}"
        html = self._get_html(url)
        if html is None:
            return None
        post = extract_detail_post(html)
        if post is None:
            logger.warning(f"No Nuxt payload for listing {listing_id}")
            return None
        sleep_for = self.delay if delay is None else delay
        if sleep_for:
            time.sleep(sleep_for)
        return self._detail_to_row(post)

    def _detail_to_row(self, post: dict[str, Any]) -> dict[str, Any] | None:
        """Map a decoded detail post onto enrichment column values."""
        specs: list[dict[str, Any]] = post.get("specs") or []

        def _unwrap(value: Any) -> Any:
            """Unwrap Nuxt tuple wrappers like ["ShallowReactive", <value>]."""
            if isinstance(value, list) and value and isinstance(value[0], str) and len(value) > 1:
                inner = value[1]
                return None if inner == "<cycle>" else inner
            if value == "<cycle>":
                return None
            return value

        def _flag(value: Any) -> Any:
            """Normalize flag values to 1/0/None (parquet-safe with nulls)."""
            value = _unwrap(value)
            if value is None:
                return None
            if isinstance(value, bool):
                return 1 if value else 0
            if isinstance(value, (int, float)):
                return 1 if value != 0 else 0
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in ("1", "true", "yes"):
                    return 1
                if lowered in ("0", "false", "no"):
                    return 0
            return None

        total_like = _unwrap(post.get("total_like"))
        if isinstance(total_like, bool) or not isinstance(total_like, (int, float, str)):
            likes_count = 0
        elif isinstance(total_like, str):
            likes_count = int(total_like) if total_like.strip().isdigit() else 0
        else:
            likes_count = int(total_like)

        description = _unwrap(post.get("description"))
        if description is not None and not isinstance(description, str):
            description = str(description)
        listing_status = _unwrap(post.get("status"))
        if listing_status is not None and not isinstance(listing_status, str):
            listing_status = str(listing_status)

        row: dict[str, Any] = {
            "description": description,
            "likes_count": likes_count,
            "is_like": _flag(post.get("is_like")),
            "is_saved": _flag(post.get("is_saved")),
            "listing_available": _flag(post.get("available")),
            "listing_status": listing_status,
            "detail_specs": (
                {str(s.get("field")): s.get("display_value") or s.get("value") for s in specs} if specs else None
            ),
            "raw_detail_payload": post,
        }
        discount_obj = post.get("discount")
        discount: dict[str, Any] = discount_obj if isinstance(discount_obj, dict) else {}
        for column, key in (
            ("sale_price", "sale_price"),
            ("original_price", "original_price"),
            ("amount_saved", "amount_saved"),
        ):
            value = discount.get(key)
            if value is None:
                value = post.get(key)
            if value is not None:
                with contextlib.suppress(ValueError):
                    row[column] = float(str(value).replace("$", "").replace(",", "").strip())
        row.update(map_detail_specs(specs))
        return row

    # ── Context manager ───────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying curl_cffi sessions."""
        self._session.close()
        self._web_session.close()

    def __enter__(self) -> "Khmer24Client":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
