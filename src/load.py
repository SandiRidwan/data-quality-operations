"""
Load REAL public datasets into the DuckDB warehouse.

No synthetic rows. Two real sources already on disk:

  1. Morrisons UK products  (a real live-storefront scrape)  -> raw_products
  2. Hacker News comments   (a real public API pull)         -> raw_comments

The point of this repo is to monitor data quality on real data, so both sources
are loaded as-is, warts and all. The DQ checks then find the real problems.

If a source file is missing the loader stops and tells you where to get it.
It never invents data.

Run:  python src/load.py
"""

from __future__ import annotations

import sys

import duckdb

from config import DB, MORRISONS_CSV, HN_COMMENTS_CSV, RAW

DDL = """
CREATE OR REPLACE TABLE raw_products (
    product_code   VARCHAR,
    brand          VARCHAR,
    name           VARCHAR,
    category       VARCHAR,
    sub_category   VARCHAR,
    price_raw      VARCHAR,   -- kept as text on purpose: the source is messy
    promo_raw      VARCHAR,   -- the 'others3' field, free text
    crawled_at     VARCHAR,
    image_url      VARCHAR
);

CREATE OR REPLACE TABLE raw_comments (
    comment_id   BIGINT,
    query        VARCHAR,
    created_at   VARCHAR,
    author       VARCHAR,
    story_title  VARCHAR,
    story_url    VARCHAR,
    points       VARCHAR,   -- text in the source, often empty
    body         VARCHAR
);
"""


def _require(path, url: str) -> None:
    if not path.exists():
        sys.exit(
            f"Real dataset not found: {path}\n"
            f"Get it from: {url}\n"
            f"Then re-run, or set the matching env var in src/config.py.")


def _load_products(con) -> int:
    _require(MORRISONS_CSV, "https://groceries.morrisons.com  (public storefront)")
    con.execute(f"""
        INSERT INTO raw_products
        SELECT
            "shop_product_id", "Brand", "Name", "cat1", "cat2",
            "Price", "others3", "crawl_timestamp", "Image1"
        FROM read_csv('{MORRISONS_CSV.as_posix()}', header=true,
                      all_varchar=true, ignore_errors=true)
    """)
    return con.execute("SELECT COUNT(*) FROM raw_products").fetchone()[0]


def _load_comments(con) -> int:
    _require(HN_COMMENTS_CSV, "https://hn.algolia.com/api  (public, no key)")
    con.execute(f"""
        INSERT INTO raw_comments
        SELECT id, query, created_at, author, story_title, story_url,
               points, text
        FROM read_csv('{HN_COMMENTS_CSV.as_posix()}', header=true,
                      all_varchar=true, ignore_errors=true)
    """)
    return con.execute("SELECT COUNT(*) FROM raw_comments").fetchone()[0]


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    con.execute(DDL)
    print("Loading REAL public datasets...")
    n_prod = _load_products(con)
    print(f"  raw_products  {n_prod:>8,} rows  (Morrisons UK catalogue)")
    n_com = _load_comments(con)
    print(f"  raw_comments  {n_com:>8,} rows  (Hacker News, public API)")
    con.close()
    print(f"Done -> {DB}")


if __name__ == "__main__":
    main()
