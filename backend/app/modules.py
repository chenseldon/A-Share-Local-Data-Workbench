from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleDefinition:
    id: str
    label: str
    layer: str
    description: str
    status: str
    tables: tuple[str, ...]


MODULES: tuple[ModuleDefinition, ...] = (
    ModuleDefinition(
        "market",
        "Market",
        "行情层",
        "K-line, quotes, valuation, index and ETF market context.",
        "configured",
        ("market_bars",),
    ),
    ModuleDefinition(
        "reports",
        "Research Reports",
        "研报层",
        "Company reports, industry reports, ratings and EPS forecasts.",
        "configured",
        ("reports",),
    ),
    ModuleDefinition(
        "signals",
        "Signals",
        "信号层",
        "Themes, northbound flow, rankings and event-driven signals.",
        "not_configured",
        (),
    ),
    ModuleDefinition(
        "chip_liquidity",
        "Chip And Liquidity",
        "资金面 / 筹码层",
        "Margin financing, block trades, shareholder counts and dividends.",
        "prepared",
        ("money_flow",),
    ),
    ModuleDefinition(
        "news",
        "News",
        "新闻层",
        "Company news, market telegrams and global market context.",
        "not_configured",
        (),
    ),
    ModuleDefinition(
        "fundamentals",
        "Fundamentals",
        "基础数据",
        "F10, company profile, financial snapshots and statements.",
        "configured",
        ("fundamentals",),
    ),
    ModuleDefinition(
        "announcements",
        "Announcements",
        "公告层",
        "Exchange and CNINFO announcements with PDF links where available.",
        "configured",
        ("announcements",),
    ),
    ModuleDefinition(
        "limit_up",
        "Limit-Up Board",
        "打板层",
        "Limit-up, broken-board, down-limit and board-height structure.",
        "prepared",
        ("limit_up_pool",),
    ),
    ModuleDefinition(
        "etf_options",
        "ETF Options",
        "ETF 期权层",
        "Contract chains, T-quotes, Greeks and implied volatility.",
        "not_configured",
        (),
    ),
    ModuleDefinition(
        "sentiment",
        "Sentiment",
        "舆情互动层",
        "Interactive Q&A, hot rankings, popularity and concept matches.",
        "not_configured",
        (),
    ),
)


MODULE_BY_ID = {module.id: module for module in MODULES}
