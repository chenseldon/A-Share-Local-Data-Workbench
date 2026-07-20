from __future__ import annotations

import html
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx

from .connectors.public_market import FREE_STOCKDB_INDICATOR_CONFIG, fetch_free_stockdb_indicators
from .modules import MODULES
from .repository import DataRepository


Provider = Literal["openai", "anthropic", "deepseek"]
AnalysisScope = Literal["current_page", "security_full", "module", "all_modules"]
InputMode = Literal["content", "content+screenshot"]

DEFAULT_MODELS: dict[Provider, str] = {
    "openai": "gpt-5.6",
    "anthropic": "claude-sonnet-5",
    "deepseek": "deepseek-v4-pro",
}

INDICATOR_FIELD_HINTS: dict[str, tuple[str, ...]] = {
    "ma": ("ma5", "ma10", "ma20"),
    "ema": ("ema5", "ema10", "ema20", "ema"),
    "sma": ("sma5", "sma10", "sma20", "sma"),
    "wma": ("wma5", "wma10", "wma20", "wma"),
    "dma": ("dma10", "dma"),
    "std": ("std20", "std"),
    "sum": ("sum20", "sum"),
    "hhv": ("hhv20", "hhv"),
    "llv": ("llv20", "llv"),
    "ref": ("ref1", "ref"),
    "macd": ("dif", "dea", "macd"),
    "kdj": ("k", "d", "j"),
    "rsi": ("rsi", "rsi6", "rsi12", "rsi24"),
    "wr": ("wr", "wr1"),
    "bias": ("bias1", "bias2", "bias3"),
    "boll": ("upper", "mid", "lower"),
    "psy": ("psy", "psyma"),
    "cci": ("cci",),
    "atr": ("atr",),
    "bbi": ("bbi",),
    "dmi": ("pdi", "mdi", "adx", "adxr"),
    "taq": ("taq_up", "taq_mid", "taq_down"),
    "ktn": ("ktn_up", "ktn_mid", "ktn_down"),
    "trix": ("trix", "trma"),
    "vr": ("vr",),
    "cr": ("cr",),
    "emv": ("emv", "maemv"),
    "dpo": ("dpo", "madpo"),
    "brar": ("ar", "br"),
    "dfma": ("dfma_dif", "dfma_difma"),
    "mtm": ("mtm", "mtmma"),
    "mass": ("mass", "ma"),
    "roc": ("roc", "maroc"),
    "expma": ("exp1", "exp2"),
    "obv": ("obv", "maobv"),
    "mfi": ("mfi",),
    "asi": ("asi", "asit"),
    "xsii": ("td1", "td2", "td3", "td4"),
}

SYSTEM_PROMPT = """You are a public-equity research assistant for a local A-share research workbench.
Use only the supplied structured data and screenshot. Do not invent missing facts.
The output is research commentary, not a trading instruction.
Return a self-contained HTML fragment in Chinese using the requested report structure."""

REPORT_SPEC_PATH = Path(__file__).resolve().parents[2] / "AIReport.md"


def build_analysis_context(
    repository: DataRepository,
    *,
    scope: AnalysisScope,
    symbol: str | None,
    module_id: str | None,
    period: str,
    page_content: Any,
    include_latest_refresh: bool,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "scope": scope,
        "symbol": symbol,
        "module_id": module_id,
        "period": period,
        "generated_at": datetime.now(UTC).isoformat(),
        "include_latest_refresh": include_latest_refresh,
        "page_content": _bounded_value(page_content, max_rows=160, max_chars=160_000),
        "source_status": repository.list_source_health(),
    }
    if scope in {"security_full", "all_modules"} and symbol:
        chart_rows, indicator_status, indicator_error = chart_rows_with_all_indicators(repository, symbol, period)
        context["security_full"] = build_security_context(
            repository,
            symbol,
            period,
            chart_rows,
            indicator_status,
            indicator_error,
        )
        context["daily_indicator_context"] = build_daily_indicator_context(repository, symbol)
    if scope == "module" and module_id:
        context["module_data"] = repository.get_module_data(module_id, symbol, limit=100)
    if scope == "all_modules":
        context["modules"] = {
            module.id: repository.get_module_data(module.id, symbol, limit=100)
            for module in MODULES
        }
    return context


