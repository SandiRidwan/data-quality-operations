<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Orbitron&weight=900&size=34&duration=3000&pause=1000&color=2E7D32&center=true&vCenter=true&width=940&height=70&lines=DATA+QUALITY+OPERATIONS" alt="Data Quality Operations" />

![DuckDB](https://img.shields.io/badge/DuckDB-SQL-FFF000?style=for-the-badge&logo=duckdb&logoColor=black)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Data](https://img.shields.io/badge/Data-REAL_public-2E7D32?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10+-1F5C3D?style=for-the-badge&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-0D1117?style=for-the-badge)

</div>

---

## 🛡️ What this is

A **data-quality monitoring system** that runs SQL checks against a warehouse,
turns the raw counts into **PASS / WARN / FAIL**, writes a plain-English **root
cause** for anything that is not a pass, and keeps a **run history** so you can
see a trend rather than a snapshot.

It is the "monitor data quality and key data flows, find errors, identify root
causes" half of an operational analyst role — in code, on **real data**.

**The data is real.** Two public datasets already on disk:

| Table | Rows | Real source |
|---|---:|---|
| `raw_products` | 18,291 | Morrisons UK catalogue (live storefront scrape) |
| `raw_comments` | 8,835 | Hacker News comments (public API, no key) |

Nothing is planted. The checks find what is actually wrong with the data.

```bash
python src/load.py          # load the two REAL datasets
python src/run_checks.py    # run every check, record findings + history
streamlit run app/dashboard.py
python tests/test_dq.py
```

---

## ⚡ Real findings (from the real data)

Latest run: **9 PASS · 2 WARN · 2 FAIL**

| Check | Category | Verdict | Measured | Root cause (as reported) |
|---|---|---|---|---|
| `comments.missing_points` | completeness | **FAIL** | 8,835 / 8,835 (100%) | The public HN API omits `points` on comment records — a **source limitation**, not a pipeline bug. Documented and tracked, not hidden. |
| `comments.stale_feed` | freshness | **FAIL** | 16 days old | The newest comment is older than the freshness window → the scheduled pull stopped running. |
| `products.price_outlier` | validity | **WARN** | 19 rows > p99.9 | A price far above the 99.9th percentile usually means a **decimal shift** (pence read as pounds), not a genuinely expensive item. |
| `cross.category_coverage` | distribution | **WARN** | 1 of 19 categories < 10 products | A near-empty category can mean a **scraping gap** on that aisle, not a small category. |
| *(9 others)* | all | PASS | 0 bad rows | — |

> **Why** — "find errors and identify root causes" is on most analyst specs, and it
> is usually untested.
> **Goal** — prove the checks run, the verdicts are rule-based, and every failure
> comes with a cause a teammate can act on.
> **Impact** — the two FAILs here are *different in kind*: one is a source
> limitation to document, the other is a real operational break to fix. Conflating
> them is the classic data-quality mistake.

---

## 🧠 How it works

Three stages, each a small file:

```
src/load.py          real CSV  ->  DuckDB warehouse (no synthetic rows)
src/run_checks.py    reads sql/checks.sql, runs each check, applies thresholds
                     -> dq_findings (latest) + dq_history (append-only)
app/dashboard.py     findings by status, root causes, trend across runs
```

**Checks live in SQL, policy lives in Python.** `sql/checks.sql` holds the rules;
`src/config.py` holds the thresholds. Change the policy without touching the SQL.

**Every check is one statement returning `(metric, bad, total)`.** The engine turns
that into a verdict:

| Category | Rule (see `src/config.py`) |
|---|---|
| completeness / validity | `> 25% bad` → FAIL · `> 5%` → WARN |
| uniqueness | `> 1% duplicates` → FAIL |
| freshness | `> 60 days` → FAIL · `> 30 days` → WARN |
| distribution | any outlier → WARN (informational) |

13 checks across **6 categories**: completeness, uniqueness, validity,
referential, freshness, distribution.

---

## ✅ Quality — 8 automated tests

```
PASS  every check parses and routes to a known category
PASS  every check executes and returns sane counts (bad <= total)
PASS  the real finding is reproducible (HN comments: 100% missing points)
PASS  completeness verdict boundaries (0% / 10% / 50%)
PASS  duplicate rule boundary
PASS  freshness rule boundaries (3 / 45 / 90 days)
PASS  outlier checks are informational (WARN, never FAIL)
PASS  a check over an empty table does not divide by zero
```

The tests verify the **engine and the rules**, using the real loaded data — not
that files exist.

---

## 📁 Structure

```
data-quality-operations/
├── src/
│   ├── config.py          # paths, data sources, DQ thresholds (the policy)
│   ├── load.py            # load REAL datasets -> DuckDB
│   └── run_checks.py      # run checks, verdicts, findings + history
├── sql/checks.sql         # the 13 rules, each with a plain-English root cause
├── app/dashboard.py       # Streamlit: status, root causes, trend
├── tests/test_dq.py       # 8 tests (engine + rules)
├── data/warehouse.duckdb  # rebuilt by load.py, not committed
├── reports/tables/        # dq_findings.csv (a real artifact)
└── docs/
```

---

## 🚀 Quick Start

```bash
pip install -r requirements.txt

# default source paths (override via env if yours differ)
set MORRISONS_CSV=F:\path\to\morrisons_products.csv
set HN_COMMENTS_CSV=F:\path\to\hn_comments.csv

python src/load.py
python src/run_checks.py
streamlit run app/dashboard.py
python tests/test_dq.py
```

If a source file is missing, the loader **stops and tells you where to get it** —
it never invents data.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Warehouse** | DuckDB (embedded OLAP; SQL is portable to PostgreSQL/BigQuery) |
| **Checks** | SQL (`sql/checks.sql`), declared with metadata comments |
| **Engine** | Python stdlib + regex parse of the check file |
| **Dashboard** | Streamlit |
| **Data** | real public datasets (Morrisons catalogue · Hacker News) |
| **Tests** | `unittest` — engine + rule boundaries |

---

## ⚠️ Limitations (honest)

- **DuckDB, not a production warehouse.** The SQL is standard and ports to
  PostgreSQL/BigQuery, but scheduling, alert routing and RBAC are out of scope here.
- **Two datasets, one domain each.** The 6 check categories are general; the
  specific thresholds are tuned to these sources.
- **No alerting yet.** Findings are written to a table and a dashboard; wiring them
  to email/Slack is a next step, not a claim.
- **The `missing_points` FAIL is a source limitation**, shown on purpose: a real DQ
  system must distinguish "the data is broken" from "the source never had it".

---

## 👤 Author

<div align="center">

**Sandi Ridwan** — Data Automation Engineer · Data Quality · SQL & Analytics

📍 Palu, Central Sulawesi, Indonesia

[![Upwork](https://img.shields.io/badge/Upwork-Hire_Me-2E7D32?style=for-the-badge&logo=upwork&logoColor=white)](https://www.upwork.com/freelancers/~011f6d0fbb4a372974)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/sandi-ridwan)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/SandiRidwan)

</div>

## 📄 License

MIT — code. Datasets belong to their sources: Morrisons UK (public storefront),
Hacker News (public API).
