from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
from sqlalchemy import create_engine

from pipelines.db import connect, database_url

QueryParams = Sequence[object] | None


def read_query(sql: str, params: QueryParams = None) -> pd.DataFrame:
    """Read a SQL query into a dataframe using the project warehouse."""
    engine = create_engine(database_url())
    with engine.connect() as conn:
        return pd.read_sql(sql, conn, params=params)


def execute_query(sql: str, params: QueryParams = None) -> None:
    """Run a write query against the project warehouse."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        conn.commit()


def read_sessions() -> pd.DataFrame:
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


def read_spots() -> pd.DataFrame:
    return read_query(
        """
        SELECT spot_id, spot_name, region
        FROM surf_spots
        ORDER BY spot_name
        """
    )


def read_spot_performance() -> pd.DataFrame:
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


def read_forecast_quality() -> pd.DataFrame:
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


def read_daily_conditions() -> pd.DataFrame:
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


def read_pipeline_runs() -> pd.DataFrame:
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
