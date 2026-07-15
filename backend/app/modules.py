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
    sources: tuple[str, ...]
    planned_fields: tuple[str, ...]


MODULES: tuple[ModuleDefinition, ...] = (
    ModuleDefinition(
        "market",
        "Market",
        "行情层",
        "K-line with MA5/MA10/MA20, latest quote, order book placeholder, valuation, index and ETF context.",
        "configured",
        ("market_bars", "market_quotes"),
        ("Tencent Finance", "Baidu K-line", "mootdx optional"),
        ("Daily K-line", "MA5/10/20", "latest quote", "PE/PB/market cap", "index/ETF"),
    ),
    ModuleDefinition(
        "reports",
        "Research Reports",
        "研报层",
        "Company reports, industry reports, ratings, PDF links, consensus EPS and natural-language search.",
        "configured",
        ("reports",),
        ("Eastmoney reportapi", "10jqka", "iwencai optional"),
        ("company reports", "industry reports", "ratings", "EPS forecast", "PDF URL"),
    ),
    ModuleDefinition(
        "signals",
        "Signals",
        "信号层",
        "Strong stocks, theme attribution, northbound flow, sector ownership, ranking and event-driven signals.",
        "prepared",
        ("module_records",),
        ("10jqka", "Eastmoney"),
        ("strong stocks", "themes", "northbound flow", "sector mapping", "dragon tiger list"),
    ),
    ModuleDefinition(
        "chip_liquidity",
        "Chip And Liquidity",
        "资金面 / 筹码层",
        "Margin financing, block trades, shareholder counts, dividends and multi-horizon money flow.",
        "configured",
        ("money_flow",),
        ("Eastmoney datacenter", "Eastmoney push2"),
        ("margin financing", "block trades", "shareholder counts", "dividends", "120-day money flow"),
    ),
    ModuleDefinition(
        "news",
        "News",
        "新闻层",
        "Company news, CLS telegrams and global market context with mutually backed sources.",
        "not_configured",
        (),
        ("Eastmoney", "CLS"),
        ("company news", "CLS telegrams", "global information"),
    ),
    ModuleDefinition(
        "fundamentals",
        "Fundamentals",
        "基础数据",
        "Financial snapshots, F10 company profile and three financial statements.",
        "configured",
        ("fundamentals", "module_records"),
        ("mootdx optional", "Eastmoney", "Sina"),
        ("37 quarterly fields", "F10 categories", "balance sheet", "income statement", "cash flow"),
    ),
    ModuleDefinition(
        "announcements",
        "Announcements",
        "公告层",
        "SSE, SZSE and BSE announcements with CNINFO search and PDF links where available.",
        "configured",
        ("announcements",),
        ("CNINFO", "mootdx optional"),
        ("announcement title", "published time", "PDF URL", "exchange scope"),
    ),
    ModuleDefinition(
        "limit_up",
        "Limit-Up Board",
        "打板层",
        "Limit-up, broken-board, down-limit, yesterday limit-up, theme reason and board-height structure.",
        "prepared",
        ("limit_up_pool",),
        ("Eastmoney push2ex", "10jqka"),
        ("limit-up pool", "broken board", "down-limit pool", "limit-up reason", "board height"),
    ),
    ModuleDefinition(
        "etf_options",
        "ETF Options",
        "期权层",
        "ETF option chains, T-quotes, Greeks and implied volatility.",
        "not_configured",
        (),
        ("Sina hq.sinajs"),
        ("option chain", "T quote", "Delta", "Gamma", "Theta", "Vega", "IV"),
    ),
    ModuleDefinition(
        "sentiment",
        "Sentiment",
        "舆情互动层",
        "Investor Q&A, hot rankings, popularity rankings and concept matches.",
        "not_configured",
        (),
        ("CNINFO Hudongyi", "10jqka", "Eastmoney"),
        ("interactive Q&A", "10jqka hot ranking", "Eastmoney popularity", "concept hit"),
    ),
)


MODULE_BY_ID = {module.id: module for module in MODULES}
