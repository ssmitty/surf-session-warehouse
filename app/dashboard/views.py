from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure
import streamlit as st

from app.dashboard.data import (
    insert_session,
    read_daily_conditions,
    read_forecast_quality,
    read_pipeline_runs,
    read_sessions,
    read_spot_performance,
    read_spots,
)
from app.dashboard.formatting import direction_bucket, format_number, rating_label


def render_overview() -> None:
    sessions = read_sessions()
    performance = read_spot_performance()
    conditions = read_daily_conditions()

    total_sessions = len(sessions)
    avg_rating = sessions["rating"].mean() if total_sessions else None
    surfable_days = _count_surfable_days(conditions)
    best_spot = _best_spot_name(performance)

    columns = st.columns(4)
    columns[0].metric("Logged Sessions", total_sessions)
    columns[1].metric("Average Rating", rating_label(avg_rating))
    columns[2].metric("Best Spot", best_spot)
    columns[3].metric("Modeled Surfable Days", surfable_days)

    if sessions.empty:
        st.info("Load sample sessions or add your first session to start analysis.")
        return

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Spot Performance")
        st.plotly_chart(_spot_rating_chart(performance), use_container_width=True)
    with right:
        st.subheader("Session Timeline")
        st.plotly_chart(_session_timeline_chart(sessions), use_container_width=True)

    st.subheader("Warehouse Mart Preview")
    st.dataframe(performance, use_container_width=True, hide_index=True)


def render_session_log() -> None:
    st.subheader("Add a Surf Session")
    spots = read_spots()
    if spots.empty:
        st.warning("Seed surf spots before logging sessions.")
    else:
        _render_session_form(spots)

    st.subheader("All Sessions")
    st.dataframe(read_sessions(), use_container_width=True, hide_index=True)


def render_forecast_analysis() -> None:
    st.subheader("Forecast Conditions")
    conditions = read_daily_conditions()
    if conditions.empty:
        st.info("Run the Open-Meteo ingestion pipeline and dbt build first.")
        return

    conditions = conditions.copy()
    conditions["wind_direction"] = conditions["avg_wind_direction_deg"].apply(
        direction_bucket
    )

    selected_spots = st.multiselect(
        "Spots",
        sorted(conditions["spot_name"].unique()),
        default=sorted(conditions["spot_name"].unique()),
    )
    filtered = _filter_spots(conditions, selected_spots)

    columns = st.columns(3)
    columns[0].metric("Forecast Days", filtered["forecast_date"].nunique())
    avg_wave_height = format_number(filtered["avg_wave_height_m"].mean())
    avg_wind_speed = format_number(filtered["avg_wind_speed_kmh"].mean())
    columns[1].metric("Avg Wave Height (m)", avg_wave_height)
    columns[2].metric("Avg Wind Speed (km/h)", avg_wind_speed)

    st.plotly_chart(_wave_forecast_chart(filtered), use_container_width=True)

    st.subheader("Modeled Surfable Days")
    surfable = filtered[filtered["modeled_surfable_day"] == 1]
    if surfable.empty:
        st.info("No modeled surfable days in the current forecast window.")
    else:
        st.dataframe(surfable, use_container_width=True, hide_index=True)


def render_quality_analysis() -> None:
    st.subheader("Forecast vs Session Quality")
    quality = read_forecast_quality()
    if quality.empty:
        st.info("Log sessions and run dbt before reviewing forecast quality.")
        return

    quality = quality.copy()
    quality["wind_direction"] = quality["avg_wind_direction_deg"].apply(
        direction_bucket
    )

    columns = st.columns(3)
    high_quality_rate = quality["high_quality_session"].mean() * 100
    matched_surfable = quality["modeled_surfable_day"].sum()
    columns[0].metric("Matched Sessions", len(quality))
    columns[1].metric("High Quality Rate", f"{high_quality_rate:.0f}%")
    columns[2].metric("Modeled Surfable Matches", int(matched_surfable))

    left, right = st.columns([1, 1])
    with left:
        chart_data = _chartable_quality_rows(quality)
        if chart_data.empty:
            st.info("No sessions have matched forecast metrics to chart yet.")
        else:
            st.plotly_chart(_quality_scatter(chart_data), use_container_width=True)
    with right:
        st.dataframe(quality, use_container_width=True, hide_index=True)


