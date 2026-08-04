#!/usr/bin/env python3
"""Compare Open-Meteo modeled surf conditions with NOAA/NDBC observations.

This script fetches recent NDBC buoy observations and Open-Meteo hourly marine
and weather fields for the sample surf spots. It reports only metrics with
matched timestamps and measured NOAA values.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
EVALUATION_DIR = ROOT_DIR / "evaluation"
SUMMARY_PATH = EVALUATION_DIR / "noaa_forecast_agreement_results.json"
MATCHES_PATH = EVALUATION_DIR / "noaa_forecast_agreement_matches.csv"

NDBC_REALTIME_URL = "https://www.ndbc.noaa.gov/data/realtime2/{station_id}.txt"
OPEN_METEO_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
OPEN_METEO_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# Station choices are nearest practical NDBC wave stations for this demo region.
# The script falls back if a station is reachable but missing wave observations.
SPOT_STATION_CANDIDATES = {
    "strathmere-nj": ["44091", "44065", "44025"],
    "ocean-city-nj": ["44091", "44065", "44025"],
    "indian-river-de": ["44009", "44091", "44065"],
}


def fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "surf-session-warehouse-evaluation/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def fetch_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    query = urllib.parse.urlencode(params, doseq=True)
    request = urllib.request.Request(
        f"{url}?{query}",
        headers={"User-Agent": "surf-session-warehouse-evaluation/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_float(value: str) -> float | None:
    if value in {"MM", "", "NaN"}:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    if math.isnan(number):
        return None
    return number


def parse_ndbc_realtime(station_id: str) -> list[dict[str, Any]]:
    text = fetch_text(NDBC_REALTIME_URL.format(station_id=station_id))
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 12:
            continue
        try:
            observed_at = datetime(
                int(parts[0]),
                int(parts[1]),
                int(parts[2]),
                int(parts[3]),
                int(parts[4]),
                tzinfo=timezone.utc,
            )
        except ValueError:
            continue
        rows.append(
            {
                "station_id": station_id,
                "observed_at": observed_at,
                "wind_direction_deg": parse_float(parts[5]),
                "wind_speed_ms": parse_float(parts[6]),
                "wave_height_m": parse_float(parts[8]),
                "dominant_wave_period_s": parse_float(parts[9]),
                "average_wave_period_s": parse_float(parts[10]),
                "mean_wave_direction_deg": parse_float(parts[11]),
            }
        )
    return rows


def read_spots() -> list[dict[str, Any]]:
    with (ROOT_DIR / "data" / "sample_spots.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def hourly_records(payload: dict[str, Any], fields: list[str]) -> dict[datetime, dict[str, Any]]:
    hourly = payload.get("hourly", {})
    times = hourly.get("time", []) if isinstance(hourly, dict) else []
    records: dict[datetime, dict[str, Any]] = {}
    for index, timestamp in enumerate(times):
        if not isinstance(timestamp, str):
            continue
        try:
            timestamp_utc = datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        record: dict[str, Any] = {"modeled_at": timestamp_utc}
        for field in fields:
            values = hourly.get(field)
            if isinstance(values, list) and index < len(values):
                record[field] = values[index]
            else:
                record[field] = None
        records[timestamp_utc] = record
    return records


def fetch_open_meteo_records(spot: dict[str, Any]) -> dict[datetime, dict[str, Any]]:
    lat = float(spot["latitude"])
    lon = float(spot["longitude"])
    marine = fetch_json(
        OPEN_METEO_MARINE_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "hourly": ["wave_height", "wave_period"],
            "timezone": "UTC",
            "past_days": 1,
            "forecast_days": 1,
        },
    )
    weather = fetch_json(
        OPEN_METEO_WEATHER_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "hourly": ["wind_speed_10m", "wind_direction_10m"],
            "timezone": "UTC",
            "past_days": 1,
            "forecast_days": 1,
        },
    )

    marine_records = hourly_records(marine, ["wave_height", "wave_period"])
    weather_records = hourly_records(weather, ["wind_speed_10m", "wind_direction_10m"])
    merged: dict[datetime, dict[str, Any]] = {}
    for timestamp in sorted(set(marine_records) | set(weather_records)):
        merged[timestamp] = {
            **marine_records.get(timestamp, {"modeled_at": timestamp}),
            **weather_records.get(timestamp, {"modeled_at": timestamp}),
        }
    return merged


def nearest_hour(timestamp: datetime) -> datetime:
    base = timestamp.replace(minute=0, second=0, microsecond=0)
    if timestamp.minute >= 30:
        base = base.replace(hour=base.hour + 1) if base.hour < 23 else base
    return base


def abs_error(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return abs(a - b)


def circular_abs_error_deg(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    diff = abs((a - b + 180) % 360 - 180)
    return diff


def wave_surfable(row: dict[str, Any], height_key: str, period_key: str) -> bool | None:
    height = row.get(height_key)
    period = row.get(period_key)
    if height is None or period is None:
        return None
    return 0.6 <= float(height) <= 2.0 and float(period) >= 7.0


def mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def rmse(values: list[float]) -> float | None:
    return math.sqrt(statistics.fmean([value * value for value in values])) if values else None


def summarize_errors(matches: list[dict[str, Any]], error_key: str) -> dict[str, Any]:
    values = [float(row[error_key]) for row in matches if row.get(error_key) is not None]
    return {
        "matched_records": len(values),
        "mean_absolute_error": mean(values),
        "median_absolute_error": median(values),
        "rmse": rmse(values),
        "min_absolute_error": min(values) if values else None,
        "max_absolute_error": max(values) if values else None,
    }


def evaluate() -> dict[str, Any]:
    EVALUATION_DIR.mkdir(exist_ok=True)
    spots = read_spots()
    all_matches: list[dict[str, Any]] = []
    station_status: dict[str, Any] = {}

    for spot in spots:
        modeled = fetch_open_meteo_records(spot)
        station_candidates = SPOT_STATION_CANDIDATES.get(spot["spot_slug"], [])
        selected_station = None
        observations: list[dict[str, Any]] = []
        for station_id in station_candidates:
            rows = parse_ndbc_realtime(station_id)
            wave_rows = [row for row in rows if row["wave_height_m"] is not None]
            station_status[f"{spot['spot_slug']}:{station_id}"] = {
                "rows": len(rows),
                "rows_with_wave_height": len(wave_rows),
            }
            if wave_rows:
                selected_station = station_id
                observations = wave_rows
                break

        if selected_station is None:
            continue

        for observation in observations:
            modeled_at = nearest_hour(observation["observed_at"])
            modeled_row = modeled.get(modeled_at)
            if not modeled_row:
                continue
            observed_period = (
                observation["dominant_wave_period_s"]
                if observation["dominant_wave_period_s"] is not None
                else observation["average_wave_period_s"]
            )
            modeled_wave_height = parse_float(str(modeled_row.get("wave_height")))
            modeled_wave_period = parse_float(str(modeled_row.get("wave_period")))
            modeled_wind_speed = parse_float(str(modeled_row.get("wind_speed_10m")))
            modeled_wind_dir = parse_float(str(modeled_row.get("wind_direction_10m")))
            observed_wind_speed_kmh = (
                observation["wind_speed_ms"] * 3.6
                if observation["wind_speed_ms"] is not None
                else None
            )

            match = {
                "spot_slug": spot["spot_slug"],
                "spot_name": spot["spot_name"],
                "station_id": selected_station,
                "observed_at": observation["observed_at"].isoformat(),
                "modeled_at": modeled_at.isoformat(),
                "observed_wave_height_m": observation["wave_height_m"],
                "modeled_wave_height_m": modeled_wave_height,
                "wave_height_abs_error_m": abs_error(
                    observation["wave_height_m"],
                    modeled_wave_height,
                ),
                "observed_wave_period_s": observed_period,
                "modeled_wave_period_s": modeled_wave_period,
                "wave_period_abs_error_s": abs_error(observed_period, modeled_wave_period),
                "observed_wind_speed_kmh": observed_wind_speed_kmh,
                "modeled_wind_speed_kmh": modeled_wind_speed,
                "wind_speed_abs_error_kmh": abs_error(
                    observed_wind_speed_kmh,
                    modeled_wind_speed,
                ),
                "observed_wind_direction_deg": observation["wind_direction_deg"],
                "modeled_wind_direction_deg": modeled_wind_dir,
                "wind_direction_abs_error_deg": circular_abs_error_deg(
                    observation["wind_direction_deg"],
                    modeled_wind_dir,
                ),
            }
            observed_surfable = wave_surfable(
                {
                    "height": observation["wave_height_m"],
                    "period": observed_period,
                },
                "height",
                "period",
            )
            modeled_surfable = wave_surfable(
                {
                    "height": modeled_wave_height,
                    "period": modeled_wave_period,
                },
                "height",
                "period",
            )
            match["observed_wave_surfable"] = observed_surfable
            match["modeled_wave_surfable"] = modeled_surfable
            match["wave_surfable_match"] = (
                observed_surfable == modeled_surfable
                if observed_surfable is not None and modeled_surfable is not None
                else None
            )
            all_matches.append(match)

    fieldnames = [
        "spot_slug",
        "spot_name",
        "station_id",
        "observed_at",
        "modeled_at",
        "observed_wave_height_m",
        "modeled_wave_height_m",
        "wave_height_abs_error_m",
        "observed_wave_period_s",
        "modeled_wave_period_s",
        "wave_period_abs_error_s",
        "observed_wind_speed_kmh",
        "modeled_wind_speed_kmh",
        "wind_speed_abs_error_kmh",
        "observed_wind_direction_deg",
        "modeled_wind_direction_deg",
        "wind_direction_abs_error_deg",
        "observed_wave_surfable",
        "modeled_wave_surfable",
        "wave_surfable_match",
    ]
    with MATCHES_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_matches)

    surfable_rows = [
        row
        for row in all_matches
        if row.get("wave_surfable_match") is not None
    ]
    surfable_matches = sum(1 for row in surfable_rows if row["wave_surfable_match"])
    by_spot: dict[str, int] = defaultdict(int)
    for row in all_matches:
        by_spot[row["spot_slug"]] += 1

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "ndbc_realtime": "https://www.ndbc.noaa.gov/data/realtime2/{station_id}.txt",
            "open_meteo_marine": OPEN_METEO_MARINE_URL,
            "open_meteo_weather": OPEN_METEO_WEATHER_URL,
        },
        "station_candidates": SPOT_STATION_CANDIDATES,
        "station_status": station_status,
        "matching_rule": "NDBC observation matched to nearest Open-Meteo hourly timestamp for the same sample surf spot.",
        "matched_records": len(all_matches),
        "matched_records_by_spot": dict(by_spot),
        "wave_height_m": summarize_errors(all_matches, "wave_height_abs_error_m"),
        "wave_period_s": summarize_errors(all_matches, "wave_period_abs_error_s"),
        "wind_speed_kmh": summarize_errors(all_matches, "wind_speed_abs_error_kmh"),
        "wind_direction_deg": summarize_errors(all_matches, "wind_direction_abs_error_deg"),
        "wave_surfable_agreement": {
            "matched_records": len(surfable_rows),
            "matches": surfable_matches,
            "agreement_rate": (surfable_matches / len(surfable_rows)) if surfable_rows else None,
            "definition": "Wave-only surfable is true when wave height is 0.6-2.0 m and wave period is at least 7 s.",
        },
        "limitations": [
            "NDBC stations are offshore observation points and may not exactly represent beach-break conditions at each sample spot.",
            "Open-Meteo past-day values from the forecast endpoints are modeled hourly fields, not independent observed ground truth.",
            "Metrics are only reported for rows where NOAA observations and Open-Meteo modeled timestamps could be matched.",
            "Wave-quality accuracy against human surf-session labels is not measured by this script.",
        ],
        "matches_csv": str(MATCHES_PATH.relative_to(ROOT_DIR)),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    print(json.dumps(evaluate(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
