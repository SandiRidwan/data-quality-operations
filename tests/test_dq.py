"""
Tests for the data-quality engine.

These verify the engine behaves correctly, using the REAL loaded data:

  - every check parses and runs (no broken SQL)
  - each check returns (metric, bad, total) with bad <= total
  - the verdict rules work on controlled inputs (FAIL/WARN/PASS boundaries)
  - the real findings are reproducible (missing_points is 100% on HN comments)

Run:  python tests/test_dq.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from config import DB, SQL_DIR  # noqa: E402
from run_checks import _parse_checks, _verdict  # noqa: E402


class TestChecksRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DB.exists():
            raise unittest.SkipTest("warehouse not built; run src/load.py")
        cls.con = duckdb.connect(str(DB), read_only=True)
        cls.checks = _parse_checks((SQL_DIR / "checks.sql").read_text("utf-8"))

    def test_all_checks_parse(self):
        self.assertGreaterEqual(len(self.checks), 12)
        for c in self.checks:
            self.assertTrue(c["name"])
            self.assertTrue(c["sql"])
            self.assertIn(c["category"],
                          {"completeness", "uniqueness", "validity",
                           "referential", "freshness", "distribution", "other"})

    def test_every_check_executes_and_is_sane(self):
        for c in self.checks:
            r = self.con.execute(c["sql"]).fetchone()
            self.assertIsNotNone(r, f"{c['name']} returned no row")
            metric, bad, total = r[0], float(r[1] or 0), float(r[2] or 0)
            self.assertGreaterEqual(bad, 0, f"{c['name']} negative bad")
            self.assertGreaterEqual(total, 0, f"{c['name']} negative total")
            # stale_feed encodes DAYS in `bad` against a literal total of 1,
            # so it is the one check where bad may exceed total by design.
            if "stale_feed" in c["name"]:
                continue
            self.assertLessEqual(bad, total, f"{c['name']} bad > total")

    def test_real_finding_is_reproducible(self):
        """HN comments genuinely have 100% missing points - the check must show it."""
        check = next(c for c in self.checks
                     if c["name"] == "comments.missing_points")
        r = self.con.execute(check["sql"]).fetchone()
        bad, total = float(r[1]), float(r[2])
        self.assertEqual(bad, total)  # all rows missing -> a real source limitation


class TestVerdictRules(unittest.TestCase):
    def test_completeness_boundaries(self):
        # 0% -> PASS, 10% -> WARN, 50% -> FAIL (thresholds 5% / 25%)
        self.assertEqual(_verdict("x.missing_field", 0, 100)[0], "PASS")
        self.assertEqual(_verdict("x.missing_field", 10, 100)[0], "WARN")
        self.assertEqual(_verdict("x.missing_field", 50, 100)[0], "FAIL")

    def test_duplicate_rule(self):
        self.assertEqual(_verdict("t.duplicate_id", 0, 1000)[0], "PASS")
        self.assertEqual(_verdict("t.duplicate_id", 50, 1000)[0], "FAIL")

    def test_freshness_rule(self):
        self.assertEqual(_verdict("stale_feed_days", 3, 1)[0], "PASS")
        self.assertEqual(_verdict("stale_feed_days", 45, 1)[0], "WARN")
        self.assertEqual(_verdict("stale_feed_days", 90, 1)[0], "FAIL")

    def test_outlier_is_informational(self):
        self.assertEqual(_verdict("x.price_outlier", 0, 100)[0], "PASS")
        self.assertEqual(_verdict("x.price_outlier", 5, 100)[0], "WARN")

    def test_zero_total_does_not_crash(self):
        # a check over an empty table must not divide by zero
        status, value = _verdict("x.missing_field", 0, 0)
        self.assertEqual(status, "PASS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
