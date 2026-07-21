from __future__ import annotations

from prefect import flow, task

from pipelines.ingest_open_meteo import ingest_open_meteo
from pipelines.seed import seed_sessions, seed_spots


@task
def load_seed_data() -> dict[str, int]:
    return {
        "spots": seed_spots(),
        "sessions": seed_sessions(),
    }


@task
def load_forecast_data() -> int:
    return ingest_open_meteo()


@flow(name="surf-session-warehouse-daily-load")
def daily_load() -> dict[str, int]:
    seed_counts = load_seed_data()
    forecast_rows = load_forecast_data()
    return {
        **seed_counts,
        "forecast_rows": forecast_rows,
    }


if __name__ == "__main__":
    result = daily_load()
    print(result)

