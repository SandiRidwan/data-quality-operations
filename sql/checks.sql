-- ===========================================================================
-- checks.sql — the data-quality rules, written as SQL.
--
-- Each check returns a single row: (metric, bad, total). The Python engine turns
-- that into PASS / WARN / FAIL against the thresholds in src/config.py, records
-- the finding, and stores it in dq_history for the dashboard.
--
-- Categories:
--   completeness · uniqueness · validity · referential · freshness · distribution
--
-- Checks run against the REAL loaded data (raw_products, raw_comments), so the
-- findings are real, not planted.
-- ===========================================================================


-- name: products.missing_product_code
-- category: completeness
-- severity: high
-- root_cause: the scraper returned rows without the store's product id, usually
--             a card that failed to expand on the listing page
SELECT
    'missing_product_code' AS metric,
    SUM(CASE WHEN product_code IS NULL OR TRIM(product_code) = '' THEN 1 ELSE 0 END) AS bad,
    COUNT(*) AS total
FROM raw_products;


-- name: products.missing_name
-- category: completeness
-- severity: high
-- root_cause: product name is required for any downstream report; a blank name
--             means the listing changed its markup and the selector missed
SELECT
    'missing_name' AS metric,
    SUM(CASE WHEN name IS NULL OR TRIM(name) = '' THEN 1 ELSE 0 END) AS bad,
    COUNT(*) AS total
FROM raw_products;


-- name: products.missing_brand
-- category: completeness
-- severity: medium
-- root_cause: brand is optional on the source; a high blank rate is normal but
--             breaks any brand-level cut, so it is watched, not failed
SELECT
    'missing_brand' AS metric,
    SUM(CASE WHEN brand IS NULL OR TRIM(brand) = '' THEN 1 ELSE 0 END) AS bad,
    COUNT(*) AS total
FROM raw_products;


-- name: products.missing_category
-- category: completeness
-- severity: medium
-- root_cause: category comes from the breadcrumb; missing means the page did not
--             render the trail before the row was captured
SELECT
    'missing_category' AS metric,
    SUM(CASE WHEN category IS NULL OR TRIM(category) = '' THEN 1 ELSE 0 END) AS bad,
    COUNT(*) AS total
FROM raw_products;


-- name: products.duplicate_product_code
-- category: uniqueness
-- severity: high
-- root_cause: the same product captured twice (double load or a re-scrape without
--             dedup); if profile_url/code is the key, this breaks joins
SELECT
    'duplicate_product_code' AS metric,
    (SELECT COALESCE(SUM(c - 1), 0) FROM (
        SELECT COUNT(*) AS c FROM raw_products
        WHERE product_code IS NOT NULL AND TRIM(product_code) <> ''
        GROUP BY product_code HAVING COUNT(*) > 1)) AS bad,
    (SELECT COUNT(*) FROM raw_products
     WHERE product_code IS NOT NULL AND TRIM(product_code) <> '') AS total;


-- name: products.unparseable_price
-- category: validity
-- severity: high
-- root_cause: the displayed price is kept as text; non-numeric means a currency
--             format the parser did not expect (e.g. '£' or a range)
SELECT
    'unparseable_price' AS metric,
    SUM(CASE WHEN TRY_CAST(REPLACE(REPLACE(price_raw,'£',''),',','') AS DOUBLE) IS NULL
                  AND price_raw IS NOT NULL AND TRIM(price_raw) <> ''
             THEN 1 ELSE 0 END) AS bad,
    COUNT(*) AS total
FROM raw_products;


-- name: products.price_outlier
-- category: validity
-- severity: medium
-- root_cause: a price far above the 99.9th percentile usually means a decimal
--             shift (e.g. pence read as pounds) rather than a real expensive item
SELECT
    'price_outlier' AS metric,
    (SELECT COUNT(*) FROM raw_products
     WHERE TRY_CAST(REPLACE(REPLACE(price_raw,'£',''),',','') AS DOUBLE) >
           (SELECT QUANTILE_CONT(
                TRY_CAST(REPLACE(REPLACE(price_raw,'£',''),',','') AS DOUBLE), 0.999)
            FROM raw_products
            WHERE TRY_CAST(REPLACE(REPLACE(price_raw,'£',''),',','') AS DOUBLE)
                  IS NOT NULL)) AS bad,
    (SELECT COUNT(*) FROM raw_products
     WHERE TRY_CAST(REPLACE(REPLACE(price_raw,'£',''),',','') AS DOUBLE) IS NOT NULL)
    AS total;


-- name: comments.missing_points
-- category: completeness
-- severity: medium
-- root_cause: the public HN API omits 'points' on comment records; this is a
--             source limitation, not a pipeline bug - documented, still tracked
SELECT
    'missing_points' AS metric,
    SUM(CASE WHEN points IS NULL OR TRIM(points) = '' THEN 1 ELSE 0 END) AS bad,
    COUNT(*) AS total
FROM raw_comments;


-- name: comments.missing_body
-- category: completeness
-- severity: high
-- root_cause: a comment with no text cannot be analysed; usually a deleted or
--             dead comment that the API still returns as a stub
SELECT
    'missing_body' AS metric,
    SUM(CASE WHEN body IS NULL OR TRIM(body) = '' THEN 1 ELSE 0 END) AS bad,
    COUNT(*) AS total
FROM raw_comments;


-- name: comments.duplicate_id
-- category: uniqueness
-- severity: high
-- root_cause: the same comment id twice means paginated pulls overlapped
SELECT
    'duplicate_comment_id' AS metric,
    (SELECT COALESCE(SUM(c - 1), 0) FROM (
        SELECT COUNT(*) AS c FROM raw_comments
        WHERE comment_id IS NOT NULL GROUP BY comment_id HAVING COUNT(*) > 1)) AS bad,
    (SELECT COUNT(*) FROM raw_comments WHERE comment_id IS NOT NULL) AS total;


-- name: comments.unparseable_date
-- category: validity
-- severity: high
-- root_cause: created_at is an ISO string; a non-parseable value breaks any
--             time-series cut and usually means a timezone/format change
SELECT
    'unparseable_created_at' AS metric,
    SUM(CASE WHEN TRY_CAST(created_at AS TIMESTAMP) IS NULL
                  AND created_at IS NOT NULL AND TRIM(created_at) <> ''
             THEN 1 ELSE 0 END) AS bad,
    COUNT(*) AS total
FROM raw_comments;


-- name: comments.stale_feed
-- category: freshness
-- severity: medium
-- root_cause: the newest comment is older than the freshness window, which means
--             the scheduled pull stopped running
SELECT
    'stale_feed_days' AS metric,
    COALESCE(
        DATE_DIFF('day', MAX(TRY_CAST(created_at AS TIMESTAMP)), CURRENT_TIMESTAMP),
        99999) AS bad,
    1 AS total
FROM raw_comments;


-- name: cross.category_coverage
-- category: distribution
-- severity: low
-- root_cause: a category with very few products can mean a scraping gap on that
--             aisle rather than a genuinely small category
SELECT
    'categories_with_under_10_products' AS metric,
    (SELECT COUNT(*) FROM (
        SELECT category FROM raw_products
        WHERE category IS NOT NULL AND TRIM(category) <> ''
        GROUP BY category HAVING COUNT(*) < 10)) AS bad,
    (SELECT COUNT(DISTINCT category) FROM raw_products
     WHERE category IS NOT NULL AND TRIM(category) <> '') AS total;
