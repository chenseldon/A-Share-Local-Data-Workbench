from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient

from app.ai_analysis import generate_analysis
from app.demo_data import seed_demo_data
from app.main import create_app


def test_ai_analysis_endpoint_returns_pdf_without_persisting_api_key(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "ai-analysis.duckdb"
    app = create_app(db_path)
    captured: dict[str, Any] = {}

    def fake_chart_rows(repository: object, symbol: str, period: str) -> tuple[list[dict[str, Any]], str, None]:
        rows = [
            {
                "symbol": symbol,
                "trade_date": f"2026-07-{(index % 28) + 1:02d}",
                "open": index + 1,
                "high": index + 2,
                "low": index,
                "close": index + 1.5,
                "volume": index * 100,
                "adjustment": "qfq",
                "ma5": index + 0.5,
                "dif": index / 10,
            }
            for index in range(520)
        ]
        return rows, "fresh", None

    def fake_generate(provider: str, api_key: str, model: str | None, context: dict[str, Any], client: object | None = None) -> tuple[str, dict[str, Any], str]:
        captured["provider"] = provider
        captured["api_key"] = api_key
        captured["model"] = model
        captured["context"] = context
        return "# 600519.SH Kweichow Moutai | 评分：60 | 倾向：中性\n## 核心结论\n仅测试。", {"input_tokens": 10}, model or "gpt-5"

    monkeypatch.setattr("app.main.chart_rows_with_all_indicators", fake_chart_rows)
    monkeypatch.setattr("app.main.generate_analysis", fake_generate)

    with TestClient(app) as client:
        seed_demo_data(db_path)
        response = client.post(
            "/api/security/600519.SH/ai-analysis",
            json={"provider": "openai", "api_key": "secret-key-123", "model": "gpt-5", "period": "1d"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "openai"
        assert payload["model"] == "gpt-5"
        assert "secret-key-123" not in json.dumps(payload, ensure_ascii=False)
        assert base64.b64decode(payload["pdf_base64"]).startswith(b"%PDF")
        assert captured["api_key"] == "secret-key-123"
        assert captured["context"]["chart"]["row_count"] == 520
        assert len(captured["context"]["chart"]["rows"]) == 500
        assert captured["context"]["snapshots"]

        health = client.get("/api/data-sources/status").json()
        jobs = client.get("/api/jobs").json()
        assert "secret-key-123" not in json.dumps(health, ensure_ascii=False)
        assert "secret-key-123" not in json.dumps(jobs, ensure_ascii=False)


def test_ai_provider_payloads_are_provider_specific() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "api.openai.com" in str(request.url):
            return httpx.Response(200, json={"output_text": "openai report", "usage": {"total_tokens": 1}})
        if "api.anthropic.com" in str(request.url):
            return httpx.Response(200, json={"content": [{"type": "text", "text": "claude report"}], "usage": {"input_tokens": 1}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "deepseek report"}}], "usage": {"total_tokens": 1}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    context = {
        "symbol": "600519.SH",
        "security": {"name": "Kweichow Moutai"},
        "chart": {"rows": []},
        "snapshots": [],
    }

    openai_text, _, openai_model = generate_analysis("openai", "openai-key", None, context, client=client)
    claude_text, _, claude_model = generate_analysis("anthropic", "claude-key", None, context, client=client)
    deepseek_text, _, deepseek_model = generate_analysis("deepseek", "deepseek-key", None, context, client=client)

    assert openai_text == "openai report"
    assert claude_text == "claude report"
    assert deepseek_text == "deepseek report"
    assert openai_model == "gpt-5"
    assert claude_model == "claude-sonnet-5"
    assert deepseek_model == "deepseek-v4-flash"
    assert requests[0].url == "https://api.openai.com/v1/responses"
    assert requests[0].headers["authorization"] == "Bearer openai-key"
    assert requests[1].url == "https://api.anthropic.com/v1/messages"
    assert requests[1].headers["x-api-key"] == "claude-key"
    assert requests[1].headers["anthropic-version"] == "2023-06-01"
    assert requests[2].url == "https://api.deepseek.com/chat/completions"
    assert requests[2].headers["authorization"] == "Bearer deepseek-key"
