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
  fundamentals: Fundamental | null;
  announcements: Announcement[];
  reports: ResearchReport[];
  money_flow: MoneyFlow[];
  freshness: Record<string, FreshnessState>;
}

export interface SearchResponse {
  query: string;
  rows: Security[];
}

export interface ModuleDataResponse {
  module: string;
  status: FreshnessState | "not_found";
  rows: DataRow[];
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
