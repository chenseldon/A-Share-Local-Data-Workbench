from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.connectors.astock_sources import AStockSourceError, ModuleRecord
from app.database import initialize_database
from app.main import create_app
from app.repository import DataRepository


def test_news_module_data_returns_structured_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "news-payload.duckdb"
    fetched_at = datetime(2026, 7, 15, 10, 30, 0)
    repository = DataRepository(db_path)
    initialize_database(db_path)
    repository.save_module_records(
        [
            ModuleRecord(
                module="news",
                source="eastmoney_stock_news",
                data_key="stock-news-1",
                symbol="600519.SH",
                record_date="2026-07-15",
                payload={
                    "symbol": "600519.SH",
                    "title": "Mock stock news",
                    "summary": "Mock company news summary",
                    "time": "2026-07-15 09:30:00",
                    "media": "Eastmoney",
                    "url": "https://finance.eastmoney.com/a/stock-news-1.html",
                    "source": "eastmoney_stock_news",
                },
                fetched_at=fetched_at,
                raw_payload_hash="news-hash-1",
            ),
            ModuleRecord(
                module="news",
                source="cls_telegraph",
                data_key="cls-1",
                symbol=None,
                record_date="2026-07-15",
                payload={
                    "symbol": None,
                    "title": "Mock CLS telegram",
                    "summary": "Mock CLS summary",
                    "time": "2026-07-15T10:00:00+00:00",
                    "media": "CLS",
                    "url": "https://www.cls.cn/detail/cls-1",
                    "source": "cls_telegraph",
                },
                fetched_at=fetched_at,
                raw_payload_hash="news-hash-2",
            ),
            ModuleRecord(
                module="news",
                source="eastmoney_global_news",
                data_key="global-1",
                symbol=None,
                record_date="2026-07-15",
                payload={
                    "symbol": None,
                    "title": "Mock global news",
                    "summary": "Mock global summary",
                    "time": "2026-07-15 10:05:00",
                    "media": "Eastmoney",
                    "url": "https://kuaixun.eastmoney.com/a/global-1.html",
                    "source": "eastmoney_global_news",
                },
                fetched_at=fetched_at,
                raw_payload_hash="news-hash-3",
            ),
        ]
    )
    app = create_app(db_path)
    with TestClient(app) as client:
        response = client.get("/api/modules/news/data?symbol=600519.SH")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["rows"][0]["title"] == "Mock stock news"
    assert payload["news"]["sections"][0]["title"] == "Stock News Snapshot"
    assert payload["news"]["sections"][0]["cards"][0]["value"] == 1
    assert payload["news"]["sections"][1]["cards"][0]["value"] == 1
    assert payload["news"]["sections"][1]["cards"][1]["value"] == 1
    assert payload["news"]["tables"][0]["rows"][0]["url"].endswith("stock-news-1.html")
    assert payload["news"]["tables"][1]["rows"][0]["title"] == "Mock CLS telegram"
    assert payload["news"]["tables"][2]["rows"][0]["title"] == "Mock global news"
    assert any(row["source"] == "cls_telegraph" for row in payload["news"]["source_status"])


def test_news_refresh_is_best_effort(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "news-refresh.duckdb"
    fetched_at = datetime(2026, 7, 15, 10, 30, 0)

    def fake_stock_news(symbol: str) -> list[ModuleRecord]:
        assert symbol == "600519.SH"
        return [
            ModuleRecord(
                module="news",
                source="eastmoney_stock_news",
                data_key="stock-news-1",
                symbol=symbol,
                record_date="2026-07-15",
                payload={"symbol": symbol, "title": "Mock stock news", "source": "eastmoney_stock_news"},
                fetched_at=fetched_at,
                raw_payload_hash="news-hash-1",
            )
        ]

    monkeypatch.setattr("app.main.eastmoney_stock_news", fake_stock_news)
    monkeypatch.setattr("app.main.cls_telegraph", lambda: (_ for _ in ()).throw(AStockSourceError("CLS failed")))
    monkeypatch.setattr("app.main.eastmoney_global_news", lambda: [])
    app = create_app(db_path)
    with TestClient(app) as client:
        refresh = client.post("/api/modules/news/refresh?symbol=600519.SH")
        assert refresh.status_code == 200
        payload = refresh.json()
        assert payload["status"] == "fresh"
        assert payload["records_written"] == 1
        assert payload["optional_results"]["eastmoney_stock_news"]["status"] == "fresh"
        assert payload["optional_results"]["cls_telegraph"]["status"] == "failed"

        data = client.get("/api/modules/news/data?symbol=600519.SH")
        assert data.status_code == 200
        source_status = data.json()["news"]["source_status"]
        assert any(row["source"] == "cls_telegraph" and row["status"] == "failed" for row in source_status)
        assert any(row["source"] == "eastmoney_global_news" and row["status"] == "fresh" for row in source_status)
