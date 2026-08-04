#!/usr/bin/env python3
"""Evaluate Surf Session Warehouse without inventing metrics.

The script has two layers:
1. Always-on repository evaluation using files that are committed to the repo.
2. Optional live database/pipeline checks when PostgreSQL, dbt, and dependencies
   are available.

All unavailable metrics are recorded explicitly instead of estimated.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
EVALUATION_DIR = ROOT_DIR / "evaluation"
RESULTS_PATH = EVALUATION_DIR / "results.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def duplicate_rate(rows: list[dict[str, str]], key_fields: list[str]) -> dict[str, Any]:
    if not rows:
        return {"duplicate_rows": 0, "total_rows": 0, "duplicate_rate": None}
    keys = [tuple(row.get(field, "") for field in key_fields) for row in rows]
    counts = Counter(keys)
    duplicate_rows = sum(count - 1 for count in counts.values() if count > 1)
    return {
        "key_fields": key_fields,
        "duplicate_rows": duplicate_rows,
        "total_rows": len(rows),
        "duplicate_rate": duplicate_rows / len(rows),
    }


def null_rates(rows: list[dict[str, str]], required_fields: list[str]) -> dict[str, Any]:
    rates: dict[str, Any] = {}
    for field in required_fields:
        null_count = sum(1 for row in rows if row.get(field) in (None, ""))
        rates[field] = {
            "null_count": null_count,
            "total_rows": len(rows),
            "null_rate": (null_count / len(rows)) if rows else None,
        }
    return rates


def stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "trials": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "stddev": None,
        }
    return {
        "trials": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "stddev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def run_command(
    command: list[str],
    cwd: Path,
    timeout_seconds: int,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        elapsed = time.perf_counter() - started
        return {
            "command": command,
            "cwd": str(cwd),
            "timeout_seconds": timeout_seconds,
            "returncode": completed.returncode,
            "runtime_seconds": elapsed,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - started
        return {
            "command": command,
            "cwd": str(cwd),
            "timeout_seconds": timeout_seconds,
            "returncode": None,
            "runtime_seconds": elapsed,
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            "timed_out": True,
        }


def evaluate_repository() -> dict[str, Any]:
    excluded_parts = {
        ".git",
        ".venv",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        "logs",
        "target",
    }
    files = {
        path.relative_to(ROOT_DIR).as_posix()
        for path in ROOT_DIR.rglob("*")
        if path.is_file()
        and not (set(path.relative_to(ROOT_DIR).parts) & excluded_parts)
        and not any(part.startswith(".venv") for part in path.relative_to(ROOT_DIR).parts)
    }
    project_type = "surf_session_warehouse"
    if any(path.startswith("warehouse/") for path in files) and "pipelines/ingest_open_meteo.py" in files:
        project_type = "surf_session_warehouse"
    elif any("opencv" in path.lower() for path in files):
        project_type = "wave_vision"

    spots = read_csv(ROOT_DIR / "data" / "sample_spots.csv")
    sessions = read_csv(ROOT_DIR / "data" / "sample_sessions.csv")
    model_files = sorted((ROOT_DIR / "warehouse" / "models").rglob("*.sql"))
    staging_models = [path for path in model_files if "/staging/" in path.as_posix()]
    mart_models = [path for path in model_files if "/marts/" in path.as_posix()]

    schema_text = (ROOT_DIR / "warehouse" / "models" / "schema.yml").read_text()
    data_quality_checks = len(
        re.findall(r"^\s*-\s+(not_null|unique|accepted_values):?", schema_text, re.MULTILINE)
    )

    return {
        "project_type": project_type,
        "repository_files": len(files),
        "sample_data": {
            "surf_spots": {
                "rows": len(spots),
                "duplicate_rate": duplicate_rate(spots, ["spot_slug"]),
                "required_field_null_rates": null_rates(
                    spots,
                    ["spot_slug", "spot_name", "region", "latitude", "longitude"],
                ),
            },
            "surf_sessions": {
                "rows": len(sessions),
                "duplicate_rate": duplicate_rate(
                    sessions,
                    ["spot_slug", "session_date", "start_time", "notes"],
                ),
                "required_field_null_rates": null_rates(
                    sessions,
                    ["spot_slug", "session_date", "duration_minutes", "rating"],
                ),
                "rating_distribution": dict(Counter(row["rating"] for row in sessions)),
            },
        },
        "dbt_static": {
            "transformation_model_count": len(model_files),
            "staging_model_count": len(staging_models),
            "mart_model_count": len(mart_models),
            "model_files": [path.relative_to(ROOT_DIR).as_posix() for path in model_files],
            "declared_data_quality_check_count": data_quality_checks,
        },
    }


def evaluate_dbt_artifacts() -> dict[str, Any]:
    run_results_path = ROOT_DIR / "warehouse" / "target" / "run_results.json"
    if not run_results_path.exists():
        return {"available": False, "reason": "warehouse/target/run_results.json not found"}

    data = json.loads(run_results_path.read_text())
    results = data.get("results", [])
    statuses = Counter(result.get("status") for result in results)
    model_results = [
        result
        for result in results
        if str(result.get("unique_id", "")).startswith("model.")
    ]
    test_results = [
        result
        for result in results
        if str(result.get("unique_id", "")).startswith("test.")
    ]

    rows_affected: dict[str, int] = {}
    for result in model_results:
        relation_name = str(result.get("relation_name") or result.get("unique_id"))
        model_name = str(result.get("unique_id", "")).split(".")[-1]
        adapter_response = result.get("adapter_response") or {}
        rows = adapter_response.get("rows_affected")
        if isinstance(rows, int) and rows >= 0:
            rows_affected[model_name or relation_name] = rows

    test_passes = sum(1 for result in test_results if result.get("status") == "pass")
    test_total = len(test_results)
    return {
        "available": True,
        "generated_at": data.get("metadata", {}).get("generated_at"),
        "dbt_version": data.get("metadata", {}).get("dbt_version"),
        "invocation_command": data.get("args", {}).get("invocation_command"),
        "elapsed_time_seconds": data.get("elapsed_time"),
        "resource_status_counts": dict(statuses),
        "model_count": len(model_results),
        "successful_model_count": sum(1 for result in model_results if result.get("status") == "success"),
        "test_count": test_total,
        "test_pass_count": test_passes,
        "test_pass_rate": (test_passes / test_total) if test_total else None,
        "model_rows_affected": rows_affected,
        "resource_execution_time_seconds": stats(
            [
                float(result["execution_time"])
                for result in results
                if isinstance(result.get("execution_time"), (int, float))
            ]
        ),
    }


def run_compileall_trials(trials: int) -> dict[str, Any]:
    runtimes: list[float] = []
    trial_results: list[dict[str, Any]] = []
    for _ in range(trials):
        result = run_command(
            [sys.executable, "-m", "compileall", "-q", "app", "pipelines", "evaluation"],
            ROOT_DIR,
            timeout_seconds=30,
        )
        trial_results.append(result)
        if result["returncode"] == 0 and not result["timed_out"]:
            runtimes.append(float(result["runtime_seconds"]))
    return {
        "description": "Python syntax compilation for app, pipelines, and evaluation code.",
        "runtime_seconds": stats(runtimes),
        "successful_trials": len(runtimes),
        "failed_trials": trials - len(runtimes),
        "trials": trial_results,
    }


def check_docker() -> dict[str, Any]:
    result = run_command(["docker", "compose", "ps"], ROOT_DIR, timeout_seconds=10)
    return {
        "available": result["returncode"] == 0,
        "check": result,
    }


def check_database(python_executable: str) -> dict[str, Any]:
    code = """
