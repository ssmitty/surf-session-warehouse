# Surf Session Warehouse

Surf Session Warehouse is an end-to-end data engineering project for modeling surf forecasts, weather conditions, and personal surf session logs. It uses PostgreSQL for storage, Python for ingestion, dbt for warehouse transformations, Prefect for scheduling, and Streamlit for analysis.

## Why This Project Exists

This project is built to show practical data engineering skills around a real interest: surfing. It answers questions like:

- Which surf spots produce the best sessions?
- What wind, swell, and wave conditions line up with high ratings?
- How fresh is the forecast pipeline?
- How do logged sessions compare with historical forecast conditions?

## Stack

- PostgreSQL
- Python
- Open-Meteo Marine and Weather APIs
- dbt
- Prefect
- Streamlit
- Docker Compose

## Project Structure

```text
app/
  streamlit_app.py
data/
  sample_sessions.csv
  sample_spots.csv
pipelines/
  db.py
  ingest_open_meteo.py
  prefect_flow.py
  seed.py
sql/
  init.sql
warehouse/
  dbt_project.yml
  profiles.yml
  models/
```

## Run Locally

1. Start PostgreSQL:

```bash
docker compose up -d postgres
```

2. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Load seed spots and sample sessions:

```bash
python -m pipelines.seed
```

4. Fetch forecast data from Open-Meteo:

```bash
python -m pipelines.ingest_open_meteo
```

5. Build dbt models:

```bash
cd warehouse
dbt build --profiles-dir .
```

6. Run the dashboard:

```bash
streamlit run app/streamlit_app.py
```

## Resume Bullet

Built an end-to-end surf analytics warehouse using PostgreSQL, dbt, Python, and scheduled pipelines to model forecast, wind, wave, and session data for spot-level performance analysis.

## Current MVP

- PostgreSQL schema for surf spots, sessions, raw marine forecasts, raw weather forecasts, and pipeline runs
- Seed data for sample surf spots and sessions
- Open-Meteo ingestion pipeline
- dbt staging, fact, and mart models
- Streamlit dashboard for sessions, conditions, spot performance, and pipeline health

