"""
Data-quality dashboard.

Shows the latest run's findings by status, the trend across runs, and the root
cause for anything that is not a PASS.

Run:  streamlit run app/dashboard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from config import DB  # noqa: E402

st.set_page_config(page_title="Data Quality Operations", page_icon="🛡️",
                   layout="wide")

STATUS_COLOR = {"PASS": "#2E7D32", "WARN": "#F9A825", "FAIL": "#C62828"}


@st.cache_data(ttl=30)
def load():
    con = duckdb.connect(str(DB), read_only=True)
    findings = con.execute(
        "SELECT check_name, category, severity, status, value, bad, total, "
        "root_cause FROM dq_findings ORDER BY "
        "CASE status WHEN 'FAIL' THEN 1 WHEN 'WARN' THEN 2 ELSE 3 END, check_name"
    ).df()
    history = con.execute(
        "SELECT run_id, check_name, status FROM dq_history ORDER BY run_id"
    ).df()
    con.close()
    return findings, history


st.title("🛡️ Data Quality Operations")

try:
    findings, history = load()
except Exception as e:
    st.error(f"Warehouse not ready. Run `python src/run_checks.py` first.\n\n{e}")
    st.stop()

if findings.empty:
    st.info("No findings yet. Run `python src/run_checks.py`.")
    st.stop()

counts = findings["status"].value_counts().to_dict()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Checks", len(findings))
c2.metric("Pass", counts.get("PASS", 0))
c3.metric("Warn", counts.get("WARN", 0))
c4.metric("Fail", counts.get("FAIL", 0))

st.caption(
    "Checks run against **real public data**: Morrisons UK catalogue (18,291 "
    "products) and Hacker News comments (8,835). Findings are real, not planted.")

st.divider()

# --- findings by status, worst first -------------------------------------
st.subheader("Findings (worst first)")
for _, r in findings.iterrows():
    color = STATUS_COLOR[r["status"]]
    head = (f"**{r['status']}** · `{r['check_name']}`  ·  {r['category']}  ·  "
            f"severity {r['severity']}")
    st.markdown(
        f"<div style='border-left:5px solid {color};padding-left:10px;'>"
        f"{head}<br><span style='color:#888'>"
        f"bad {int(r['bad']):,} / {int(r['total']):,} · value {r['value']}</span>"
        f"</div>", unsafe_allow_html=True)
    if r["status"] != "PASS" and r["root_cause"]:
        st.caption(f"Root cause: {r['root_cause']}")

st.divider()

# --- trend across runs ----------------------------------------------------
st.subheader("Trend across runs")
if not history.empty and history["run_id"].nunique() > 0:
    pivot = (history.groupby(["run_id", "status"]).size()
             .unstack(fill_value=0).sort_index())
    for col in ("PASS", "WARN", "FAIL"):
        if col not in pivot:
            pivot[col] = 0
    st.line_chart(pivot[["PASS", "WARN", "FAIL"]])
    st.caption(f"{history['run_id'].nunique()} run(s) recorded. "
               "Run src/run_checks.py again to add a point.")
else:
    st.info("Only one run recorded so far.")

with st.expander("Raw findings table"):
    st.dataframe(findings, use_container_width=True, hide_index=True)
