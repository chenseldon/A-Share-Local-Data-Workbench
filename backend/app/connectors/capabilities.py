from __future__ import annotations

import importlib.util
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from ..free_stockdb_sdk import configure_free_stockdb_sdk_path


@dataclass(frozen=True)
class ConnectorCapability:
    module: str
    function: str
    source: str
    description: str
    status: str
    requires_key: bool = False
    optional_dependency: str | None = None
    note: str | None = None


_CAPABILITIES: tuple[ConnectorCapability, ...] = (
    ConnectorCapability("market", "free_stockdb_kline", "free-stockdb local SDK", "Local daily K-line data from stockdb.exe on 127.0.0.1:7899.", "wired"),
    ConnectorCapability("market", "free_stockdb_security", "free-stockdb local SDK", "Resolve complete code searches from the latest local K-line row.", "wired"),
    ConnectorCapability("market", "free_stockdb_zb", "free-stockdb zhibiao SDK", "On-demand technical indicators through zb.get().", "wired"),
    ConnectorCapability("market", "tencent_quote", "Tencent Finance", "Latest quote, valuation and limit fields.", "wired"),
    ConnectorCapability("market", "baidu_kline_with_ma", "Baidu K-line", "Disabled as a chart source; retained only as a reference connector.", "planned"),
    ConnectorCapability("market", "mootdx_bars", "mootdx", "TDX K-line and multi-period bars.", "optional_dependency_missing", optional_dependency="mootdx"),
    ConnectorCapability("market", "mootdx_quotes", "mootdx", "Five-level quotes and transaction snapshots.", "optional_dependency_missing", optional_dependency="mootdx"),
    ConnectorCapability("reports", "eastmoney_reports", "Eastmoney reportapi", "Company research reports and PDF URL metadata.", "wired"),
    ConnectorCapability("reports", "eastmoney_industry_reports", "Eastmoney reportapi", "Industry research reports.", "wired"),
    ConnectorCapability("reports", "eastmoney_pdf_url", "Eastmoney PDF", "PDF URL generated from Eastmoney infoCode; local PDF download is not implemented.", "prepared"),
    ConnectorCapability("reports", "ths_eps_forecast", "10jqka", "Consensus EPS from 10jqka worth page.", "optional_dependency_missing", optional_dependency="pandas"),
    ConnectorCapability("reports", "iwencai_search", "iwencai", "Natural-language research and screening search.", "needs_key", requires_key=True, note="IWENCAI_API_KEY"),
    ConnectorCapability("signals", "ths_hot_reason", "10jqka", "Strong stocks and theme reasons.", "planned", note="Endpoint has not been revalidated in this runtime."),
    ConnectorCapability(
        "signals",
        "hsgt_realtime",
        "Eastmoney/HKEX",
        "Northbound capital flow status boundary.",
        "prepared",
        note="Shenzhen Connect minute data reliability declined after 2024-08 disclosure changes; authoritative daily data should be checked from HKEX.",
    ),
    ConnectorCapability("signals", "eastmoney_concept_blocks", "Eastmoney push2", "Stock industry/concept/region block ownership.", "wired"),
    ConnectorCapability("signals", "free_stockdb_bk", "free-stockdb zhibiao SDK", "Concept and Shenwan industry mapping through bk.get().", "wired"),
    ConnectorCapability("signals", "eastmoney_fund_flow_minute", "Eastmoney push2", "Intraday minute fund flow.", "wired"),
    ConnectorCapability("signals", "dragon_tiger_board", "Eastmoney datacenter", "Stock dragon-tiger records.", "wired"),
    ConnectorCapability("signals", "daily_dragon_tiger", "Eastmoney datacenter", "Full-market dragon-tiger board.", "planned"),
    ConnectorCapability("signals", "lockup_expiry", "Eastmoney datacenter", "Unlock schedule.", "planned"),
    ConnectorCapability("signals", "industry_comparison", "Eastmoney push2", "Industry comparison and ranking.", "wired"),
    ConnectorCapability("chip_liquidity", "margin_trading", "Eastmoney datacenter", "Margin financing detail.", "wired"),
    ConnectorCapability("chip_liquidity", "block_trade", "Eastmoney datacenter", "Block trades.", "wired"),
    ConnectorCapability("chip_liquidity", "holder_num_change", "Eastmoney datacenter", "Shareholder count changes.", "wired"),
    ConnectorCapability("chip_liquidity", "dividend_history", "Eastmoney datacenter", "Dividend and bonus history.", "wired"),
    ConnectorCapability("chip_liquidity", "stock_fund_flow_120d", "Eastmoney push2his", "120-trading-day stock fund flow.", "wired"),
    ConnectorCapability("chip_liquidity", "fund_flow_backup", "Sina", "Daily four-tier fund-flow backup when Eastmoney push2his is unavailable.", "prepared"),
    ConnectorCapability("news", "eastmoney_stock_news", "Eastmoney search-api-web", "Stock news.", "wired"),
    ConnectorCapability("news", "cls_telegraph", "CLS", "CLS telegrams with local signature.", "wired"),
    ConnectorCapability("news", "eastmoney_global_news", "Eastmoney", "Global information feed.", "wired"),
    ConnectorCapability("fundamentals", "eastmoney_stock_info", "Eastmoney push2", "Stock profile, shares, market cap and listing date.", "wired"),
    ConnectorCapability("fundamentals", "sina_financial_report", "Sina Finance", "Balance sheet, income statement and cash flow records.", "wired"),
    ConnectorCapability("fundamentals", "mootdx_finance", "mootdx", "TDX finance snapshot and F10 profile.", "optional_dependency_missing", optional_dependency="mootdx"),
    ConnectorCapability("announcements", "cninfo_announcements", "CNINFO", "Full-text announcement search and detail URL.", "wired"),
    ConnectorCapability("announcements", "mootdx_f10_latest", "mootdx", "TDX F10 latest tips and announcement summary.", "optional_dependency_missing", optional_dependency="mootdx"),
    ConnectorCapability("announcements", "announcements_backup", "SZSE official / Eastmoney", "Backup announcement route documented by a-stock-data; not used as the default CNINFO source.", "prepared"),
    ConnectorCapability("etf_options", "sina_option_codes", "Sina hq.sinajs", "ETF option contract list.", "wired"),
    ConnectorCapability("etf_options", "sina_option_tquote", "Sina hq.sinajs", "ETF option T-quote.", "wired"),
    ConnectorCapability("etf_options", "sina_option_greeks", "Sina hq.sinajs", "Greeks and implied volatility.", "wired"),
)
_FREE_STOCKDB_REQUIREMENTS = {
    "free_stockdb_kline": {"stock_sdk": "stock_sdk_available"},
    "free_stockdb_security": {"stock_sdk": "stock_sdk_available"},
    "free_stockdb_zb": {"zhibiao": "zhibiao_available"},
    "free_stockdb_bk": {"zhibiao": "zhibiao_available"},
}


def list_capabilities() -> list[dict[str, object]]:
    now = datetime.now(UTC).isoformat()
    capabilities: list[dict[str, object]] = []
    for capability in _CAPABILITIES:
        item = asdict(capability)
        status = capability.status
        note = capability.note
        if capability.optional_dependency and importlib.util.find_spec(capability.optional_dependency) is not None:
            status = "planned"
        if capability.requires_key and os.getenv(str(capability.note or "")):
            status = "planned"
        requirements = _FREE_STOCKDB_REQUIREMENTS.get(capability.function)
        if requirements:
            sdk_status = configure_free_stockdb_sdk_path()
            missing = [name for name, field in requirements.items() if not getattr(sdk_status, field)]
            if missing:
                status = "sdk_missing"
                note = (
                    f"Missing {', '.join(missing)}. {sdk_status.error} "
                    f"Current path: {sdk_status.configured_path or 'not configured'}."
                )
        item["status"] = status
        item["note"] = note
        item["checked_at"] = now
        capabilities.append(item)
    return capabilities


def capability_summary_by_module() -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for capability in list_capabilities():
        module = str(capability["module"])
        status = str(capability["status"])
        summary.setdefault(module, {})
        summary[module][status] = summary[module].get(status, 0) + 1
    return summary
