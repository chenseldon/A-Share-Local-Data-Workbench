from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import httpx

from app.connectors import capabilities
from app.connectors.astock_sources import eastmoney_get
from app.connectors.base import ConnectorResult, payload_hash
from app.connectors.public_market import _stockdb_rows_to_market_bars
from app.free_stockdb_sdk import FreeStockdbSdkStatus, configure_free_stockdb_sdk_path


def test_connector_result_contract() -> None:
    result = ConnectorResult(
        source="fixture_source",
        status="fresh",
        records=[{"symbol": "600519.SH"}],
        raw_payload_hash=payload_hash("payload"),
    )

    assert result.source == "fixture_source"
    assert result.status == "fresh"
    assert result.records[0]["symbol"] == "600519.SH"
    assert len(result.raw_payload_hash) == 64


def test_stockdb_rows_are_normalized_to_market_bars() -> None:
    fetched_at = datetime(2026, 7, 16, 9, 30, 0)
    rows = [
        [20260715, "600519", "Kweichow Moutai", 1203.66, 1256.6, 1198.66, 1251.06, 7194400, 8922860000, 2.98],
        [20260714, "600519", "Kweichow Moutai", 1208.99, 1226.87, 1205, 1214.88, 4352700, 5294790000, 0.32],
    ]

    bars = _stockdb_rows_to_market_bars("600519.SH", rows, fetched_at=fetched_at, adjustment="qfq")

    assert [bar.trade_date for bar in bars] == ["2026-07-14", "2026-07-15"]
    assert bars[0].symbol == "600519.SH"
    assert bars[0].adjustment == "qfq"
    assert bars[0].source == "free_stockdb_kline"
    assert bars[0].chart_time is not None
    assert bars[1].close == 1251.06


def test_free_stockdb_sdk_path_bootstrap_adds_valid_pybao_path(tmp_path: Path, monkeypatch) -> None:
    sdk_path = tmp_path / "pybao"
    sdk_path.mkdir()
    (sdk_path / "stock_sdk.py").write_text("class StockDBClient: pass\n", encoding="utf-8")
    (sdk_path / "zhibiao.py").write_text("class zb: pass\nclass bk: pass\n", encoding="utf-8")
    monkeypatch.setenv("ASHARE_FREE_STOCKDB_SDK_PATH", str(sdk_path))
    monkeypatch.setattr(sys, "path", [path for path in sys.path if path != str(sdk_path)])
    importlib.invalidate_caches()

    status = configure_free_stockdb_sdk_path()

    assert status.configured_path == str(sdk_path)
    assert status.ready
    assert importlib.util.find_spec("stock_sdk") is not None
    assert importlib.util.find_spec("zhibiao") is not None


def test_capabilities_reports_free_stockdb_sdk_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        capabilities,
        "configure_free_stockdb_sdk_path",
        lambda: FreeStockdbSdkStatus(
            configured_path="C:/missing/pybao",
            path_exists=False,
            stock_sdk_available=False,
            zhibiao_available=False,
            error="Set ASHARE_FREE_STOCKDB_SDK_PATH to the free-stockdb pybao directory.",
        ),
    )

    rows = capabilities.list_capabilities()
    free_stockdb_rows = [row for row in rows if str(row["function"]).startswith("free_stockdb")]

    assert free_stockdb_rows
    assert {row["status"] for row in free_stockdb_rows} == {"sdk_missing"}
    assert all("ASHARE_FREE_STOCKDB_SDK_PATH" in str(row["note"]) for row in free_stockdb_rows)


def test_eastmoney_get_follows_redirects() -> None:
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"Location": "https://push2delay.eastmoney.com/final"})
        return httpx.Response(200, json={"ok": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    response = eastmoney_get("https://push2.eastmoney.com/redirect", client=client)

    assert response.status_code == 200
    assert requested_urls == ["https://push2.eastmoney.com/redirect", "https://push2delay.eastmoney.com/final"]
