from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]


def load_environment() -> None:
    load_dotenv(ROOT_DIR / ".env")


def database_url() -> str:
    load_environment()
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "surf_warehouse")
    user = os.getenv("POSTGRES_USER", "surf")
    password = os.getenv("POSTGRES_PASSWORD", "surf")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def connect() -> psycopg.Connection:
    return psycopg.connect(database_url())


def ensure_schema() -> None:
    init_sql = ROOT_DIR / "sql" / "init.sql"
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(init_sql.read_text())
        conn.commit()