def build_security_context(
    repository: DataRepository,
    symbol: str,
    period: str,
    chart_rows: list[dict[str, Any]],
    indicator_status: str,
    indicator_error: str | None,
) -> dict[str, Any]:
    overview = repository.get_security_overview(symbol)
    return {
        "symbol": symbol,
        "period": period,
        "security": overview.get("security"),
        "market": overview.get("market"),
        "quote": overview.get("quote"),
        "freshness": overview.get("freshness"),
        "chart": {
            "period": period,
            "row_count": len(chart_rows),
            "rows": chart_rows[-500:],
            "requested_indicator_count": len(FREE_STOCKDB_INDICATOR_CONFIG),
            "indicator_status": indicator_status,
            "indicator_error": indicator_error,
        },
        "snapshots": overview.get("module_snapshots", []),
    }


def chart_rows_with_all_indicators(repository: DataRepository, symbol: str, period: str) -> tuple[list[dict[str, Any]], str, str | None]:
    rows = repository.chart_bars(symbol, limit=500, adjustment="auto")
    if not rows:
        return [], "not_collected", None
    indicator_ids = tuple(FREE_STOCKDB_INDICATOR_CONFIG.keys())
    indicator_status = "fresh"
    indicator_error = None
    try:
        indicator_rows = fetch_free_stockdb_indicators(
            symbol,
            indicator_ids,
            start=str(rows[0].get("trade_date")),
            end=str(rows[-1].get("trade_date")),
            frequency=period,
            fq="qfq",
        )
        indicator_by_date = {str(row.get("date")): row for row in indicator_rows}
        for row in rows:
            matched = indicator_by_date.get(str(row.get("trade_date")))
            if matched:
                row.update({key: value for key, value in matched.items() if key != "date"})
    except Exception as exc:  # noqa: BLE001 - external SDK failures should not block report context.
        indicator_status = "failed"
        indicator_error = str(exc)
    return rows, indicator_status, indicator_error


def build_daily_indicator_context(repository: DataRepository, symbol: str) -> dict[str, Any]:
    rows, status, error = chart_rows_with_all_indicators(repository, symbol, "1d")
    return {
        "period": "1d",
        "row_count": len(rows),
        "rows": rows[-500:],
        "status": status,
        "error": error,
        "indicator_catalog": indicator_catalog(),
        "indicator_coverage": indicator_coverage(rows, status, error),
    }


def indicator_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": indicator_id,
            "name": str(config.get("name") or indicator_id),
            "params": config.get("n"),
            "fields": list(INDICATOR_FIELD_HINTS.get(indicator_id, (indicator_id,))),
        }
        for indicator_id, config in FREE_STOCKDB_INDICATOR_CONFIG.items()
    ]


def indicator_coverage(rows: list[dict[str, Any]], status: str, error: str | None) -> list[dict[str, Any]]:
    coverage: list[dict[str, Any]] = []
    for indicator_id, fields in INDICATOR_FIELD_HINTS.items():
        available_fields = [
            field for field in fields
            if any(row.get(field) not in (None, "", "-") for row in rows)
        ]
        coverage.append(
            {
                "id": indicator_id,
                "status": "failed" if status == "failed" else ("fresh" if available_fields else "no_data"),
                "fields": list(fields),
                "available_fields": available_fields,
                "missing_fields": [field for field in fields if field not in available_fields],
                "available_row_count": sum(
                    1 for row in rows
                    if any(row.get(field) not in (None, "", "-") for field in fields)
                ),
                "error": error if status == "failed" else None,
            }
        )
    return coverage