import json
import os
import time

started = time.perf_counter()
try:
    import psycopg
    url = os.getenv("DATABASE_URL") or "postgresql://surf:surf@localhost:5432/surf_warehouse?connect_timeout=3"
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("select current_database(), current_user")
        row = cur.fetchone()
    print(json.dumps({"available": True, "row": row, "runtime_seconds": time.perf_counter() - started}))
except Exception as exc:
    print(json.dumps({"available": False, "error_type": type(exc).__name__, "error": str(exc), "runtime_seconds": time.perf_counter() - started}))
"""
    result = run_command(
        [python_executable, "-c", code],
        ROOT_DIR,
        timeout_seconds=12,
    )
    parsed: dict[str, Any] | None = None
    if result["stdout_tail"].strip():
        try:
            parsed = json.loads(result["stdout_tail"].strip().splitlines()[-1])
        except json.JSONDecodeError:
            parsed = None
    return {
        "available": bool(parsed and parsed.get("available")),
        "parsed": parsed,
        "check": result,
    }


def run_database_metrics(python_executable: str, query_trials: int) -> dict[str, Any]:
    code = f"""
import json
import os
import statistics
import time

import psycopg

url = os.getenv("DATABASE_URL") or "postgresql://surf:surf@localhost:5432/surf_warehouse?connect_timeout=3"
queries = {{
    "raw_marine_rows": "select count(*) from raw_marine_forecasts",
    "raw_weather_rows": "select count(*) from raw_weather_forecasts",
    "surf_spots": "select count(*) from surf_spots",
    "surf_sessions": "select count(*) from surf_sessions",
    "daily_condition_rows": "select count(*) from analytics.fct_daily_spot_conditions",
    "spot_performance_rows": "select count(*) from analytics.mart_spot_performance",
    "forecast_vs_session_rows": "select count(*) from analytics.mart_forecast_vs_session_quality",
    "matched_session_rows": "select count(*) from analytics.mart_forecast_vs_session_quality where avg_wave_height_m is not null",
    "raw_marine_duplicate_rows": "select coalesce(sum(n - 1), 0) from (select count(*) n from raw_marine_forecasts group by spot_id, forecast_time, source having count(*) > 1) d",
    "raw_weather_duplicate_rows": "select coalesce(sum(n - 1), 0) from (select count(*) n from raw_weather_forecasts group by spot_id, forecast_time, source having count(*) > 1) d",
    "pipeline_success_runs": "select count(*) from pipeline_runs where status = 'success'",
    "pipeline_failed_runs": "select count(*) from pipeline_runs where status = 'failed'",
    "pipeline_total_runs": "select count(*) from pipeline_runs where status in ('success', 'failed')",
}}

