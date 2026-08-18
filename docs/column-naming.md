# Processed columns: Before → After

## Table

| Before | After |
|---|---|
| `id` | `listing_id` |
| `title` | `listing_title` |
| `price` | `price` |
| `currency` | `currency` |
| `discount_price` | `discount_price` |
| `is_premium` | `is_premium` |
| `category` | `category` |
| `category_slug` | `category_slug` |
| `province` | `province` |
| `province_slug` | `province_slug` |
| `district` | `district` |
| `full_location` | `location_full` |
| `seller_id` | `seller_id` |
| `seller_name` | `seller_name` |
| `seller_type` | `seller_type` |
| `seller_username` | `seller_username` |
| `phone_numbers` | `seller_phones` |
| `views` | `view_count` |
| `posted_date` | `posted_at` |
| `renew_date` | `renewed_at` |
| `thumbnail_url` | `thumbnail_url` |
| `product_link` | `listing_url` |
| `car_year` | `vehicle_model_year` |
| `car_condition` | `vehicle_condition` |
| `tax_type` | `vehicle_tax_type` |
| `vehicle_brand` | `vehicle_brand` |
| `vehicle_model` | `vehicle_model` |
| `mileage_km` | `vehicle_mileage_km` |
| `fuel_type` | `vehicle_fuel_type` |
| `transmission` | `vehicle_transmission` |
| `engine_cc` | `vehicle_engine_cc` |
| `color` | `vehicle_color` |
| `specs` | `raw_specs` |
| `scraped_at` | `scraped_at` |

**17 renamed · 17 identical · 0 dropped.**

## Why (plain language)

**`id` → `listing_id`** — every other id in the table is qualified (`seller_id`, `category_id`, `province_id`). A bare `id` doesn't say *whose* id it is, and it collides when you join tables. `listing_id` means "this is the id of the listing".

**`title` → `listing_title`** — pairs with `listing_id` and `listing_url`: all three describe the listing itself, so they share the `listing_` prefix.

**`full_location` → `location_full`** — the field is the complete address string. Putting the noun first (`location`) groups it with the other location columns (`province`, `district`) when sorted alphabetically.

**`phone_numbers` → `seller_phones`** — every other seller field starts with `seller_` (`seller_id`, `seller_name`...). `seller_phones` keeps the whole seller group together and greppable.

**`posted_date` → `posted_at`** — `_at` marks timestamps. Also the value is normalized to UTC, so it's an instant in time, not just a date.

**`renew_date` → `renewed_at`** — same reason: a timestamp, named consistently with `posted_at` and `scraped_at`.

**`product_link` → `listing_url`** — `_url` is the suffix used for every web address (`thumbnail_url`). "Link" and "URL" mean the same thing; one word is used everywhere.

**`car_year` → `vehicle_model_year`** — `car_` and `vehicle_` both meant the car's fields; one prefix removes the confusion. "Model year" says exactly what the number is (the year of the car model, not the year the ad was posted).

**`car_condition` → `vehicle_condition`** — same prefix cleanup.

**`tax_type` → `vehicle_tax_type`** — same prefix cleanup.

**`mileage_km` → `vehicle_mileage_km`** — same prefix cleanup; the unit stays in the name.

**`fuel_type` → `vehicle_fuel_type`** — same prefix cleanup.

**`transmission` → `vehicle_transmission`** — same prefix cleanup.

**`engine_cc` → `vehicle_engine_cc`** — same prefix cleanup; the unit stays in the name.

**`color` → `vehicle_color`** — same prefix cleanup.

**`specs` → `raw_specs`** — the `raw_` prefix marks data stored exactly as the website sent it (not cleaned or interpreted). It sets the expectation: look here only if you want the untouched original.

**`views` → `view_count`** — `_count` is the convention for "how many times something happened" (`likes_count` in the raw dataset). `view_count` is unambiguous: a number of views, not a list of views.

**Unchanged (17)** — already clear and conventional: `price`, `currency`, `discount_price`, `is_premium`, `category`, `category_slug`, `province`, `province_slug`, `district`, `seller_id`, `seller_name`, `seller_type`, `seller_username`, `thumbnail_url`, `vehicle_brand`, `vehicle_model`, `scraped_at`.

## Rule of thumb behind every name

1. **Group prefix** — `seller_`, `vehicle_`, `listing_`, `location_`: fields that belong together sort and grep together.
2. **Suffix tells the type** — `_at` (timestamp), `_url` (web address), `_id` (identifier), `_slug` (url-friendly name), `_count` (a number), `_cc`/`_km` (units).
3. **No synonyms** — one word per concept: `url` not "link", `posted` not "date".
4. **Raw is marked** — `raw_` means "verbatim from the source".