def check_ai_connection(
    provider: Provider,
    api_key: str,
    model: str | None,
    client: httpx.Client | None = None,
) -> tuple[bool, dict[str, Any] | None, str, str]:
    selected_model = model.strip() if model and model.strip() else DEFAULT_MODELS[provider]
    prompt = "Reply with exactly: ok"
    owns_client = client is None
    http_client = client or httpx.Client(timeout=30)
    try:
        if provider == "openai":
            text, usage = _call_openai(http_client, api_key, selected_model, prompt, None)
        elif provider == "anthropic":
            text, usage = _call_anthropic(http_client, api_key, selected_model, prompt, None)
        elif provider == "deepseek":
            text, usage = _call_deepseek(http_client, api_key, selected_model, prompt, None)
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")
    finally:
        if owns_client:
            http_client.close()
    ok = bool(str(text or "").strip())
    return ok, usage, selected_model, "AI provider responded." if ok else "AI provider returned an empty response."


def generate_html_analysis(
    provider: Provider,
    api_key: str,
    model: str | None,
    context: dict[str, Any],
    screenshot_base64: str | None = None,
    client: httpx.Client | None = None,
) -> tuple[str, str, dict[str, Any] | None, str, InputMode]:
    selected_model = model.strip() if model and model.strip() else DEFAULT_MODELS[provider]
    use_screenshot = bool(screenshot_base64 and model_supports_screenshot(provider, selected_model))
    input_mode: InputMode = "content+screenshot" if use_screenshot else "content"
    prompt = _analysis_prompt(context, input_mode)
    owns_client = client is None
    http_client = client or httpx.Client(timeout=90)
    try:
        if provider == "openai":
            text, usage = _call_openai(http_client, api_key, selected_model, prompt, screenshot_base64 if use_screenshot else None)
        elif provider == "anthropic":
            text, usage = _call_anthropic(http_client, api_key, selected_model, prompt, screenshot_base64 if use_screenshot else None)
        elif provider == "deepseek":
            text, usage = _call_deepseek(http_client, api_key, selected_model, prompt, screenshot_base64 if use_screenshot else None)
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")
    finally:
        if owns_client:
            http_client.close()
    report_html = sanitize_report_html(text)
    report_text = html_to_text(report_html)
    return report_html, report_text, usage, selected_model, input_mode


def model_supports_screenshot(provider: Provider, model: str) -> bool:
    normalized = model.lower()
    if provider == "openai":
        return any(token in normalized for token in ("gpt-4o", "gpt-4.1", "gpt-5", "gpt-5.5", "gpt-5.6", "o3", "o4", "vision"))
    if provider == "anthropic":
        return any(token in normalized for token in ("claude-3", "claude-sonnet", "claude-opus", "claude-haiku", "sonnet", "opus", "haiku"))
    if provider == "deepseek":
        return "vision" in normalized or "vl" in normalized
    return False


