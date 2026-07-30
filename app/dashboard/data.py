from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

from pipelines.db import connect, sqlalchemy_database_url

QueryParams = Sequence[object] | None
ROOT_DIR = Path(__file__).resolve().parents[2]


def read_query(sql: str, params: QueryParams = None) -> pd.DataFrame:
    """Read a SQL query into a dataframe using the project warehouse."""
    engine = create_engine(sqlalchemy_database_url())
    with engine.connect() as conn:
        return pd.read_sql(sql, conn, params=params)


def execute_query(sql: str, params: QueryParams = None) -> None:
    """Run a write query against the project warehouse."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        conn.commit()


def read_sessions() -> pd.DataFrame:
    try:
        return read_query(
            """
            SELECT
                session_id,
                spot_name,
                region,
                session_date,
                start_time,
                duration_minutes,
                rating,
                crowd_level,
                board,
                actual_wave_quality,
                notes
            FROM analytics.fct_surf_sessions
            ORDER BY session_date DESC, session_id DESC
            """
        )
    except Exception:
        return _demo_sessions()


def read_spots() -> pd.DataFrame:
    try:
        return read_query(
            """
            SELECT spot_id, spot_name, region
            FROM surf_spots
            ORDER BY spot_name
            """
        )
    except Exception:
        return _demo_spots()[["spot_id", "spot_name", "region"]]


def read_spot_performance() -> pd.DataFrame:
    try:
        return read_query(
            """
            SELECT
                spot_name,
                region,
                session_count,
                avg_session_rating,
                best_session_rating,
                avg_duration_minutes,
                most_recent_session_date
            FROM analytics.mart_spot_performance
            ORDER BY avg_session_rating DESC, session_count DESC
            """
        )
    except Exception:
        return _demo_spot_performance()


def read_forecast_quality() -> pd.DataFrame:
    try:
        return read_query(
            """
            SELECT
                spot_name,
                region,
                session_date,
                rating,
                actual_wave_quality,
                avg_wave_height_m,
                max_wave_height_m,
                avg_wave_period_s,
                avg_swell_wave_height_m,
                avg_swell_wave_period_s,
                avg_wind_speed_kmh,
                avg_wind_direction_deg,
                modeled_surfable_day,
                high_quality_session
            FROM analytics.mart_forecast_vs_session_quality
            ORDER BY session_date DESC, spot_name
            """
        )
    except Exception:
        return _demo_forecast_quality()


def read_daily_conditions() -> pd.DataFrame:
    try:
        return read_query(
            """
            SELECT
                spots.spot_name,
                spots.region,
                conditions.forecast_date,
                conditions.avg_wave_height_m,
                conditions.max_wave_height_m,
                conditions.avg_wave_period_s,
                conditions.avg_swell_wave_height_m,
                conditions.avg_swell_wave_period_s,
                conditions.avg_wind_speed_kmh,
                conditions.avg_wind_direction_deg,
                conditions.modeled_surfable_day
            FROM analytics.fct_daily_spot_conditions conditions
            JOIN analytics.stg_spots spots
                ON conditions.spot_id = spots.spot_id
            ORDER BY conditions.forecast_date DESC, spots.spot_name
            """
        )
    except Exception:
        return _demo_daily_conditions()


def read_forecast_lineage() -> pd.DataFrame:
    try:
        return read_query(
            """
            WITH marine AS (
                SELECT
                    spot_id,
                    COUNT(*) AS raw_marine_rows
                FROM raw_marine_forecasts
                GROUP BY spot_id
            ),
            weather AS (
                SELECT
                    spot_id,
                    COUNT(*) AS raw_weather_rows
                FROM raw_weather_forecasts
                GROUP BY spot_id
            ),
            daily_conditions AS (
                SELECT
                    spot_id,
                    COUNT(*) AS daily_condition_rows,
                    MIN(forecast_date) AS first_forecast_date,
                    MAX(forecast_date) AS latest_forecast_date
                FROM analytics.fct_daily_spot_conditions
                GROUP BY spot_id
            )
            SELECT
                spots.spot_name,
                COALESCE(marine.raw_marine_rows, 0) AS raw_marine_rows,
                COALESCE(weather.raw_weather_rows, 0) AS raw_weather_rows,
                COALESCE(daily_conditions.daily_condition_rows, 0) AS daily_condition_rows,
                daily_conditions.first_forecast_date,
                daily_conditions.latest_forecast_date
            FROM surf_spots spots
            LEFT JOIN marine
                ON spots.spot_id = marine.spot_id
            LEFT JOIN weather
                ON spots.spot_id = weather.spot_id
            LEFT JOIN daily_conditions
                ON spots.spot_id = daily_conditions.spot_id
            ORDER BY spots.spot_name
            """
        )
    except Exception:
        return _demo_forecast_lineage()


def read_pipeline_runs() -> pd.DataFrame:
    try:
        return read_query(
            """
            SELECT
                pipeline_name,
                status,
                rows_loaded,
                message,
                started_at,
                finished_at
            FROM pipeline_runs
            ORDER BY started_at DESC
            LIMIT 50
            """
        )
    except Exception:
        return _demo_pipeline_runs()


def insert_session(
    spot_id: int,
    session_date: object,
    start_time: object,
    duration_minutes: int,
    rating: int,
    crowd_level: str,
    board: str,
    actual_wave_quality: str,
    notes: str,
) -> None:
    execute_query(
        """
        INSERT INTO surf_sessions (
            spot_id,
            session_date,
            start_time,
            duration_minutes,
            rating,
            crowd_level,
            board,
            actual_wave_quality,
            notes
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            spot_id,
            session_date,
            start_time,
            duration_minutes,
            rating,
            crowd_level,
            board,
            actual_wave_quality,
            notes,
        ),
    )


