from __future__ import annotations

import importlib.util
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime


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
    ConnectorCapability("market", "tencent_quote", "Tencent Finance", "Latest quote, valuation and limit fields.", "wired"),
    ConnectorCapability("market", "baidu_kline_with_ma", "Baidu K-line", "Disabled as a chart source; retained only as a reference connector.", "planned"),
    ConnectorCapability("market", "mootdx_bars", "mootdx", "TDX K-line and multi-period bars.", "optional_dependency_missing", optional_dependency="mootdx"),
    ConnectorCapability("market", "mootdx_quotes", "mootdx", "Five-level quotes and transaction snapshots.", "optional_dependency_missing", optional_dependency="mootdx"),
    ConnectorCapability("reports", "eastmoney_reports", "Eastmoney reportapi", "Company research reports and PDF URL metadata.", "wired"),
    ConnectorCapability("reports", "eastmoney_industry_reports", "Eastmoney reportapi", "Industry research reports.", "planned"),
    ConnectorCapability("reports", "download_pdf", "Eastmoney PDF", "PDF download with Eastmoney referer.", "planned"),
    ConnectorCapability("reports", "ths_eps_forecast", "10jqka", "Consensus EPS from 10jqka worth page.", "optional_dependency_missing", optional_dependency="pandas"),
    ConnectorCapability("reports", "iwencai_search", "iwencai", "Natural-language research and screening search.", "needs_key", requires_key=True, note="IWENCAI_API_KEY"),
    ConnectorCapability("signals", "ths_hot_reason", "10jqka", "Strong stocks and theme reasons.", "planned"),
    ConnectorCapability("signals", "hsgt_realtime", "Eastmoney", "Northbound capital flow.", "planned"),
    ConnectorCapability("signals", "eastmoney_concept_blocks", "Eastmoney push2", "Stock industry/concept/region block ownership.", "wired"),
    ConnectorCapability("signals", "eastmoney_fund_flow_minute", "Eastmoney push2", "Intraday minute fund flow.", "planned"),
    ConnectorCapability("signals", "dragon_tiger_board", "Eastmoney datacenter", "Stock dragon-tiger records.", "planned"),
    ConnectorCapability("signals", "daily_dragon_tiger", "Eastmoney datacenter", "Full-market dragon-tiger board.", "planned"),
    ConnectorCapability("signals", "lockup_expiry", "Eastmoney datacenter", "Unlock schedule.", "planned"),
    ConnectorCapability("signals", "industry_comparison", "Eastmoney", "Industry comparison and ranking.", "planned"),
    ConnectorCapability("chip_liquidity", "margin_trading", "Eastmoney datacenter", "Margin financing detail.", "planned"),
    ConnectorCapability("chip_liquidity", "block_trade", "Eastmoney datacenter", "Block trades.", "planned"),
    ConnectorCapability("chip_liquidity", "holder_num_change", "Eastmoney datacenter", "Shareholder count changes.", "planned"),
    ConnectorCapability("chip_liquidity", "dividend_history", "Eastmoney datacenter", "Dividend and bonus history.", "planned"),
    ConnectorCapability("chip_liquidity", "stock_fund_flow_120d", "Eastmoney push2his", "120-trading-day stock fund flow.", "wired"),
    ConnectorCapability("news", "eastmoney_stock_news", "Eastmoney search-api-web", "Stock news.", "planned"),
    ConnectorCapability("news", "cls_telegraph", "CLS", "CLS telegrams with local signature.", "planned"),
    ConnectorCapability("news", "eastmoney_global_news", "Eastmoney", "Global information feed.", "planned"),
    ConnectorCapability("fundamentals", "eastmoney_stock_info", "Eastmoney push2", "Stock profile, shares, market cap and listing date.", "wired"),
    ConnectorCapability("fundamentals", "sina_financial_report", "Sina Finance", "Balance sheet, income statement and cash flow records.", "wired"),
    ConnectorCapability("fundamentals", "mootdx_finance", "mootdx", "TDX finance snapshot and F10 profile.", "optional_dependency_missing", optional_dependency="mootdx"),
    ConnectorCapability("announcements", "cninfo_announcements", "CNINFO", "Full-text announcement search and detail URL.", "wired"),
    ConnectorCapability("announcements", "mootdx_f10_latest", "mootdx", "TDX F10 latest tips and announcement summary.", "optional_dependency_missing", optional_dependency="mootdx"),
    ConnectorCapability("limit_up", "em_zt_pool", "Eastmoney push2ex", "Limit-up pool.", "planned"),
    ConnectorCapability("limit_up", "em_zb_pool", "Eastmoney push2ex", "Broken-board pool.", "planned"),
    ConnectorCapability("limit_up", "em_dt_pool", "Eastmoney push2ex", "Down-limit pool.", "planned"),
    ConnectorCapability("limit_up", "em_yzt_pool", "Eastmoney push2ex", "Yesterday limit-up pool.", "planned"),
    ConnectorCapability("limit_up", "ths_limit_up_pool", "10jqka", "Limit-up reason, board type and seal quality.", "planned"),
    ConnectorCapability("limit_up", "limit_up_sentiment", "Eastmoney push2ex", "Limit-up sentiment metrics.", "planned"),
    ConnectorCapability("etf_options", "sina_option_codes", "Sina hq.sinajs", "ETF option contract list.", "planned"),
    ConnectorCapability("etf_options", "sina_option_tquote", "Sina hq.sinajs", "ETF option T-quote.", "planned"),
    ConnectorCapability("etf_options", "sina_option_greeks", "Sina hq.sinajs", "Greeks and implied volatility.", "planned"),
    ConnectorCapability("sentiment", "cninfo_irm", "CNINFO Hudongyi", "Investor Q&A.", "planned"),
    ConnectorCapability("sentiment", "ths_hot_list", "10jqka", "10jqka hot ranking.", "planned"),
    ConnectorCapability("sentiment", "em_hot_rank", "Eastmoney appdata", "Eastmoney popularity ranking.", "planned"),
    ConnectorCapability("sentiment", "em_hot_concept", "Eastmoney appdata", "Hot concept hits for a stock.", "planned"),
)


def list_capabilities() -> list[dict[str, object]]:
    now = datetime.now(UTC).isoformat()
    capabilities: list[dict[str, object]] = []
    for capability in _CAPABILITIES:
        item = asdict(capability)
        status = capability.status
        if capability.optional_dependency and importlib.util.find_spec(capability.optional_dependency) is not None:
            status = "planned"
        if capability.requires_key and os.getenv(str(capability.note or "")):
            status = "planned"
        item["status"] = status
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
