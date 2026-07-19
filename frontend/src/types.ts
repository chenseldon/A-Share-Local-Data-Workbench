export type FreshnessState =
  | "fresh"
  | "stale"
  | "failed"
  | "not_collected"
  | "not_configured"
  | "ok"
  | "prepared";

export type DataRow = Record<string, unknown>;

export interface ModuleDefinition {
  id: string;
  label: string;
  layer: string;
  description: string;
  status: "configured" | "prepared" | "not_configured";
  tables: string[];
  sources: string[];
  planned_fields: string[];
  capabilities?: Record<string, number>;
}

export interface ConnectorCapability {
  module: string;
  function: string;
  source: string;
  description: string;
  status: FreshnessState | "wired" | "planned" | "needs_key" | "optional_dependency_missing";
  requires_key: boolean;
  optional_dependency: string | null;
  note: string | null;
  checked_at: string;
}

export interface Security {
  symbol: string;
  name: string;
  exchange: string;
  asset_type: string;
  listing_date: string | null;
  sector: string | null;
  is_active: boolean;
  source: string;
  fetched_at: string;
}

export interface MarketBar {
  symbol: string;
  trade_date: string;
  chart_time?: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  amount: number | null;
  adjustment: string;
  source: string;
  fetched_at: string;
}

export interface MarketQuote {
  symbol: string;
  price_time: string | null;
  last_price: number | null;
  previous_close: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
  amount: number | null;
  bid1: number | null;
  ask1: number | null;
  change_amt?: number | null;
  change_pct?: number | null;
  turnover_pct?: number | null;
  pe_ttm?: number | null;
  amplitude_pct?: number | null;
  total_market_cap?: number | null;
  float_market_cap?: number | null;
  pb?: number | null;
  limit_up?: number | null;
  limit_down?: number | null;
  volume_ratio?: number | null;
  pe_static?: number | null;
  source: string;
  fetched_at: string;
}

export interface ChartBar extends MarketBar {
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  dif?: number | null;
  dea?: number | null;
  macd?: number | null;
  k?: number | null;
  d?: number | null;
  j?: number | null;
  rsi?: number | null;
  upper?: number | null;
  mid?: number | null;
  lower?: number | null;
  [key: string]: unknown;
}

export interface Fundamental {
  symbol: string;
  report_period: string;
  eps: number | null;
  roe: number | null;
  net_profit: number | null;
  revenue: number | null;
  total_market_cap: number | null;
  pe_ttm: number | null;
  pb: number | null;
  source: string;
  fetched_at: string;
}

export interface Announcement {
  id: string;
  symbol: string;
  title: string;
  published_at: string;
  url: string | null;
  source: string;
  fetched_at: string;
}

export interface ResearchReport {
  id: string;
  symbol: string;
  title: string;
  institution: string | null;
  analyst: string | null;
  rating: string | null;
  report_date: string;
  eps_forecast: string | null;
  url: string | null;
  source: string;
  fetched_at: string;
}

export interface MoneyFlow {
  symbol: string;
  trade_date: string;
  main_net_inflow: number | null;
  retail_net_inflow: number | null;
  turnover_rate: number | null;
  source: string;
  fetched_at: string;
}

export interface SecurityOverview {
  symbol: string;
  security: Security;
  market: MarketBar | null;
  quote: MarketQuote | null;
  fundamentals: Fundamental | null;
  announcements: Announcement[];
  reports: ResearchReport[];
  money_flow: MoneyFlow[];
  freshness: Record<string, FreshnessState>;
}

export interface SearchResponse {
  query: string;
  rows: Security[];
  remote_status?: FreshnessState | "fetched" | "not_needed" | "preloaded" | "preload_empty";
  remote_error?: string | null;
}

export interface SecurityUniverseStatus {
  count: number;
  last_fetched_at: string | null;
  source: string;
}

export interface BoardMappingResponse {
  symbol: string;
  concepts: string[];
  sw_l1: string[];
  sw_l2: string[];
  sw_l3: string[];
  source: string;
  fetched_at: string;
}

