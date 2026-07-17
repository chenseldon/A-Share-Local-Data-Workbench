from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.connectors.public_market import BoardMapping, MarketBar, MarketQuote, MarketSnapshot, ResolvedSecurity, normalize_symbol
from app.database import initialize_database
from app.demo_data import seed_demo_data
from app.main import create_app
from app.repository import DataRepository


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


def test_default_startup_removes_fixture_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "purge-fixtures.duckdb"
    initialize_database(db_path)
    seed_demo_data(db_path)
    app = create_app(db_path)
    with TestClient(app) as client:
        search = client.get("/api/securities/search?remote=false")
        assert search.status_code == 200
        assert search.json()["rows"] == []


def test_capabilities_registry_is_exposed(tmp_path: Path) -> None:
    db_path = tmp_path / "capabilities.duckdb"
    app = create_app(db_path)
    with TestClient(app) as client:
        response = client.get("/api/connectors/capabilities")
        assert response.status_code == 200
        rows = response.json()["rows"]
        assert any(row["function"] == "tencent_quote" and row["status"] == "wired" for row in rows)
        assert any(row["function"] == "iwencai_search" and row["status"] == "needs_key" for row in rows)


def test_module_refresh_reports_uses_connector_and_cache(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "module-refresh.duckdb"

    def fake_reports(symbol: str, max_pages: int = 1) -> list[dict[str, object]]:
        assert symbol == "600519.SH"
        assert max_pages == 1
        return [
            {
                "infoCode": "123456",
                "title": "Mock report",
                "publishDate": "2026-07-15 08:00:00",
                "orgSName": "Mock Securities",
                "emRatingName": "Buy",
                "predictThisYearEps": "10.0",
            }
        ]

    monkeypatch.setattr("app.main.eastmoney_reports", fake_reports)
    app = create_app(db_path)
    with TestClient(app) as client:
        refresh = client.post("/api/modules/reports/refresh?symbol=600519.SH")
        assert refresh.status_code == 200
        assert refresh.json()["records_written"] == 1

        data = client.get("/api/modules/reports/data?symbol=600519.SH")
        assert data.status_code == 200
        payload = data.json()
        assert payload["status"] == "ok"
        assert payload["rows"][0]["title"] == "Mock report"


def test_symbol_normalization() -> None:
    assert normalize_symbol("600519") == "600519.SH"
    assert normalize_symbol("000001") == "000001.SZ"
    assert normalize_symbol("920001") == "920001.BJ"


def test_partial_search_does_not_remote_resolve(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "partial.duckdb"

    def fail_exact(_: str) -> ResolvedSecurity:
        raise AssertionError("partial query should not call exact connector")

    monkeypatch.setattr("app.main.fetch_free_stockdb_security", fail_exact)
    app = create_app(db_path)
    with TestClient(app) as client:
        search = client.get("/api/securities/search?q=60")
        assert search.status_code == 200
        assert search.json()["rows"] == []
        assert search.json()["remote_status"] == "not_needed"


def test_universe_refresh_builds_local_search_directory(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "universe-search.duckdb"
    fetched_at = datetime(2026, 7, 15, 10, 30, 0)

    def fake_universe() -> tuple[ResolvedSecurity, ...]:
        return (
            ResolvedSecurity(
                symbol="600519.SH",
                name="\u8d35\u5dde\u8305\u53f0",
                exchange="SSE",
                asset_type="stock",
                sector=None,
                source="free_stockdb_universe",
                fetched_at=fetched_at,
                raw_payload_hash="security-hash",
            ),
            ResolvedSecurity(
                symbol="600004.SH",
                name="\u767d\u4e91\u673a\u573a",
                exchange="SSE",
                asset_type="stock",
                sector=None,
                source="free_stockdb_universe",
                fetched_at=fetched_at,
                raw_payload_hash="security-hash-2",
            ),
        )

    monkeypatch.setattr("app.main.fetch_free_stockdb_security_universe", fake_universe)
    app = create_app(db_path)
    with TestClient(app) as client:
        status = client.get("/api/securities/universe/status")
        assert status.status_code == 200
        assert status.json()["count"] == 0

        refresh = client.post("/api/securities/universe/refresh")
        assert refresh.status_code == 200
        assert refresh.json()["records_written"] == 2
        assert refresh.json()["candidates_scanned"] > 38000
        assert refresh.json()["prefixes_scanned"] > 38
        assert refresh.json()["expected_source_count"] == 7400

        search = client.get("/api/securities/search?q=\u8305\u53f0")
        assert search.status_code == 200
        payload = search.json()
        assert payload["remote_status"] == "not_needed"
        assert payload["rows"][0]["symbol"] == "600519.SH"

        code_search = client.get("/api/securities/search?q=600004")
        assert code_search.status_code == 200
        assert code_search.json()["rows"][0]["name"] == "\u767d\u4e91\u673a\u573a"


def test_complete_search_resolves_with_free_stockdb_security(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "remote-search.duckdb"
    fetched_at = datetime(2026, 7, 15, 10, 30, 0)

    def fake_free_stockdb_security(symbol: str) -> ResolvedSecurity:
        assert symbol == "600519.SH"
        return ResolvedSecurity(
            symbol="600519.SH",
            name="贵州茅台",
            exchange="SSE",
            asset_type="stock",
            sector=None,
            source="free_stockdb_security",
            fetched_at=fetched_at,
            raw_payload_hash="security-hash",
        )

    monkeypatch.setattr("app.main.fetch_free_stockdb_security", fake_free_stockdb_security)
    app = create_app(db_path)
    with TestClient(app) as client:
        search = client.get("/api/securities/search?q=600519&remote=true")
        assert search.status_code == 200
        payload = search.json()
        assert payload["remote_status"] == "fetched"
        assert payload["rows"][0]["symbol"] == "600519.SH"
        assert payload["rows"][0]["name"] == "贵州茅台"


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
                source="free_stockdb_kline",
                fetched_at=fetched_at,
                raw_payload_hash=f"bar-{day}",
            )
            for day in range(1, 22)
        )
        return MarketSnapshot(security=security, quote=quote, bars=bars)

    monkeypatch.setattr("app.main.fetch_public_market_snapshot", fake_snapshot)
    monkeypatch.setattr("app.main.fetch_free_stockdb_bars", lambda symbol, **_: fake_snapshot(symbol).bars)
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


def test_chart_indicators_are_merged_on_demand(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "chart-indicators.duckdb"
    fetched_at = datetime(2026, 7, 15, 10, 30, 0)

    def fake_snapshot(_: str) -> MarketSnapshot:
        security = ResolvedSecurity(
            symbol="600004.SH",
            name="Baiyun Airport",
            exchange="SSE",
            asset_type="stock",
            sector=None,
            source="free_stockdb_security",
            fetched_at=fetched_at,
            raw_payload_hash="security-hash",
        )
        bars = tuple(
            MarketBar(
                symbol="600004.SH",
                trade_date=f"2026-07-{day:02d}",
                open=7.0 + day / 100,
                high=7.2 + day / 100,
                low=6.9 + day / 100,
                close=7.1 + day / 100,
                volume=1000 + day,
                amount=100000 + day,
                adjustment="qfq",
                source="free_stockdb_kline",
                fetched_at=fetched_at,
                raw_payload_hash=f"bar-{day}",
            )
            for day in range(1, 4)
        )
        return MarketSnapshot(security=security, quote=None, bars=bars)

    def fake_indicators(symbol: str, indicators: tuple[str, ...], **kwargs: object) -> dict[str, dict[str, object]]:
        assert symbol == "600004.SH"
        assert indicators == ("ma", "macd")
        assert kwargs["frequency"] == "1d"
        return {
            "2026-07-03": {
                "ma5": 7.12,
                "dif": 0.02,
                "dea": 0.01,
                "macd": None,
            }
        }

    monkeypatch.setattr("app.main.fetch_public_market_snapshot", fake_snapshot)
    monkeypatch.setattr("app.main.fetch_free_stockdb_bars", lambda symbol, **_: fake_snapshot(symbol).bars)
    monkeypatch.setattr("app.main.fetch_free_stockdb_indicators", fake_indicators)
    app = create_app(db_path)
    with TestClient(app) as client:
        assert client.post("/api/security/600004/refresh").status_code == 200
        chart = client.get("/api/security/600004.SH/chart?indicators=ma,macd")
        assert chart.status_code == 200
        payload = chart.json()
        assert payload["indicator_status"] == "fresh"
        assert payload["requested_indicators"] == ["ma", "macd"]
        assert payload["rows"][-1]["ma5"] == 7.12
        assert payload["rows"][-1]["macd"] is None

        invalid = client.get("/api/security/600004.SH/chart?indicators=unknown")
        assert invalid.status_code == 400


def test_chart_period_uses_free_stockdb_frequency(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "chart-period.duckdb"
    fetched_at = datetime(2026, 7, 15, 10, 30, 0)

    def fake_bars(symbol: str, **kwargs: object) -> tuple[MarketBar, ...]:
        assert symbol == "600004.SH"
        assert kwargs["frequency"] == "1m"
        return (
            MarketBar(
                symbol="600004.SH",
                trade_date="2026-07-16 09:31:00",
                chart_time=1784165460,
                open=7.1,
                high=7.2,
                low=7.0,
                close=7.15,
                volume=1000,
                amount=7150,
                adjustment="qfq",
                source="free_stockdb_kline",
                fetched_at=fetched_at,
                raw_payload_hash="bar-1m",
            ),
        )

    monkeypatch.setattr("app.main.fetch_free_stockdb_bars", fake_bars)
    app = create_app(db_path)
    with TestClient(app) as client:
        chart = client.get("/api/security/600004.SH/chart?period=1m")
        assert chart.status_code == 200
        payload = chart.json()
        assert payload["period"] == "1m"
        assert payload["rows"][0]["chart_time"] == 1784165460

        invalid = client.get("/api/security/600004.SH/chart?period=4h")
        assert invalid.status_code == 422


def test_boards_endpoint_updates_security_sector(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "boards.duckdb"
    fetched_at = datetime(2026, 7, 15, 10, 30, 0)

    def fake_boards(symbol: str) -> BoardMapping:
        assert symbol == "600004.SH"
        return BoardMapping(
            symbol="600004.SH",
            concepts=["免税店", "国企改革"],
            sw_l1=["交通运输"],
            sw_l2=["航空机场"],
            sw_l3=["机场"],
            source="free_stockdb_bk",
            fetched_at=fetched_at,
        )

    monkeypatch.setattr("app.main.fetch_free_stockdb_board_mapping", fake_boards)
    app = create_app(db_path)
    with TestClient(app) as client:
        DataRepository(db_path).save_security(
            ResolvedSecurity(
                symbol="600004.SH",
                name="白云机场",
                exchange="SSE",
                asset_type="stock",
                sector=None,
                source="free_stockdb_universe",
                fetched_at=fetched_at,
                raw_payload_hash="security-hash",
            )
        )
        boards = client.get("/api/security/600004.SH/boards")
        assert boards.status_code == 200
        assert boards.json()["concepts"] == ["免税店", "国企改革"]
        assert boards.json()["sw_l1"] == ["交通运输"]

        overview = client.get("/api/security/600004.SH/overview")
        assert overview.status_code == 200
        assert overview.json()["security"]["sector"] == "交通运输"
