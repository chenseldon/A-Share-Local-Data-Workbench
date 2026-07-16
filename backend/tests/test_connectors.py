from __future__ import annotations

from datetime import datetime

from app.connectors.base import ConnectorResult, payload_hash
from app.connectors.public_market import _stockdb_rows_to_market_bars


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
    assert bars[1].close == 1251.06
