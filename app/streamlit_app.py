from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from pipelines.db import connect, ensure_schema

st.set_page_config(page_title="Surf Session Warehouse", layout="wide")


@st.cache_data(ttl=60)
def read_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql(sql, conn, params=params)


def execute(sql: str, params: tuple = ()) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        conn.commit()
    read_query.clear()


def direction_bucket(degrees: float | None) -> str:
    if degrees is None or pd.isna(degrees):
        return "Unknown"
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return directions[int((degrees + 22.5) // 45) % 8]


ensure_schema()

st.title("Surf Session Warehouse")
st.caption(
    "PostgreSQL-backed surf session analytics with forecast ingestion, "
    "warehouse models, and dashboard reporting."
)

overview, sessions_tab, forecast_tab, pipeline_tab = st.tabs(
    ["Overview", "Session Log", "Forecast Conditions", "Pipeline Health"]
)

with overview:
    sessions = read_query(
        """
        SELECT
            s.session_id,
            sp.spot_name,
            sp.region,
            s.session_date,
            s.duration_minutes,
            s.rating,
            s.crowd_level,
            s.board,
            s.actual_wave_quality,
            s.notes
        FROM surf_sessions s
        JOIN surf_spots sp ON s.spot_id = sp.spot_id
        ORDER BY s.session_date DESC, s.session_id DESC
        """
    )

    total_sessions = len(sessions)
    avg_rating = sessions["rating"].mean() if total_sessions else 0
    best_spot = "No sessions yet"
    if total_sessions:
        best_spot = (
            sessions.groupby("spot_name")["rating"]
            .mean()
            .sort_values(ascending=False)
            .index[0]
        )

    metric_cols = st.columns(3)
    metric_cols[0].metric("Logged Sessions", total_sessions)
    avg_rating_label = f"{avg_rating:.2f}" if total_sessions else "0.00"
    metric_cols[1].metric("Average Rating", avg_rating_label)
    metric_cols[2].metric("Best Spot", best_spot)

    if total_sessions:
        left, right = st.columns(2)
        with left:
            st.subheader("Rating by Spot")
            spot_ratings = sessions.groupby(
                "spot_name",
                as_index=False,
            )["rating"].mean()
            chart = px.bar(
                spot_ratings,
                x="spot_name",
                y="rating",
                labels={"spot_name": "Spot", "rating": "Avg Rating"},
            )
            st.plotly_chart(chart, use_container_width=True)
        with right:
            st.subheader("Recent Sessions")
            st.dataframe(sessions, use_container_width=True, hide_index=True)
    else:
        st.info(
            "Load sample sessions or add your first surf session to start "
            "the dashboard."
        )

with sessions_tab:
    st.subheader("Add a Surf Session")
    spots = read_query("SELECT spot_id, spot_name FROM surf_spots ORDER BY spot_name")
    if spots.empty:
        st.warning("Seed surf spots before logging sessions.")
    else:
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
            spot_id = int(
                spots.loc[spots["spot_name"] == spot_name, "spot_id"].iloc[0]
            )
            execute(
                """
                INSERT INTO surf_sessions (
                    spot_id, session_date, start_time, duration_minutes, rating,
                    crowd_level, board, actual_wave_quality, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    spot_id,
                    session_date,
                    start_time,
                    duration,
                    rating,
                    crowd,
                    board,
                    quality,
                    notes,
                ),
            )
            st.success("Session saved.")

    st.subheader("All Sessions")
    session_table = read_query(
        """
        SELECT
            s.session_date,
            sp.spot_name,
            s.start_time,
            s.duration_minutes,
            s.rating,
            s.crowd_level,
            s.board,
            s.actual_wave_quality,
            s.notes
        FROM surf_sessions s
        JOIN surf_spots sp ON s.spot_id = sp.spot_id
        ORDER BY s.session_date DESC
        """
    )
    st.dataframe(session_table, use_container_width=True, hide_index=True)

with forecast_tab:
    st.subheader("Forecast Conditions")
    forecast = read_query(
        """
        SELECT
            sp.spot_name,
            m.forecast_time,
            m.wave_height_m,
            m.wave_period_s,
            m.swell_wave_height_m,
            m.swell_wave_period_s,
            w.wind_speed_kmh,
            w.wind_direction_deg,
            w.temperature_c
        FROM raw_marine_forecasts m
        JOIN surf_spots sp ON m.spot_id = sp.spot_id
        LEFT JOIN raw_weather_forecasts w
            ON m.spot_id = w.spot_id
           AND m.forecast_time = w.forecast_time
        ORDER BY m.forecast_time DESC
        LIMIT 1000
        """
    )
    if forecast.empty:
        st.info("Run the Open-Meteo ingestion pipeline to load forecast rows.")
    else:
        forecast["wind_direction"] = forecast["wind_direction_deg"].apply(
            direction_bucket
        )
        spot_filter = st.multiselect(
            "Spots",
            sorted(forecast["spot_name"].unique()),
            default=sorted(forecast["spot_name"].unique())[:2],
        )
        if spot_filter:
            filtered = forecast[forecast["spot_name"].isin(spot_filter)]
        else:
            filtered = forecast
        st.plotly_chart(
            px.line(
                filtered.sort_values("forecast_time"),
                x="forecast_time",
                y="wave_height_m",
                color="spot_name",
                labels={
                    "forecast_time": "Forecast Time",
                    "wave_height_m": "Wave Height (m)",
                    "spot_name": "Spot",
                },
            ),
            use_container_width=True,
        )
        st.dataframe(filtered, use_container_width=True, hide_index=True)

with pipeline_tab:
    st.subheader("Pipeline Runs")
    runs = read_query(
        """
        SELECT pipeline_name, status, rows_loaded, message, started_at, finished_at
        FROM pipeline_runs
        ORDER BY started_at DESC
        LIMIT 50
        """
    )
    if runs.empty:
        st.info("No pipeline runs recorded yet.")
    else:
        st.dataframe(runs, use_container_width=True, hide_index=True)
