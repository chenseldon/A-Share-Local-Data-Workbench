import type { ModuleDefinition } from "../types";

export const fallbackModules: ModuleDefinition[] = [
  {
    id: "market",
    label: "Market",
    layer: "行情层",
    description: "K-line with MA5/MA10/MA20, latest quote, order book placeholder, valuation, index and ETF context.",
    status: "configured",
    tables: ["market_bars", "market_quotes"],
    sources: ["Tencent Finance", "Baidu K-line", "mootdx optional"],
    planned_fields: ["Daily K-line", "MA5/10/20", "latest quote", "PE/PB/market cap", "index/ETF"],
    capabilities: { wired: 3, optional_dependency_missing: 2 }
  },
  {
    id: "reports",
    label: "Research Reports",
    layer: "研报层",
    description: "Company reports, industry reports, ratings, PDF links, consensus EPS and natural-language search.",
    status: "configured",
    tables: ["reports"],
    sources: ["Eastmoney reportapi", "10jqka", "iwencai optional"],
    planned_fields: ["company reports", "industry reports", "ratings", "EPS forecast", "PDF URL"],
    capabilities: { wired: 2, prepared: 1, needs_key: 1, optional_dependency_missing: 1 }
  },
  {
    id: "signals",
    label: "Signals",
    layer: "信号层",
    description: "Strong stocks, theme attribution, northbound flow, sector ownership, ranking and event-driven signals.",
    status: "configured",
    tables: ["module_records"],
    sources: ["Eastmoney", "free-stockdb", "10jqka planned", "HKEX boundary"],
    planned_fields: ["sector mapping", "minute fund flow", "dragon tiger list", "industry ranking", "northbound boundary"],
    capabilities: { wired: 5, prepared: 1, planned: 1 }
  },
  {
    id: "chip_liquidity",
    label: "Chip And Liquidity",
    layer: "资金面 / 筹码层",
    description: "Margin financing, block trades, shareholder counts, dividends and multi-horizon money flow.",
    status: "configured",
    tables: ["money_flow", "module_records"],
    sources: ["Eastmoney datacenter", "Eastmoney push2"],
    planned_fields: ["margin financing", "block trades", "shareholder counts", "dividends", "120-day money flow"],
    capabilities: { wired: 5, prepared: 1 }
  },
  {
    id: "news",
    label: "News",
    layer: "新闻层",
    description: "Company news, CLS telegrams and global market context with mutually backed sources.",
    status: "configured",
    tables: ["module_records"],
    sources: ["Eastmoney", "CLS"],
    planned_fields: ["company news", "CLS telegrams", "global information"],
    capabilities: { wired: 3 }
  },
  {
    id: "fundamentals",
    label: "Fundamentals",
    layer: "基础数据",
    description: "Financial snapshots, F10 company profile and three financial statements.",
    status: "configured",
    tables: ["fundamentals", "module_records"],
    sources: ["mootdx optional", "Eastmoney", "Sina"],
    planned_fields: ["37 quarterly fields", "F10 categories", "balance sheet", "income statement", "cash flow"],
    capabilities: { wired: 4, optional_dependency_missing: 1 }
  },
  {
    id: "announcements",
    label: "Announcements",
    layer: "公告层",
    description: "SSE, SZSE and BSE announcements with CNINFO search and PDF links where available.",
    status: "configured",
    tables: ["announcements"],
    sources: ["CNINFO", "mootdx optional", "SZSE/Eastmoney backup prepared"],
    planned_fields: ["announcement title", "published time", "detail URL", "backup route status"],
    capabilities: { wired: 1, prepared: 2, optional_dependency_missing: 1 }
  },
  {
    id: "limit_up",
    label: "Limit-Up Board",
    layer: "打板层",
    description: "Limit-up, broken-board, down-limit, yesterday limit-up, theme reason and board-height structure.",
    status: "prepared",
    tables: ["limit_up_pool"],
    sources: ["Eastmoney push2ex", "10jqka"],
    planned_fields: ["limit-up pool", "broken board", "down-limit pool", "limit-up reason", "board height"],
    capabilities: { planned: 6 }
  },
  {
    id: "etf_options",
    label: "ETF Options",
    layer: "期权层",
    description: "ETF option chains, T-quotes, Greeks and implied volatility.",
    status: "not_configured",
    tables: [],
    sources: ["Sina hq.sinajs"],
    planned_fields: ["option chain", "T quote", "Delta", "Gamma", "Theta", "Vega", "IV"],
    capabilities: { planned: 3 }
  },
  {
    id: "sentiment",
    label: "Sentiment",
    layer: "舆情互动层",
    description: "Investor Q&A, hot rankings, popularity rankings and concept matches.",
    status: "configured",
    tables: ["module_records"],
    sources: ["CNINFO Hudongyi", "10jqka", "Eastmoney"],
    planned_fields: ["interactive Q&A", "10jqka hot ranking", "Eastmoney popularity", "concept hit"],
    capabilities: { wired: 4 }
  }
];
