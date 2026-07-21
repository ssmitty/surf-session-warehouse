from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict

import requests

from pipelines.db import connect, ensure_schema

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


class SurfSpot(TypedDict):
    spot_id: int
    spot_slug: str
    spot_name: str
    latitude: float
    longitude: float


def start_pipeline_run(name: str) -> int:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pipeline_runs (pipeline_name, status)
            VALUES (%s, 'started')
            RETURNING run_id
            """,
            (name,),
        )
        run_id = cur.fetchone()[0]
        conn.commit()
    return run_id


def finish_pipeline_run(
    run_id: int,
    status: str,
    rows_loaded: int,
    message: str | None = None,
) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE pipeline_runs
            SET status = %s,
                rows_loaded = %s,
                message = %s,
                finished_at = NOW()
            WHERE run_id = %s
            """,
            (status, rows_loaded, message, run_id),
        )
        conn.commit()


def get_spots() -> list[SurfSpot]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT spot_id, spot_slug, spot_name, latitude, longitude
            FROM surf_spots
            ORDER BY spot_name
            """
        )
        return [
            {
                "spot_id": row[0],
                "spot_slug": row[1],
                "spot_name": row[2],
                "latitude": float(row[3]),
                "longitude": float(row[4]),
            }
            for row in cur.fetchall()
        ]


def fetch_json(url: str, params: dict[str, object]) -> dict[str, object]:
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def list_value(values: object, index: int) -> object | None:
    if not isinstance(values, list):
        return None
    if values is None or index >= len(values):
        return None
    return values[index]


def load_marine_forecast(spot: SurfSpot) -> int:
    payload = fetch_json(
        MARINE_URL,
        {
            "latitude": spot["latitude"],
            "longitude": spot["longitude"],
            "hourly": [
                "wave_height",
                "wave_period",
                "wind_wave_height",
                "swell_wave_height",
                "swell_wave_period",
                "swell_wave_direction",
            ],
            "timezone": "UTC",
            "forecast_days": 7,
        },
    )
    hourly = payload.get("hourly", {})
    if not isinstance(hourly, dict):
        return 0
    times = hourly.get("time", [])
    if not isinstance(times, list):
        return 0
    rows_loaded = 0

    with connect() as conn, conn.cursor() as cur:
        for index, timestamp in enumerate(times):
            if not isinstance(timestamp, str):
                continue
            forecast_time = datetime.fromisoformat(timestamp).replace(
                tzinfo=timezone.utc
            )
            cur.execute(
                """
                INSERT INTO raw_marine_forecasts (
                    spot_id, forecast_time, wave_height_m, wave_period_s,
                    wind_wave_height_m, swell_wave_height_m, swell_wave_period_s,
                    swell_wave_direction_deg
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (spot_id, forecast_time, source) DO UPDATE SET
                    wave_height_m = EXCLUDED.wave_height_m,
                    wave_period_s = EXCLUDED.wave_period_s,
                    wind_wave_height_m = EXCLUDED.wind_wave_height_m,
                    swell_wave_height_m = EXCLUDED.swell_wave_height_m,
                    swell_wave_period_s = EXCLUDED.swell_wave_period_s,
                    swell_wave_direction_deg = EXCLUDED.swell_wave_direction_deg,
                    loaded_at = NOW()
                """,
                (
                    spot["spot_id"],
                    forecast_time,
                    list_value(hourly.get("wave_height"), index),
                    list_value(hourly.get("wave_period"), index),
                    list_value(hourly.get("wind_wave_height"), index),
                    list_value(hourly.get("swell_wave_height"), index),
                    list_value(hourly.get("swell_wave_period"), index),
                    list_value(hourly.get("swell_wave_direction"), index),
                ),
            )
            rows_loaded += 1
        conn.commit()
    return rows_loaded


def load_weather_forecast(spot: SurfSpot) -> int:
    payload = fetch_json(
        WEATHER_URL,
        {
            "latitude": spot["latitude"],
            "longitude": spot["longitude"],
            "hourly": [
                "temperature_2m",
                "wind_speed_10m",
                "wind_direction_10m",
                "precipitation",
            ],
            "timezone": "UTC",
            "forecast_days": 7,
        },
    )
    hourly = payload.get("hourly", {})
    if not isinstance(hourly, dict):
        return 0
    times = hourly.get("time", [])
    if not isinstance(times, list):
        return 0
    rows_loaded = 0

    with connect() as conn, conn.cursor() as cur:
        for index, timestamp in enumerate(times):
            if not isinstance(timestamp, str):
                continue
            forecast_time = datetime.fromisoformat(timestamp).replace(
                tzinfo=timezone.utc
            )
            cur.execute(
                """
                INSERT INTO raw_weather_forecasts (
                    spot_id, forecast_time, temperature_c, wind_speed_kmh,
                    wind_direction_deg, precipitation_mm
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (spot_id, forecast_time, source) DO UPDATE SET
                    temperature_c = EXCLUDED.temperature_c,
                    wind_speed_kmh = EXCLUDED.wind_speed_kmh,
                    wind_direction_deg = EXCLUDED.wind_direction_deg,
                    precipitation_mm = EXCLUDED.precipitation_mm,
                    loaded_at = NOW()
                """,
                (
                    spot["spot_id"],
                    forecast_time,
                    list_value(hourly.get("temperature_2m"), index),
                    list_value(hourly.get("wind_speed_10m"), index),
                    list_value(hourly.get("wind_direction_10m"), index),
                    list_value(hourly.get("precipitation"), index),
                ),
            )
            rows_loaded += 1
        conn.commit()
    return rows_loaded


def ingest_open_meteo() -> int:
    ensure_schema()
    run_id = start_pipeline_run("open_meteo_forecast_ingestion")
    rows_loaded = 0
    try:
        for spot in get_spots():
            rows_loaded += load_marine_forecast(spot)
            rows_loaded += load_weather_forecast(spot)
        finish_pipeline_run(
            run_id,
            "success",
            rows_loaded,
            "Forecast ingestion completed.",
        )
        return rows_loaded
    except Exception as exc:
        finish_pipeline_run(run_id, "failed", rows_loaded, str(exc))
        raise


def main() -> None:
    rows_loaded = ingest_open_meteo()
    print(f"Open-Meteo ingestion complete: {rows_loaded} forecast rows processed.")


if __name__ == "__main__":
    main()