def sanitize_report_html(value: str) -> str:
    cleaned = _strip_code_fence(value.strip())
    if "<" not in cleaned or ">" not in cleaned:
        cleaned = _plain_text_to_html(cleaned)
    cleaned = re.sub(r"<script\b[^>]*>.*?</script>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"\s+on[a-zA-Z]+\s*=\s*(['\"]).*?\1", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"\s+on[a-zA-Z]+\s*=\s*[^\s>]+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"javascript:", "", cleaned, flags=re.IGNORECASE)
    if "ai-report-document" not in cleaned:
        cleaned = f'<article class="ai-report-document">{cleaned}</article>'
    return cleaned


def html_to_text(value: str) -> str:
    text = re.sub(r"<(br|/p|/div|/li|/h[1-6]|/section|/article)\b[^>]*>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _analysis_prompt(context: dict[str, Any], input_mode: InputMode) -> str:
    report_spec = _load_report_spec()
    return (
        f"{report_spec}\n\n"
        f"Input mode: {input_mode}. If a screenshot is provided, use it only to cross-check visual context; structured data remains primary.\n\n"
        "Structured input JSON:\n"
        + json.dumps(context, ensure_ascii=False, default=str)
    )


def _load_report_spec() -> str:
    if REPORT_SPEC_PATH.exists():
        return REPORT_SPEC_PATH.read_text(encoding="utf-8")
    return (
        "# AI Report Spec\n"
        "Return a dark-theme HTML research report. Use the fixed sections: 核心结论, 行情层, 指标层, 基础数据, 公告层, 新闻层, 研报层, 资金面/筹码层, 信号层, 期权层, 反证与失效条件, 数据质量与来源限制."
    )


def _call_openai(
    client: httpx.Client,
    api_key: str,
    model: str,
    prompt: str,
    screenshot_base64: str | None,
) -> tuple[str, dict[str, Any] | None]:
    user_content: Any
    if screenshot_base64:
        user_content = [
            {"type": "input_text", "text": prompt},
            {"type": "input_image", "image_url": f"data:image/png;base64,{screenshot_base64}"},
        ]
    else:
        user_content = prompt
    response = client.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "input": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        },
    )
    response.raise_for_status()
    payload = response.json()
    text = payload.get("output_text") or _extract_openai_output_text(payload)
    return str(text or ""), payload.get("usage")


def _call_anthropic(
    client: httpx.Client,
    api_key: str,
    model: str,
    prompt: str,
    screenshot_base64: str | None,
) -> tuple[str, dict[str, Any] | None]:
    content: Any
    if screenshot_base64:
        content = [
            {"type": "text", "text": prompt},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": screenshot_base64}},
        ]
    else:
        content = prompt
    response = client.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 6000,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": content}],
        },
    )
    response.raise_for_status()
    payload = response.json()
    text = "\n".join(str(item.get("text") or "") for item in payload.get("content", []) if item.get("type") == "text")
    return text, payload.get("usage")


def _call_deepseek(
    client: httpx.Client,
    api_key: str,
    model: str,
    prompt: str,
    screenshot_base64: str | None,
) -> tuple[str, dict[str, Any] | None]:
    user_content: Any = prompt
    if screenshot_base64:
        user_content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}},
        ]
    response = client.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        },
    )
    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices") or []
    message = choices[0].get("message", {}) if choices else {}
    return str(message.get("content") or ""), payload.get("usage")


def _extract_openai_output_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if isinstance(content, dict):
                text = content.get("text")
                if text:
                    parts.append(str(text))
    return "\n".join(parts)


def _strip_code_fence(value: str) -> str:
    match = re.fullmatch(r"```(?:html)?\s*(.*?)\s*```", value, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else value


def _plain_text_to_html(value: str) -> str:
    lines = value.splitlines()
    parts: list[str] = ['<article class="ai-report-document">']
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            parts.append(f"<h1>{html.escape(stripped[2:].strip())}</h1>")
        elif stripped.startswith("## "):
            parts.append(f"<h2>{html.escape(stripped[3:].strip())}</h2>")
        elif stripped.startswith("- "):
            parts.append(f"<p>{html.escape(stripped)}</p>")
        else:
            parts.append(f"<p>{html.escape(stripped)}</p>")
    parts.append("</article>")
    return "\n".join(parts)


def _bounded_value(value: Any, *, max_rows: int, max_chars: int) -> Any:
    serialized = json.dumps(value, ensure_ascii=False, default=str)
    if len(serialized) <= max_chars:
        return value
    if isinstance(value, dict):
        bounded: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(item, list):
                bounded[key] = item[:max_rows]
            elif isinstance(item, dict):
                bounded[key] = _bounded_value(item, max_rows=max_rows, max_chars=max_chars // 2)
            else:
                bounded[key] = item
        return bounded
    if isinstance(value, list):
        return value[:max_rows]
    return str(value)[:max_chars]
