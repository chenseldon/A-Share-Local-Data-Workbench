from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient

from app.ai_analysis import build_analysis_context, generate_html_analysis, model_supports_screenshot
from app.demo_data import seed_demo_data
from app.main import create_app


def test_ai_analyze_endpoint_returns_html_without_persisting_api_key(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "ai-analysis.duckdb"
    app = create_app(db_path)
    captured: dict[str, Any] = {}

    def fake_build_context(repository: object, **kwargs: Any) -> dict[str, Any]:
        captured["context_kwargs"] = kwargs
        return {
            "scope": kwargs["scope"],
            "symbol": kwargs["symbol"],
            "module_id": kwargs["module_id"],
            "page_content": kwargs["page_content"],
            "chart": {"rows": [{"trade_date": "2026-07-20", "close": 10}]},
            "snapshots": [{"module": "reports", "tables": []}],
        }

    def fake_generate(
        provider: str,
        api_key: str,
        model: str | None,
        context: dict[str, Any],
        screenshot_base64: str | None = None,
        client: object | None = None,
    ) -> tuple[str, str, dict[str, Any], str, str]:
        captured["provider"] = provider
        captured["api_key"] = api_key
        captured["model"] = model
        captured["context"] = context
        captured["screenshot_base64"] = screenshot_base64
        return (
            '<article class="ai-report-document"><h1>600519.SH Kweichow Moutai | 评分：50 | 倾向：中性</h1><p>仅测试。</p></article>',
            "600519.SH Kweichow Moutai | 评分：50 | 倾向：中性\n仅测试。",
            {"input_tokens": 10},
            model or "gpt-5.6",
            "content+screenshot",
        )

    monkeypatch.setattr("app.main.build_analysis_context", fake_build_context)
    monkeypatch.setattr("app.main.generate_html_analysis", fake_generate)

    with TestClient(app) as client:
        seed_demo_data(db_path)
        response = client.post(
            "/api/ai/analyze",
            json={
                "provider": "openai",
                "api_key": "secret-key-123",
                "model": "gpt-5.6",
                "scope": "security_full",
                "symbol": "600519.SH",
                "include_latest_refresh": False,
                "period": "1d",
                "page_content": {"visible_text": "cached page"},
                "screenshot_base64": "ZmFrZS1wbmc=",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "openai"
        assert payload["model"] == "gpt-5.6"
        assert payload["input_mode"] == "content+screenshot"
        assert "report_html" in payload
        assert "pdf_base64" not in payload
        assert "secret-key-123" not in json.dumps(payload, ensure_ascii=False)
        assert captured["api_key"] == "secret-key-123"
        assert captured["context_kwargs"]["scope"] == "security_full"
        assert captured["context_kwargs"]["page_content"] == {"visible_text": "cached page"}

        health = client.get("/api/data-sources/status").json()
        jobs = client.get("/api/jobs").json()
        assert "secret-key-123" not in json.dumps(health, ensure_ascii=False)
        assert "secret-key-123" not in json.dumps(jobs, ensure_ascii=False)


def test_ai_provider_payloads_support_text_and_image_modes() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "api.openai.com" in str(request.url):
            return httpx.Response(200, json={"output_text": "<h1>openai report</h1>", "usage": {"total_tokens": 1}})
        if "api.anthropic.com" in str(request.url):
            return httpx.Response(200, json={"content": [{"type": "text", "text": "<h1>claude report</h1>"}], "usage": {"input_tokens": 1}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "<h1>deepseek report</h1>"}}], "usage": {"total_tokens": 1}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    context = {
        "scope": "security_full",
        "symbol": "600519.SH",
        "security": {"name": "Kweichow Moutai"},
        "chart": {"rows": []},
        "snapshots": [],
    }

    openai_html, _, _, openai_model, openai_mode = generate_html_analysis("openai", "openai-key", None, context, "fake", client=client)
    claude_html, _, _, claude_model, claude_mode = generate_html_analysis("anthropic", "claude-key", None, context, "fake", client=client)
    deepseek_html, _, _, deepseek_model, deepseek_mode = generate_html_analysis("deepseek", "deepseek-key", None, context, "fake", client=client)

    assert "openai report" in openai_html
    assert "claude report" in claude_html
    assert "deepseek report" in deepseek_html
    assert openai_model == "gpt-5.6"
    assert claude_model == "claude-sonnet-5"
    assert deepseek_model == "deepseek-v4-pro"
    assert openai_mode == "content+screenshot"
    assert claude_mode == "content+screenshot"
    assert deepseek_mode == "content"
    assert requests[0].url == "https://api.openai.com/v1/responses"
    assert requests[0].headers["authorization"] == "Bearer openai-key"
    assert "input_image" in requests[0].content.decode()
    assert requests[1].url == "https://api.anthropic.com/v1/messages"
    assert requests[1].headers["x-api-key"] == "claude-key"
    assert '"type":"image"' in requests[1].content.decode()
    assert requests[2].url == "https://api.deepseek.com/chat/completions"
    assert requests[2].headers["authorization"] == "Bearer deepseek-key"
    assert "image_url" not in requests[2].content.decode()


def test_ai_report_spec_is_loaded_into_prompt() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"output_text": "<h1>report</h1>"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    generate_html_analysis("openai", "key", "gpt-5.6", {"scope": "current_page"}, client=client)
    body = requests[0].content.decode()
    assert "AI Report Specification" in body
    assert "行情层" in body
    assert "期权层" in body


def test_model_screenshot_capabilities_are_provider_specific() -> None:
    assert model_supports_screenshot("openai", "gpt-5.6")
    assert model_supports_screenshot("anthropic", "claude-sonnet-5")
    assert not model_supports_screenshot("deepseek", "deepseek-v4-pro")
    assert not model_supports_screenshot("deepseek", "deepseek-v4-flash")
    assert model_supports_screenshot("deepseek", "deepseek-vl")


def test_ai_check_endpoint_is_sanitized(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "ai-check.duckdb"
    app = create_app(db_path)
    captured: dict[str, Any] = {}

    def fake_check(provider: str, api_key: str, model: str | None) -> tuple[bool, dict[str, Any], str, str]:
        captured["api_key"] = api_key
        return True, {"input_tokens": 1}, model or "deepseek-v4-pro", "AI provider responded."

    monkeypatch.setattr("app.main.check_ai_connection", fake_check)

    with TestClient(app) as client:
        response = client.post(
            "/api/ai/check",
            json={"provider": "deepseek", "api_key": "secret-key-456", "model": "deepseek-v4-pro"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["model"] == "deepseek-v4-pro"
        assert "secret-key-456" not in json.dumps(payload, ensure_ascii=False)
        assert captured["api_key"] == "secret-key-456"


def test_ai_check_endpoint_failure_does_not_echo_key(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "ai-check-failure.duckdb"
    app = create_app(db_path)

    def fake_check(provider: str, api_key: str, model: str | None) -> tuple[bool, dict[str, Any], str, str]:
        raise RuntimeError(f"bad key {api_key}")

    monkeypatch.setattr("app.main.check_ai_connection", fake_check)

    with TestClient(app) as client:
        response = client.post(
            "/api/ai/check",
            json={"provider": "openai", "api_key": "secret-key-789", "model": "gpt-5.6"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is False
        assert "secret-key-789" not in json.dumps(payload, ensure_ascii=False)


def test_security_full_context_includes_daily_indicator_context(monkeypatch) -> None:
    class FakeRepository:
        def list_source_health(self) -> list[dict[str, Any]]:
            return []

        def chart_bars(self, symbol: str, limit: int = 500, adjustment: str = "auto") -> list[dict[str, Any]]:
            return [
                {"symbol": symbol, "trade_date": "2026-07-17", "close": 10.0},
                {"symbol": symbol, "trade_date": "2026-07-20", "close": 11.0},
            ]

        def get_security_overview(self, symbol: str) -> dict[str, Any]:
            return {"security": {"symbol": symbol, "name": "Demo"}, "market": None, "quote": None, "freshness": [], "module_snapshots": []}

    def fake_indicators(symbol: str, indicator_ids: tuple[str, ...], start: str, end: str, frequency: str, fq: str) -> list[dict[str, Any]]:
        assert frequency == "1d"
        assert "macd" in indicator_ids
        return [
            {"date": "2026-07-17", "dif": 1.0, "dea": 0.8, "macd": 0.2, "rsi": 55.0},
            {"date": "2026-07-20", "dif": 1.1, "dea": 0.9, "macd": 0.3, "rsi": 58.0},
        ]

    monkeypatch.setattr("app.ai_analysis.fetch_free_stockdb_indicators", fake_indicators)
    context = build_analysis_context(
        FakeRepository(),  # type: ignore[arg-type]
        scope="security_full",
        symbol="600519.SH",
        module_id=None,
        period="1d",
        page_content={},
        include_latest_refresh=False,
    )
    daily = context["daily_indicator_context"]
    assert daily["period"] == "1d"
    assert daily["row_count"] == 2
    assert len(daily["rows"]) <= 500
    assert any(item["id"] == "macd" and item["status"] == "fresh" for item in daily["indicator_coverage"])
    assert any(item["id"] == "macd" for item in daily["indicator_catalog"])
