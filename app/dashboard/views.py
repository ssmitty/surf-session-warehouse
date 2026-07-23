from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from app.dashboard.data import (
    insert_session,
    read_daily_conditions,
    read_forecast_lineage,
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

    _render_project_summary()

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
        _render_spot_rating_chart(performance)
    with right:
        st.subheader("Session Timeline")
        _render_session_timeline_chart(sessions)

    st.subheader("Spot Performance Mart")
    st.dataframe(performance, use_container_width=True, hide_index=True)


def render_session_log() -> None:
    st.caption(
        "Use this tab to log personal surf sessions. These rows feed the dbt "
        "session fact table and the spot performance mart."
    )
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
    st.caption(
        "This tab shows Open-Meteo forecast data after it has been loaded into "
        "PostgreSQL and rolled up by dbt from hourly raw rows into daily spot "
        "condition rows."
    )
    conditions = read_daily_conditions()
    lineage = read_forecast_lineage()
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

    selected_lineage = _filter_spots(lineage, selected_spots)

    columns = st.columns(4)
    columns[0].metric("Forecast Days", filtered["forecast_date"].nunique())
    columns[1].metric("Daily Condition Rows", len(filtered))
    raw_rows = _sum_columns(selected_lineage, ["raw_marine_rows", "raw_weather_rows"])
    columns[2].metric("Raw Forecast Rows", raw_rows)
    avg_wave_height = format_number(filtered["avg_wave_height_m"].mean())
    avg_wind_speed = format_number(filtered["avg_wind_speed_kmh"].mean())
    columns[3].metric("Avg Wave / Wind", f"{avg_wave_height} m / {avg_wind_speed} km/h")

    _render_wave_forecast_chart(filtered)

    st.subheader("Forecast Warehouse Lineage")
    st.dataframe(selected_lineage, use_container_width=True, hide_index=True)

    st.subheader("Daily Condition Mart")
    st.dataframe(filtered, use_container_width=True, hide_index=True)

    st.subheader("Modeled Surfable Days")
    surfable = filtered[filtered["modeled_surfable_day"] == 1]
    if surfable.empty:
        st.info("No modeled surfable days in the current forecast window.")
    else:
        st.dataframe(surfable, use_container_width=True, hide_index=True)


def render_quality_analysis() -> None:
    st.subheader("Forecast vs Session Quality")
    st.caption(
        "This tab compares logged surf sessions with same-day modeled forecast "
        "conditions when the session dates overlap the current forecast window."
    )
    quality = read_forecast_quality()
    conditions = read_daily_conditions()
    if quality.empty:
        st.info("Log sessions and run dbt before reviewing forecast quality.")
        return

    quality = quality.copy()
    quality["wind_direction"] = quality["avg_wind_direction_deg"].apply(
        direction_bucket
    )

    chart_data = _chartable_quality_rows(quality)

    columns = st.columns(4)
    high_quality_rate = quality["high_quality_session"].mean() * 100
    matched_surfable = _numeric_sum(quality["modeled_surfable_day"])
    columns[0].metric("Analyzed Sessions", len(quality))
    columns[1].metric("High Quality Rate", f"{high_quality_rate:.0f}%")
    columns[2].metric("Forecast-Matched Sessions", len(chart_data))
    columns[3].metric("Modeled Surfable Matches", matched_surfable)

    if chart_data.empty:
        st.info(_forecast_gap_message(quality, conditions))

    left, right = st.columns([1, 1])
    with left:
        if chart_data.empty:
            st.subheader("Forecast Quality Window")
            _render_forecast_quality_chart(conditions)
        else:
            st.subheader("Matched Session Quality")
            _render_quality_scatter(chart_data)
    with right:
        st.subheader("Session Match Status")
        st.dataframe(
            _quality_status_rows(quality),
            use_container_width=True,
            hide_index=True,
        )


def render_pipeline_health() -> None:
    st.subheader("Pipeline Health")
    st.caption(
        "This tab tracks ingestion runs, row counts, statuses, and freshness for "
        "the forecast pipeline."
    )
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


def _render_project_summary() -> None:
    st.subheader("What This App Does")
    st.markdown(
        """
        Surf Session Warehouse is a data engineering demo that turns surf
        forecasts and personal session logs into analytics-ready tables.

        1. Ingest hourly marine and weather forecasts from Open-Meteo.
        2. Store raw forecast rows and surf sessions in PostgreSQL.
        3. Use dbt to model daily spot conditions, session facts, and analytics marts.
        4. Use Streamlit to inspect spot performance, forecast conditions, pipeline health,
           and whether sessions line up with modeled surfable days.
        """
    )


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


def _sum_columns(data: pd.DataFrame, columns: list[str]) -> int:
    if data.empty:
        return 0
    return int(data[columns].sum().sum())


def _numeric_sum(series: pd.Series) -> int:
    return int(pd.to_numeric(series, errors="coerce").fillna(0).sum())


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


def _forecast_gap_message(quality: pd.DataFrame, conditions: pd.DataFrame) -> str:
    if conditions.empty:
        return "No forecast conditions are available yet. Run ingestion and dbt to compare sessions against modeled conditions."

    session_start = quality["session_date"].min()
    session_end = quality["session_date"].max()
    forecast_start = conditions["forecast_date"].min()
    forecast_end = conditions["forecast_date"].max()
    return (
        "No logged sessions share a date with the current forecast mart. "
        f"Your sessions run from {session_start} to {session_end}, while the "
        f"forecast window runs from {forecast_start} to {forecast_end}."
    )


def _quality_status_rows(quality: pd.DataFrame) -> pd.DataFrame:
    status = quality.copy()
    has_forecast = status["avg_wave_height_m"].notna()
    status["forecast_match_status"] = "No same-day forecast"
    status.loc[has_forecast, "forecast_match_status"] = "Matched"
    return status[
        [
            "spot_name",
            "region",
            "session_date",
            "rating",
            "actual_wave_quality",
            "forecast_match_status",
            "avg_wave_height_m",
            "avg_wave_period_s",
            "avg_wind_speed_kmh",
            "modeled_surfable_day",
        ]
    ]


def _render_spot_rating_chart(performance: pd.DataFrame) -> None:
    if performance.empty:
        st.info("No spot performance rows are available yet.")
        return
    chart_data = performance.set_index("spot_name")["avg_session_rating"]
    st.bar_chart(chart_data, x_label="Spot", y_label="Average Rating")


def _render_session_timeline_chart(sessions: pd.DataFrame) -> None:
    if sessions.empty:
        st.info("No sessions are available yet.")
        return
    chart_data = sessions.copy()
    chart_data["session_date"] = pd.to_datetime(chart_data["session_date"])
    st.scatter_chart(
        chart_data,
        x="session_date",
        y="rating",
        color="spot_name",
        size="duration_minutes",
        x_label="Session Date",
        y_label="Rating",
    )


def _render_wave_forecast_chart(conditions: pd.DataFrame) -> None:
    if conditions.empty:
        st.info("No forecast condition rows are available yet.")
        return
    chart_data = conditions.copy()
    chart_data["forecast_date"] = pd.to_datetime(chart_data["forecast_date"])
    st.line_chart(
        chart_data,
        x="forecast_date",
        y="avg_wave_height_m",
        color="spot_name",
        x_label="Forecast Date",
        y_label="Average Wave Height (m)",
    )


def _render_forecast_quality_chart(conditions: pd.DataFrame) -> None:
    if conditions.empty:
        st.info("No forecast condition rows are available yet.")
        return
    chart_data = conditions.copy()
    chart_data["forecast_date"] = pd.to_datetime(chart_data["forecast_date"])
    st.line_chart(
        chart_data,
        x="forecast_date",
        y="avg_wave_height_m",
        color="spot_name",
        x_label="Forecast Date",
        y_label="Average Wave Height (m)",
    )


def _render_quality_scatter(quality: pd.DataFrame) -> None:
    st.scatter_chart(
        quality,
        x="avg_wave_height_m",
        y="rating",
        color="spot_name",
        size="avg_wave_period_s",
        x_label="Average Wave Height (m)",
        y_label="Session Rating",
    )
