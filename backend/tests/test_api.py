from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.connectors.public_market import MarketBar, MarketQuote, MarketSnapshot, ResolvedSecurity, normalize_symbol
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


def test_symbol_normalization() -> None:
    assert normalize_symbol("600519") == "600519.SH"
    assert normalize_symbol("000001") == "000001.SZ"
    assert normalize_symbol("920001") == "920001.BJ"


def test_partial_search_does_not_remote_resolve(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "partial.duckdb"

    def fail_remote(_: str) -> MarketSnapshot:
        raise AssertionError("partial query should not call remote connector")

    monkeypatch.setattr("app.main.fetch_public_market_snapshot", fail_remote)
    app = create_app(db_path)
    with TestClient(app) as client:
        search = client.get("/api/securities/search?q=60")
        assert search.status_code == 200
        assert search.json()["rows"] == []
        assert search.json()["remote_status"] == "not_needed"


def test_refresh_quote_and_chart_are_cached(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "refresh.duckdb"
    fetched_at = datetime(2026, 7, 15, 10, 30, 0)

    def fake_snapshot(symbol: str) -> MarketSnapshot:
        assert symbol == "600519.SH"
        security = ResolvedSecurity(
            symbol="600519.SH",
            name="Kweichow Moutai",
            exchange="SSE",
            asset_type="stock",
            sector=None,
            source="tencent_quote",
            fetched_at=fetched_at,
            raw_payload_hash="security-hash",
        )
        quote = MarketQuote(
            symbol="600519.SH",
            price_time=fetched_at,
            last_price=1518.5,
            previous_close=1510.0,
            open=1512.0,
            high=1520.0,
            low=1508.0,
            volume=123456.0,
            amount=187000000.0,
            bid1=1518.4,
            ask1=1518.6,
            source="tencent_quote",
            fetched_at=fetched_at,
            raw_payload_hash="quote-hash",
        )
        bars = tuple(
            MarketBar(
                symbol="600519.SH",
                trade_date=f"2026-07-{day:02d}",
                open=1500 + day,
                high=1510 + day,
                low=1490 + day,
                close=1505 + day,
                volume=1000 + day,
                amount=100000 + day,
                adjustment="none",
                source="tencent_kline",
                fetched_at=fetched_at,
                raw_payload_hash=f"bar-{day}",
            )
            for day in range(1, 22)
        )
        return MarketSnapshot(security=security, quote=quote, bars=bars)

    monkeypatch.setattr("app.main.fetch_public_market_snapshot", fake_snapshot)
    app = create_app(db_path)
    with TestClient(app) as client:
        refresh = client.post("/api/security/600519/refresh")
        assert refresh.status_code == 200
        assert refresh.json()["records_written"] == 23

        quote = client.get("/api/security/600519.SH/quote")
        assert quote.status_code == 200
        assert quote.json()["quote"]["last_price"] == 1518.5

        chart = client.get("/api/security/600519.SH/chart")
        assert chart.status_code == 200
        rows = chart.json()["rows"]
        assert len(rows) == 21
        assert rows[-1]["ma20"] is not None
