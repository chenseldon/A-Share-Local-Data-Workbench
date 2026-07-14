import type { ModuleDefinition } from "../types";

export const fallbackModules: ModuleDefinition[] = [
  {
    id: "market",
    label: "Market",
    layer: "行情层",
    description: "K-line, quotes, valuation, index and ETF market context.",
    status: "configured",
    tables: ["market_bars"]
  },
  {
    id: "reports",
    label: "Research Reports",
    layer: "研报层",
    description: "Company reports, industry reports, ratings and EPS forecasts.",
    status: "configured",
    tables: ["reports"]
  },
  {
    id: "signals",
    label: "Signals",
    layer: "信号层",
    description: "Themes, northbound flow, rankings and event-driven signals.",
    status: "not_configured",
    tables: []
  },
  {
    id: "chip_liquidity",
    label: "Chip And Liquidity",
    layer: "资金面 / 筹码层",
    description: "Margin financing, block trades, shareholder counts and dividends.",
    status: "prepared",
    tables: ["money_flow"]
  },
  {
    id: "news",
    label: "News",
    layer: "新闻层",
    description: "Company news, market telegrams and global market context.",
    status: "not_configured",
    tables: []
  },
  {
    id: "fundamentals",
    label: "Fundamentals",
    layer: "基础数据",
    description: "F10, company profile, financial snapshots and statements.",
    status: "configured",
    tables: ["fundamentals"]
  },
  {
    id: "announcements",
    label: "Announcements",
    layer: "公告层",
    description: "Exchange and CNINFO announcements with PDF links where available.",
    status: "configured",
    tables: ["announcements"]
  },
  {
    id: "limit_up",
    label: "Limit-Up Board",
    layer: "打板层",
    description: "Limit-up, broken-board, down-limit and board-height structure.",
    status: "prepared",
    tables: ["limit_up_pool"]
  },
  {
    id: "etf_options",
    label: "ETF Options",
    layer: "ETF 期权层",
    description: "Contract chains, T-quotes, Greeks and implied volatility.",
    status: "not_configured",
    tables: []
  },
  {
    id: "sentiment",
    label: "Sentiment",
    layer: "舆情互动层",
    description: "Interactive Q&A, hot rankings, popularity and concept matches.",
    status: "not_configured",
    tables: []
  }
];