export interface ModuleDataResponse {
  module: string;
  status: FreshnessState | "not_found";
  rows: DataRow[];
  market?: MarketModuleData;
  announcements?: AnnouncementsModuleData;
  reports?: ReportsModuleData;
  signals?: SignalsModuleData;
  news?: NewsModuleData;
  chip_liquidity?: ChipLiquidityModuleData;
  limit_up?: LimitUpModuleData;
}

export interface MarketModuleSection {
  source?: string | null;
  fetched_at?: string | null;
  [key: string]: unknown;
}

export interface MarketModuleCapability {
  status: string;
  source: string;
  note?: string | null;
  rows?: DataRow[];
  entries?: Array<{ label: string; symbol: string }>;
}

export interface MarketSourceStatus {
  source: string;
  module: string;
  status: string;
  last_success_at: string | null;
  last_failure_at: string | null;
  last_error: string | null;
  updated_at: string | null;
}

export interface MarketModuleData {
  symbol: string | null;
  quote_snapshot: MarketQuote | null;
  latest_bar: MarketBar | null;
  recent_bars: MarketBar[];
  valuation: MarketModuleSection;
  limits: MarketModuleSection;
  liquidity: MarketModuleSection;
  order_book: MarketModuleCapability;
  index_etf: MarketModuleCapability;
  source_status: MarketSourceStatus[];
}

export interface ReportModuleCard {
  label: string;
  value: unknown;
  status?: string | null;
}

export interface ReportModuleSection {
  id: string;
  title: string;
  source?: string | null;
  fetched_at?: string | null;
  cards: ReportModuleCard[];
}

export interface ReportModuleTableColumn {
  key: string;
  label: string;
}

export interface ReportModuleTable {
  id: string;
  title: string;
  rows: DataRow[];
  columns: ReportModuleTableColumn[];
}

export interface SignalsModuleData {
  symbol: string | null;
  sections: ReportModuleSection[];
  tables: ReportModuleTable[];
  source_status: MarketSourceStatus[];
}

export interface AnnouncementsModuleData {
  symbol: string | null;
  sections: ReportModuleSection[];
  tables: ReportModuleTable[];
  source_status: MarketSourceStatus[];
}

export interface NewsModuleData {
  symbol: string | null;
  sections: ReportModuleSection[];
  tables: ReportModuleTable[];
  source_status: MarketSourceStatus[];
}

export interface ChipLiquidityModuleData {
  symbol: string | null;
  sections: ReportModuleSection[];
  tables: ReportModuleTable[];
  source_status: MarketSourceStatus[];
}

export interface LimitUpModuleData {
  symbol: string | null;
  trade_date: string | null;
  sections: ReportModuleSection[];
  tables: ReportModuleTable[];
  source_status: MarketSourceStatus[];
  selected_symbol_hits: DataRow[];
}

export interface ReportsModuleData {
  symbol: string | null;
  sections: ReportModuleSection[];
  tables: ReportModuleTable[];
  source_status: MarketSourceStatus[];
}

export interface DataJob {
  id: string;
  job_type: string;
  module: string;
  source: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  records_written: number;
  error_message: string | null;
}

export interface SourceHealth {
  source: string;
  module: string;
  status: FreshnessState;
  last_success_at: string | null;
  last_failure_at: string | null;
  last_error: string | null;
  updated_at: string;
}

export interface RowsResponse<T> {
  rows: T[];
}

export interface QuoteResponse {
  symbol: string;
  status: FreshnessState;
  quote: MarketQuote | null;
}

export interface ChartResponse {
  symbol: string;
  period: string;
  adjustment: string;
  status: FreshnessState;
  rows: ChartBar[];
  requested_indicators?: string[];
  indicator_status?: FreshnessState | "not_requested";
  indicator_error?: string | null;
}

export interface RefreshResponse {
  symbol?: string;
  module?: string;
  status: FreshnessState;
  records_written: number;
  source?: string;
  candidates_scanned?: number;
  prefixes_scanned?: number;
  expected_source_count?: number;
  module_results?: Record<string, unknown>;
}
