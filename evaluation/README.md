# Surf Session Warehouse Evaluation

This directory contains repeatable evaluation scripts and measured results for
the Surf Session Warehouse project. Metrics are only reported when they can be
reproduced from repository files, dbt artifacts, database queries, or commands
run locally.

## Project Type

The repository is classified as **Surf Session Warehouse** because it contains
PostgreSQL schema setup, Open-Meteo ingestion code, dbt warehouse models,
Prefect orchestration, and a Streamlit dashboard.

## Reproduction Commands

Run the repository and artifact evaluation:

```bash
python3 evaluation/evaluate_surf_session_warehouse.py --trials 5
```

Run live dbt build timing as well, after PostgreSQL is available:

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

Run the dashboard:

```bash
scripts/start_dashboard.sh
```

## Metrics Collected

- Project classification from repository contents.
- Sample source data row counts.
- Duplicate rates and required-field null rates for committed CSV files.
- Number of dbt SQL transformation models.
- Number of declared dbt data-quality checks.
- Prior dbt artifact results from `warehouse/target/run_results.json`, when
  present.
- Python syntax compilation runtime over repeated trials.
- Docker availability.
- PostgreSQL availability.
- Optional live database row counts, duplicate checks, pipeline run status, and
  dashboard query runtimes when the database is reachable.
- Optional live dbt build runtime over repeated trials.

## Metric Definitions

- **Duplicate-record rate**: duplicate rows divided by total rows using the
  natural key defined in the script for each dataset.
- **Required-field null rate**: blank or missing values divided by total rows
  for fields required by the repository schema or seed workflow.
- **dbt test pass rate**: passed dbt tests divided by total dbt tests in the dbt
  run artifact.
- **Runtime summary**: number of trials, mean, median, minimum, maximum, and
  sample standard deviation in seconds.
- **Forecast/session agreement**: only valid when logged sessions overlap
  modeled forecast dates. No weather or surf-quality accuracy is claimed unless
  such overlap and a defensible comparison exist.

## Limitations

- The committed sample session dataset contains 4 surf sessions and 3 surf
  spots. It is useful for validating the pipeline shape, not for claiming
  production scale.
- Forecast accuracy is not claimed unless same-day forecast rows can be joined
  to logged surf sessions or observations.
- Live ingestion and dbt runtime metrics require a reachable PostgreSQL
  database and working Python/dbt dependencies.
- Open-Meteo data changes over time, so live row values and forecast windows may
  differ by run date.
- The script records unavailable live metrics explicitly instead of estimating
  them.

## Results

Machine-readable results are written to:

```bash
evaluation/results.json
```