def warehouse_is_available() -> bool:
    try:
        read_query("SELECT 1")
    except Exception:
        return False
    return True


def _demo_spots() -> pd.DataFrame:
    spots = pd.read_csv(ROOT_DIR / "data" / "sample_spots.csv")
    spots.insert(0, "spot_id", range(1, len(spots) + 1))
    return spots


def _demo_sessions() -> pd.DataFrame:
    spots = _demo_spots()
    sessions = pd.read_csv(ROOT_DIR / "data" / "sample_sessions.csv")
    sessions = sessions.merge(
        spots[["spot_id", "spot_slug", "spot_name", "region"]],
        on="spot_slug",
        how="left",
    )
    sessions.insert(0, "session_id", range(1, len(sessions) + 1))
    sessions["session_date"] = pd.to_datetime(sessions["session_date"]).dt.date
    return sessions[
        [
            "session_id",
            "spot_name",
            "region",
            "session_date",
            "start_time",
            "duration_minutes",
            "rating",
            "crowd_level",
            "board",
            "actual_wave_quality",
            "notes",
        ]
    ].sort_values(["session_date", "session_id"], ascending=[False, False])


def _demo_daily_conditions() -> pd.DataFrame:
    spots = _demo_spots()
    rows: list[dict[str, object]] = []
    forecast_dates = pd.date_range("2026-07-21", periods=7, freq="D")
    spot_adjustments = {
        "Indian River Inlet": 0.25,
        "Ocean City": 0.05,
        "Strathmere": 0.15,
    }

    for _, spot in spots.iterrows():
        adjustment = spot_adjustments.get(str(spot["spot_name"]), 0)
        for day_index, forecast_date in enumerate(forecast_dates):
            wave_height = round(0.7 + adjustment + (day_index % 4) * 0.18, 2)
            wave_period = round(6.5 + (day_index % 5) * 0.7, 1)
            wind_speed = round(10 + ((day_index + int(spot["spot_id"])) % 5) * 2.4, 1)
            rows.append(
                {
                    "spot_name": spot["spot_name"],
                    "region": spot["region"],
                    "forecast_date": forecast_date.date(),
                    "avg_wave_height_m": wave_height,
                    "max_wave_height_m": round(wave_height + 0.35, 2),
                    "avg_wave_period_s": wave_period,
                    "avg_swell_wave_height_m": round(wave_height * 0.82, 2),
                    "avg_swell_wave_period_s": round(wave_period + 0.4, 1),
                    "avg_wind_speed_kmh": wind_speed,
                    "avg_wind_direction_deg": 260,
                    "modeled_surfable_day": int(
                        0.6 <= wave_height <= 2.0
                        and wave_period >= 7
                        and wind_speed <= 20
                    ),
                }
            )

    return pd.DataFrame(rows).sort_values(["forecast_date", "spot_name"], ascending=[False, True])


def _demo_spot_performance() -> pd.DataFrame:
    sessions = _demo_sessions()
    performance = (
        sessions.groupby(["spot_name", "region"], as_index=False)
        .agg(
            session_count=("session_id", "count"),
            avg_session_rating=("rating", "mean"),
            best_session_rating=("rating", "max"),
            avg_duration_minutes=("duration_minutes", "mean"),
            most_recent_session_date=("session_date", "max"),
        )
        .sort_values(["avg_session_rating", "session_count"], ascending=[False, False])
    )
    performance["avg_session_rating"] = performance["avg_session_rating"].round(2)
    performance["avg_duration_minutes"] = performance["avg_duration_minutes"].round(1)
    return performance


def _demo_forecast_quality() -> pd.DataFrame:
    sessions = _demo_sessions()
    conditions = _demo_daily_conditions()
    quality = sessions.merge(
        conditions,
        left_on=["spot_name", "session_date"],
        right_on=["spot_name", "forecast_date"],
        how="left",
        suffixes=("", "_forecast"),
    )
    quality["region"] = quality["region"].fillna(quality.get("region_forecast"))
    quality["high_quality_session"] = (quality["rating"] >= 4).astype(int)
    return quality[
        [
            "spot_name",
            "region",
            "session_date",
            "rating",
            "actual_wave_quality",
            "avg_wave_height_m",
            "max_wave_height_m",
            "avg_wave_period_s",
            "avg_swell_wave_height_m",
            "avg_swell_wave_period_s",
            "avg_wind_speed_kmh",
            "avg_wind_direction_deg",
            "modeled_surfable_day",
            "high_quality_session",
        ]
    ].sort_values(["session_date", "spot_name"], ascending=[False, True])


def _demo_forecast_lineage() -> pd.DataFrame:
    conditions = _demo_daily_conditions()
    lineage = (
        conditions.groupby("spot_name", as_index=False)
        .agg(
            daily_condition_rows=("forecast_date", "count"),
            first_forecast_date=("forecast_date", "min"),
            latest_forecast_date=("forecast_date", "max"),
        )
        .sort_values("spot_name")
    )
    lineage["raw_marine_rows"] = lineage["daily_condition_rows"] * 24
    lineage["raw_weather_rows"] = lineage["daily_condition_rows"] * 24
    return lineage[
        [
            "spot_name",
            "raw_marine_rows",
            "raw_weather_rows",
            "daily_condition_rows",
            "first_forecast_date",
            "latest_forecast_date",
        ]
    ]


def _demo_pipeline_runs() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "pipeline_name": "open_meteo_forecast_ingestion",
                "status": "demo",
                "rows_loaded": 1008,
                "message": "Demo mode uses generated forecast rows when PostgreSQL is unavailable.",
                "started_at": datetime(2026, 7, 21, 12, 0),
                "finished_at": datetime(2026, 7, 21, 12, 2),
            }
        ]
    )