def render_pipeline_health() -> None:
    st.subheader("Pipeline Health")
    runs = read_pipeline_runs()
    if runs.empty:
        st.info("No pipeline runs recorded yet.")
        return

    latest = runs.iloc[0]
    columns = st.columns(3)
    columns[0].metric("Latest Status", latest["status"])
    columns[1].metric("Latest Rows Loaded", int(latest["rows_loaded"]))
    columns[2].metric("Recorded Runs", len(runs))

    st.dataframe(runs, use_container_width=True, hide_index=True)


def _render_session_form(spots: pd.DataFrame) -> None:
    with st.form("session_form"):
        spot_name = st.selectbox("Spot", spots["spot_name"].tolist())
        session_date = st.date_input("Session date", value=date.today())
        start_time = st.time_input("Start time")
        duration = st.number_input(
            "Duration minutes",
            min_value=15,
            max_value=360,
            value=90,
            step=5,
        )
        rating = st.slider("Rating", min_value=1, max_value=5, value=3)
        crowd = st.selectbox("Crowd level", ["Low", "Medium", "High"])
        board = st.text_input("Board", value="Shortboard")
        quality = st.selectbox(
            "Actual wave quality",
            ["Poor", "Fair", "Good", "Great", "Excellent"],
        )
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Save session")

    if submitted:
        spot_id = int(spots.loc[spots["spot_name"] == spot_name, "spot_id"].iloc[0])
        insert_session(
            spot_id,
            session_date,
            start_time,
            duration,
            rating,
            crowd,
            board,
            quality,
            notes,
        )
        st.cache_data.clear()
        st.success("Session saved. Run dbt build to refresh analytics marts.")


def _best_spot_name(performance: pd.DataFrame) -> str:
    if performance.empty:
        return "No sessions"
    return str(performance.iloc[0]["spot_name"])


def _count_surfable_days(conditions: pd.DataFrame) -> int:
    if conditions.empty:
        return 0
    return int(conditions["modeled_surfable_day"].sum())


def _filter_spots(data: pd.DataFrame, selected_spots: list[str]) -> pd.DataFrame:
    if not selected_spots:
        return data
    return data[data["spot_name"].isin(selected_spots)]


def _chartable_quality_rows(quality: pd.DataFrame) -> pd.DataFrame:
    chart_data = quality.copy()
    numeric_columns = [
        "avg_wave_height_m",
        "avg_wave_period_s",
        "rating",
    ]
    for column in numeric_columns:
        chart_data[column] = pd.to_numeric(chart_data[column], errors="coerce")

    chart_data = chart_data.dropna(subset=["avg_wave_height_m", "rating"])
    chart_data["avg_wave_period_s"] = chart_data["avg_wave_period_s"].fillna(1)
    return chart_data


def _spot_rating_chart(performance: pd.DataFrame) -> Figure:
    return px.bar(
        performance,
        x="spot_name",
        y="avg_session_rating",
        color="region",
        labels={
            "spot_name": "Spot",
            "avg_session_rating": "Avg Rating",
            "region": "Region",
        },
    )


def _session_timeline_chart(sessions: pd.DataFrame) -> Figure:
    return px.scatter(
        sessions.sort_values("session_date"),
        x="session_date",
        y="rating",
        color="spot_name",
        size="duration_minutes",
        labels={
            "session_date": "Session Date",
            "rating": "Rating",
            "spot_name": "Spot",
            "duration_minutes": "Duration",
        },
    )


def _wave_forecast_chart(conditions: pd.DataFrame) -> Figure:
    return px.line(
        conditions.sort_values("forecast_date"),
        x="forecast_date",
        y="avg_wave_height_m",
        color="spot_name",
        labels={
            "forecast_date": "Forecast Date",
            "avg_wave_height_m": "Avg Wave Height (m)",
            "spot_name": "Spot",
        },
    )


def _quality_scatter(quality: pd.DataFrame) -> Figure:
    return px.scatter(
        quality,
        x="avg_wave_height_m",
        y="rating",
        color="spot_name",
        size="avg_wave_period_s",
        hover_data=["session_date", "actual_wave_quality", "wind_direction"],
        labels={
            "avg_wave_height_m": "Avg Wave Height (m)",
            "rating": "Session Rating",
            "spot_name": "Spot",
            "avg_wave_period_s": "Avg Wave Period",
        },
    )
