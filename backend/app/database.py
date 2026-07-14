from __future__ import annotations

import os
from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "ashare.duckdb"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_database_path() -> Path:
    configured = os.getenv("ASHARE_DB_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_DB_PATH


def connect(db_path: Path | str | None = None) -> duckdb.DuckDBPyConnection:
    path = Path(db_path) if db_path is not None else get_database_path()
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def initialize_database(db_path: Path | str | None = None) -> None:
    connection = connect(db_path)
    try:
        connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    finally:
        connection.close()
