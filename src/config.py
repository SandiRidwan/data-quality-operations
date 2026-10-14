"""Central config: paths, data sources, and DQ thresholds."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
DB = DATA / "warehouse.duckdb"
SQL_DIR = ROOT / "sql"
REPORTS = ROOT / "reports"
TABLES = REPORTS / "tables"

# ---------------------------------------------------------------------------
# REAL public datasets already on disk. No synthetic data.
# Override with env vars if your paths differ.
# ---------------------------------------------------------------------------
MORRISONS_CSV = Path(os.environ.get(
    "MORRISONS_CSV",
    r"F:\PROJECT\Data Analyst Project\morrisons-market-intelligence"
    r"\data\raw\morrisons_products.csv"))

HN_COMMENTS_CSV = Path(os.environ.get(
    "HN_COMMENTS_CSV",
    r"F:\PROJECT\Data Analyst Project\ai-sentiment-intelligence"
    r"\data\raw\hn_comments.csv"))

# ---------------------------------------------------------------------------
# DQ thresholds. A check fails when the measured value breaks these.
# Kept here (not hard-coded in SQL) so the policy is visible and tunable.
# ---------------------------------------------------------------------------
THRESHOLDS = {
    "null_rate_warn": 0.05,     # > 5% nulls  -> WARN
    "null_rate_fail": 0.25,     # > 25% nulls -> FAIL (for a required field)
    "stale_days_warn": 30,      # data older than N days -> WARN
    "duplicate_rate_warn": 0.01,
    "min_rows": 1,
}
