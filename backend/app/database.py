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
        _apply_lightweight_migrations(connection)
    finally:
        connection.close()


def _apply_lightweight_migrations(connection: duckdb.DuckDBPyConnection) -> None:
    quote_columns = {
        row[1] for row in connection.execute("PRAGMA table_info('market_quotes')").fetchall()
    }
    for column, column_type in {
        "change_amt": "DOUBLE",
        "change_pct": "DOUBLE",
        "turnover_pct": "DOUBLE",
        "pe_ttm": "DOUBLE",
        "amplitude_pct": "DOUBLE",
        "total_market_cap": "DOUBLE",
        "float_market_cap": "DOUBLE",
        "pb": "DOUBLE",
        "limit_up": "DOUBLE",
        "limit_down": "DOUBLE",
        "volume_ratio": "DOUBLE",
        "pe_static": "DOUBLE",
    }.items():
        if column not in quote_columns:
            connection.execute(f"ALTER TABLE market_quotes ADD COLUMN {column} {column_type}")
