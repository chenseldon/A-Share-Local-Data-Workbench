from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.demo_data import seed_demo_data
from app.main import create_app


def test_empty_api_states(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.duckdb"
    app = create_app(db_path)
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        modules = client.get("/api/modules")
        assert modules.status_code == 200
        assert len(modules.json()) == 10

        unknown = client.get("/api/security/600519.SH/overview")
        assert unknown.status_code == 404

        market = client.get("/api/modules/market/data")
        assert market.status_code == 200
        assert market.json()["status"] == "not_collected"


def test_seeded_search_and_overview(tmp_path: Path) -> None:
    db_path = tmp_path / "seeded.duckdb"
    app = create_app(db_path)
    with TestClient(app) as client:
        seed_demo_data(db_path)

        search = client.get("/api/securities/search?q=600519")
        assert search.status_code == 200
        assert search.json()["rows"][0]["symbol"] == "600519.SH"

        overview = client.get("/api/security/600519.SH/overview")
        payload = overview.json()
        assert overview.status_code == 200
        assert payload["market"]["source"] == "local_fixture"
        assert payload["freshness"]["market"] == "fresh"
        assert payload["freshness"]["reports"] == "fresh"

        market = client.get("/api/modules/market/data?symbol=600519.SH")
        assert market.status_code == 200
        assert market.json()["status"] == "ok"


def test_seed_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "idempotent.duckdb"
    app = create_app(db_path)
    with TestClient(app) as client:
        seed_demo_data(db_path)
        seed_demo_data(db_path)

        search = client.get("/api/securities/search")
        assert search.status_code == 200
        assert len(search.json()["rows"]) == 4