counts = {{}}
timings = {{}}
with psycopg.connect(url) as conn, conn.cursor() as cur:
    for name, sql in queries.items():
        durations = []
        value = None
        for _ in range({query_trials}):
            started = time.perf_counter()
            cur.execute(sql)
            value = cur.fetchone()[0]
            durations.append(time.perf_counter() - started)
        counts[name] = int(value)
        timings[name] = {{
            "trials": len(durations),
            "mean": statistics.fmean(durations),
            "median": statistics.median(durations),
            "min": min(durations),
            "max": max(durations),
            "stddev": statistics.stdev(durations) if len(durations) > 1 else 0.0,
        }}

print(json.dumps({{"counts": counts, "query_runtime_seconds": timings}}, default=str))
"""
    result = run_command([python_executable, "-c", code], ROOT_DIR, timeout_seconds=30)
    parsed = None
    if result["stdout_tail"].strip():
        try:
            parsed = json.loads(result["stdout_tail"].strip().splitlines()[-1])
        except json.JSONDecodeError:
            parsed = None
    return {
        "available": result["returncode"] == 0 and parsed is not None,
        "parsed": parsed,
        "check": result,
    }


def run_live_dbt_build_trials(python_executable: str, trials: int) -> dict[str, Any]:
    dbt_path = str(Path(python_executable).parent / "dbt")
    runtimes: list[float] = []
    trial_results: list[dict[str, Any]] = []
    env = os.environ.copy()
    env.setdefault("POSTGRES_HOST", "localhost")
    env.setdefault("POSTGRES_PORT", "5432")
    env.setdefault("POSTGRES_DB", "surf_warehouse")
    env.setdefault("POSTGRES_USER", "surf")
    env.setdefault("POSTGRES_PASSWORD", "surf")

    for _ in range(trials):
        result = run_command(
            [dbt_path, "build", "--profiles-dir", "."],
            ROOT_DIR / "warehouse",
            timeout_seconds=180,
            env=env,
        )
        trial_results.append(result)
        if result["returncode"] == 0 and not result["timed_out"]:
            runtimes.append(float(result["runtime_seconds"]))

    return {
        "runtime_seconds": stats(runtimes),
        "successful_trials": len(runtimes),
        "failed_trials": trials - len(runtimes),
        "trials": trial_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--query-trials", type=int, default=5)
    parser.add_argument("--python", default=str(ROOT_DIR / ".venv" / "bin" / "python"))
    parser.add_argument("--run-dbt-build", action="store_true")
    args = parser.parse_args()

    EVALUATION_DIR.mkdir(exist_ok=True)
    results: dict[str, Any] = {
        "generated_at": now_utc(),
        "repo": str(ROOT_DIR),
        "commands": {
            "evaluation": f"python3 evaluation/evaluate_surf_session_warehouse.py --trials {args.trials}",
            "optional_live_dbt": (
                f"python3 evaluation/evaluate_surf_session_warehouse.py --trials {args.trials} "
                "--run-dbt-build"
            ),
        },
        "repository": evaluate_repository(),
        "dbt_artifact": evaluate_dbt_artifacts(),
        "compileall_benchmark": run_compileall_trials(args.trials),
        "docker": check_docker(),
        "database": check_database(args.python),
    }

    if results["database"]["available"]:
        results["database_metrics"] = run_database_metrics(args.python, args.query_trials)
    else:
        results["database_metrics"] = {
            "available": False,
            "reason": "Database check did not succeed; live database metrics were not run.",
        }

    if args.run_dbt_build:
        results["live_dbt_build"] = run_live_dbt_build_trials(args.python, args.trials)
    else:
        results["live_dbt_build"] = {
            "available": False,
            "reason": "Not requested. Use --run-dbt-build when PostgreSQL and dbt are available.",
        }

    RESULTS_PATH.write_text(json.dumps(results, indent=2, sort_keys=True))
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
