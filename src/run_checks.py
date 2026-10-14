"""
Run the data-quality checks and record findings.

Reads sql/checks.sql, executes every check against the warehouse, turns the raw
counts into PASS / WARN / FAIL using the thresholds in src/config.py, and writes:

  - dq_findings   : the latest run, one row per check (for the dashboard)
  - dq_history    : append-only run log (one row per check per run)

Findings carry a plain-English root cause (from the check's comment header), so
the output is something a teammate can act on, not just a red number.

Run:  python src/run_checks.py
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import duckdb

from config import DB, SQL_DIR, TABLES, THRESHOLDS


def _parse_checks(sql_text: str) -> list[dict]:
    """Split checks.sql into individual checks with their metadata comments."""
    # a check starts at a line beginning with '-- name:'
    blocks = re.split(r"\n(?=-- name:)", sql_text)
    checks = []
    for block in blocks:
        m = re.search(r"-- name:\s*(\S+)", block)
        if not m:
            continue
        name = m.group(1)
        category = (re.search(r"-- category:\s*(\S+)", block) or [None, "other"])[1]
        severity = (re.search(r"-- severity:\s*(\S+)", block) or [None, "medium"])[1]
        root = re.search(r"-- root_cause:\s*(.+?)(?:\n--|\n\n|$)",
                         block, re.S)
        root_cause = " ".join(root.group(1).split()) if root else ""
        # keep everything up to the terminating ';' of this check's statement
        stmt = block.rsplit(";", 1)[0]
        # drop the leading comment lines to keep the SQL only
        sql = "\n".join(
            line for line in stmt.splitlines() if not line.strip().startswith("--"))
        checks.append({
            "name": name, "category": category, "severity": severity,
            "root_cause": root_cause, "sql": sql.strip(),
        })
    return checks


def _verdict(name: str, bad: float, total: float) -> tuple[str, float]:
    """Return (status, value) where value is the metric that matters for the rule."""
    if name == "stale_feed_days":
        days = bad
        st = "FAIL" if days > THRESHOLDS["stale_days_warn"] * 2 else (
            "WARN" if days > THRESHOLDS["stale_days_warn"] else "PASS")
        return st, days

    total = total or 1
    rate = bad / total
    if name.endswith("_outlier") or name.endswith("under_10_products"):
        # informational distribution checks
        st = "WARN" if bad > 0 else "PASS"
        return st, rate
    if "duplicate" in name:
        st = "FAIL" if rate > THRESHOLDS["duplicate_rate_warn"] else "PASS"
        return st, rate
    # completeness / validity -> null/failure rate rules
    st = "FAIL" if rate > THRESHOLDS["null_rate_fail"] else (
        "WARN" if rate > THRESHOLDS["null_rate_warn"] else "PASS")
    # a required, high-severity completeness field fails sooner
    return st, rate


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB))
    checks = _parse_checks((SQL_DIR / "checks.sql").read_text(encoding="utf-8"))

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ran_at = datetime.now(timezone.utc).isoformat()

    con.execute("""
        CREATE TABLE IF NOT EXISTS dq_findings (
            run_id TEXT, check_name TEXT, category TEXT, severity TEXT,
            status TEXT, value DOUBLE, bad DOUBLE, total DOUBLE,
            root_cause TEXT
        );
        CREATE TABLE IF NOT EXISTS dq_history (
            run_id TEXT, ran_at TEXT, check_name TEXT, category TEXT,
            severity TEXT, status TEXT, value DOUBLE, bad DOUBLE, total DOUBLE
        );
        DELETE FROM dq_findings;   -- findings table always holds the latest run
    """)

    rows = []
    summary = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for c in checks:
        r = con.execute(c["sql"]).fetchone()
        metric, bad, total = r[0], float(r[1] or 0), float(r[2] or 0)
        status, value = _verdict(c["name"], bad, total)
        summary[status] += 1
        rows.append((run_id, c["name"], c["category"], c["severity"], status,
                     round(value, 4), bad, total, c["root_cause"]))
        tag = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL"}[status]
        print(f"  [{tag}] {c['name']:<38} bad={int(bad):>7} total={int(total):>8}")

    con.executemany(
        "INSERT INTO dq_findings VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.executemany(
        "INSERT INTO dq_history (run_id,ran_at,check_name,category,severity,"
        "status,value,bad,total) VALUES (?,?,?,?,?,?,?,?,?)",
        [(r[0], ran_at, r[1], r[2], r[3], r[4], r[5], r[6], r[7]) for r in rows])

    # persist the latest findings as CSV for the repo (a real artifact)
    con.execute(f"""
        COPY dq_findings TO '{(TABLES / "dq_findings.csv").as_posix()}'
        (HEADER, DELIMITER ',')
    """)
    con.close()

    print(f"\nRun {run_id}: {summary['PASS']} pass, "
          f"{summary['WARN']} warn, {summary['FAIL']} fail")
    print(f"Wrote {(TABLES / 'dq_findings.csv')}")


if __name__ == "__main__":
    main()
