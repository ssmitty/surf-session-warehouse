# Surf Session Warehouse Evaluation Report

Generated from `evaluation/results.json` on 2026-08-04.

## Verified Metrics

- Repository classified as Surf Session Warehouse from dbt, PostgreSQL, Open-Meteo ingestion, Prefect, and Streamlit project contents.
- Evaluated 41 project files, excluding local virtual environments, caches, logs, git metadata, and generated dbt targets.
- Source sample data contains 3 surf spots and 4 surf sessions.
- Sample spot data had 0 duplicate `spot_slug` rows across 3 rows.
- Sample session data had 0 duplicate natural-key rows across 4 rows.
- Required-field null rate was 0.0% for checked spot fields: `spot_slug`, `spot_name`, `region`, `latitude`, `longitude`.
- Required-field null rate was 0.0% for checked session fields: `spot_slug`, `session_date`, `duration_minutes`, `rating`.
- Repository contains 8 dbt transformation models: 4 staging models and 4 mart/fact models.
- Repository declares 14 dbt data-quality checks in `warehouse/models/schema.yml`.
- Existing dbt artifact at `warehouse/target/run_results.json` recorded 8 successful model builds and 14 passing dbt tests.
- Existing dbt artifact recorded a 100.0% dbt test pass rate, based on 14 passed tests out of 14 tests.
- Existing dbt artifact recorded 68.93 seconds elapsed for `dbt build --profiles-dir .` on 2026-07-21.
- Existing dbt artifact recorded these produced model row counts:
  - `fct_daily_spot_conditions`: 21 rows
  - `fct_surf_sessions`: 4 rows
  - `mart_forecast_vs_session_quality`: 4 rows
  - `mart_spot_performance`: 3 rows
- Python syntax compilation for `app`, `pipelines`, and `evaluation` succeeded in 5 out of 5 trials.
- Python syntax compilation runtime across 5 trials:
  - Mean: 0.0440 seconds
  - Median: 0.0360 seconds
  - Minimum: 0.0352 seconds
  - Maximum: 0.0765 seconds
  - Standard deviation: 0.0182 seconds

## Methodology

The evaluation script uses only repository files, committed sample CSVs, dbt SQL/YAML files, and existing dbt run artifacts unless live services are available. It writes all measurements to `evaluation/results.json`.

The script checks Docker and PostgreSQL availability before attempting database-backed metrics. If a live dependency is unavailable or times out, the metric is marked unavailable rather than estimated.

## Reproduction Commands

Run the current evaluation:

```bash
python3 evaluation/evaluate_surf_session_warehouse.py --trials 5
```

Run live dbt timing after Docker/PostgreSQL and dependencies are healthy:

```bash
docker compose up -d postgres
source .venv/bin/activate
python -m pipelines.seed
python -m pipelines.ingest_open_meteo
python3 evaluation/evaluate_surf_session_warehouse.py --trials 5 --run-dbt-build
```

Run dbt directly:

```bash
cd warehouse
dbt build --profiles-dir .
```

## Caveats

- Docker was not available during this run. The Docker check returned: `Cannot connect to the Docker daemon at unix:///Users/sean/.orbstack/run/docker.sock. Is the docker daemon running?`
- The current `.venv` timed out while importing or checking `psycopg`, so live PostgreSQL metrics, ingestion runtime, dashboard query runtime, duplicate rates in raw forecast tables, and pipeline run success rate were not measured in this run.
- The dbt build timing and row counts come from the existing dbt artifact generated on 2026-07-21, not from a fresh live database run on 2026-08-04.
- Total raw records ingested was not measured in this run because live PostgreSQL metrics were unavailable.
- Forecast accuracy was not measured. The repo does not include independent observed surf conditions or a same-day labeled forecast comparison sufficient to claim weather or surf-quality accuracy.
- The sample dataset is intentionally small: 3 spots and 4 sessions. It supports validation of the warehouse shape, not production traffic claims.

## Recommended Resume Bullets

- Modeled surf forecast and session data across 3 sample surf spots using Python, PostgreSQL, and dbt, producing 21 daily spot-condition rows, 4 session fact rows, and 3 spot-performance rows in the recorded warehouse build.
- Built an 8-model dbt warehouse with 4 staging models and 4 mart/fact models, resulting in 14 passing dbt data-quality checks and a 100.0% test pass rate in the recorded dbt build artifact.
- Validated committed surf session seed data with 0 duplicate natural-key rows and 0.0% null rates across required spot and session fields by adding a repeatable Python evaluation harness with machine-readable JSON results.
