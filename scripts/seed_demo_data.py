from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.database import initialize_database  # noqa: E402
from app.demo_data import seed_demo_data  # noqa: E402


def main() -> None:
    initialize_database()
    seed_demo_data()
    print("Seeded labeled fixture data into the local DuckDB database.")


if __name__ == "__main__":
    main()
