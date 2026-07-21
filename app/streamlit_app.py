from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.dashboard.views import (
    render_forecast_analysis,
    render_overview,
    render_pipeline_health,
    render_quality_analysis,
    render_session_log,
)
from pipelines.db import ensure_schema

st.set_page_config(page_title="Surf Session Warehouse", layout="wide")

ensure_schema()

st.title("Surf Session Warehouse")
st.caption(
    "PostgreSQL-backed surf session analytics with forecast ingestion, "
    "warehouse models, and dashboard reporting."
)

tabs = st.tabs(
    [
        "Overview",
        "Session Log",
        "Forecast Conditions",
        "Quality Analysis",
        "Pipeline Health",
    ]
)

with tabs[0]:
    render_overview()

with tabs[1]:
    render_session_log()

with tabs[2]:
    render_forecast_analysis()

with tabs[3]:
    render_quality_analysis()

with tabs[4]:
    render_pipeline_health()
