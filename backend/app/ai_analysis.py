from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from textwrap import wrap
from typing import Any, Literal

import httpx
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .connectors.public_market import FREE_STOCKDB_INDICATOR_CONFIG, fetch_free_stockdb_indicators
from .repository import DataRepository


Provider = Literal["openai", "anthropic", "deepseek"]

DEFAULT_MODELS: dict[Provider, str] = {
    "openai": "gpt-5",
    "anthropic": "claude-sonnet-5",
    "deepseek": "deepseek-v4-flash",
}

SYSTEM_PROMPT = """You are a public-equity research assistant for a local A-share research workbench.
Use only the supplied JSON data. Do not invent missing facts.
The output is research commentary, not a trading instruction.
Return the report in Chinese with the exact template sections requested."""

REPORT_TEMPLATE = """首行格式必须为：
# {symbol} {name} | 评分：{0-100} | 倾向：看多/中性/看空

固定章节：
## 核心结论
## 价格/量能
## 基本面
## 公告/新闻/研报
## 资金筹码
## 信号层
## 反证与失效条件
## 数据质量与来源限制

要求：
- 评分必须是 0 到 100 的整数。
- 倾向只能是 看多、中性、看空。
- 每个结论都应能追溯到输入数据字段、source 或 fetched_at。
- 对缺失、过期、失败或空表数据必须明确说明，不要补全。
- 不得给出无条件买入、卖出、加仓、减仓、做多或做空指令。
"""


@dataclass(frozen=True)
class AnalysisResult:
    symbol: str
    name: str
    provider: Provider
    model: str
    generated_at: str
    report_text: str
    pdf_base64: str
    usage: dict[str, Any] | None


def build_ai_context(
    repository: DataRepository,
    symbol: str,
    period: str,
    chart_rows: list[dict[str, Any]],
    indicator_status: str,
    indicator_error: str | None,
) -> dict[str, Any]:
    overview = repository.get_security_overview(symbol)
    boards = {
        "concepts": [],
        "sw_l1": [],
        "sw_l2": [],
        "sw_l3": [],
        "source": None,
        "fetched_at": None,
        "status": "not_collected",
    }
    source_status = repository.list_source_health()
    return {
        "symbol": symbol,
        "period": period,
        "generated_at": datetime.now(UTC).isoformat(),
        "security": overview.get("security"),
        "market": overview.get("market"),
        "quote": overview.get("quote"),
        "freshness": overview.get("freshness"),
        "boards": boards,
        "chart": {
            "period": period,
            "row_count": len(chart_rows),
            "rows": chart_rows[-500:],
            "requested_indicator_count": len(FREE_STOCKDB_INDICATOR_CONFIG),
            "indicator_status": indicator_status,
            "indicator_error": indicator_error,
        },
        "snapshots": overview.get("module_snapshots", []),
        "source_status": source_status,
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


def generate_analysis(
    provider: Provider,
    api_key: str,
    model: str | None,
    context: dict[str, Any],
    client: httpx.Client | None = None,
) -> tuple[str, dict[str, Any] | None, str]:
    selected_model = model.strip() if model and model.strip() else DEFAULT_MODELS[provider]
    prompt = _analysis_prompt(context)
    owns_client = client is None
    http_client = client or httpx.Client(timeout=60)
    try:
        if provider == "openai":
            text, usage = _call_openai(http_client, api_key, selected_model, prompt)
        elif provider == "anthropic":
            text, usage = _call_anthropic(http_client, api_key, selected_model, prompt)
        elif provider == "deepseek":
            text, usage = _call_deepseek(http_client, api_key, selected_model, prompt)
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")
    finally:
        if owns_client:
            http_client.close()
    return text.strip(), usage, selected_model


def make_pdf_base64(report_text: str, title: str) -> str:
    pdf_bytes = BytesIO()
    registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "ChineseBody",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=10,
        leading=15,
        spaceAfter=5,
    )
    heading_style = ParagraphStyle(
        "ChineseHeading",
        parent=styles["Heading2"],
        fontName="STSong-Light",
        fontSize=13,
        leading=18,
        spaceBefore=8,
        spaceAfter=6,
    )
    story: list[Any] = [Paragraph(_escape_pdf_text(title), heading_style), Spacer(1, 4 * mm)]
    for line in report_text.splitlines():
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 3 * mm))
            continue
        style = heading_style if stripped.startswith("#") else body_style
        cleaned = stripped.lstrip("#").strip()
        for chunk in wrap(cleaned, width=95, break_long_words=False, replace_whitespace=False) or [cleaned]:
            story.append(Paragraph(_escape_pdf_text(chunk), style))
    document = SimpleDocTemplate(
        pdf_bytes,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=title,
    )
    document.build(story)
    return base64.b64encode(pdf_bytes.getvalue()).decode("ascii")


def _analysis_prompt(context: dict[str, Any]) -> str:
    symbol = str(context.get("symbol") or "")
    security = context.get("security") if isinstance(context.get("security"), dict) else {}
    name = str(security.get("name") or "")
    return (
        REPORT_TEMPLATE.replace("{symbol}", symbol).replace("{name}", name)
        + "\n\n输入数据 JSON：\n"
        + json.dumps(context, ensure_ascii=False, default=str)
    )


def _call_openai(client: httpx.Client, api_key: str, model: str, prompt: str) -> tuple[str, dict[str, Any] | None]:
    response = client.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "input": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        },
    )
    response.raise_for_status()
    payload = response.json()
    text = payload.get("output_text") or _extract_openai_output_text(payload)
    return str(text or ""), payload.get("usage")


def _call_anthropic(client: httpx.Client, api_key: str, model: str, prompt: str) -> tuple[str, dict[str, Any] | None]:
    response = client.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 4096,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    response.raise_for_status()
    payload = response.json()
    text = "\n".join(str(item.get("text") or "") for item in payload.get("content", []) if item.get("type") == "text")
    return text, payload.get("usage")


def _call_deepseek(client: httpx.Client, api_key: str, model: str, prompt: str) -> tuple[str, dict[str, Any] | None]:
    response = client.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
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


def _escape_pdf_text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
