from __future__ import annotations

from app.connectors.base import ConnectorResult, payload_hash


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
