from __future__ import annotations

import csv
from pathlib import Path

from pipelines.db import ROOT_DIR, connect, ensure_schema


def seed_spots() -> int:
    path = ROOT_DIR / "data" / "sample_spots.csv"
    rows_loaded = 0
    with connect() as conn, conn.cursor() as cur, path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            cur.execute(
                """
                INSERT INTO surf_spots (
                    spot_slug,
                    spot_name,
                    region,
                    latitude,
                    longitude,
                    preferred_wind_direction,
                    notes
                )
                VALUES (
                    %(spot_slug)s,
                    %(spot_name)s,
                    %(region)s,
                    %(latitude)s,
                    %(longitude)s,
                    %(preferred_wind_direction)s,
                    %(notes)s
                )
                ON CONFLICT (spot_slug) DO UPDATE SET
                    spot_name = EXCLUDED.spot_name,
                    region = EXCLUDED.region,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    preferred_wind_direction = EXCLUDED.preferred_wind_direction,
                    notes = EXCLUDED.notes
                """,
                row,
            )
            rows_loaded += 1
        conn.commit()
    return rows_loaded


def seed_sessions() -> int:
    path = ROOT_DIR / "data" / "sample_sessions.csv"
    rows_loaded = 0
    with connect() as conn, conn.cursor() as cur, path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            cur.execute(
                "SELECT spot_id FROM surf_spots WHERE spot_slug = %s",
                (row["spot_slug"],),
            )
            spot_id = cur.fetchone()[0]
            cur.execute(
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
                SELECT
                    %(spot_id)s,
                    %(session_date)s,
                    %(start_time)s,
                    %(duration_minutes)s,
                    %(rating)s,
                    %(crowd_level)s,
                    %(board)s,
                    %(actual_wave_quality)s,
                    %(notes)s
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM surf_sessions
                    WHERE spot_id = %(spot_id)s
                      AND session_date = %(session_date)s
                      AND start_time = %(start_time)s
                      AND notes = %(notes)s
                )
                """,
                {**row, "spot_id": spot_id},
            )
            rows_loaded += cur.rowcount
        conn.commit()
    return rows_loaded


def main() -> None:
    ensure_schema()
    spots = seed_spots()
    sessions = seed_sessions()
    print(f"Seed complete: {spots} spots processed, {sessions} sessions inserted.")


if __name__ == "__main__":
    main()
