import { FileText, LineChart, Newspaper, WalletCards } from "lucide-react";
import type { ChartPeriod } from "../api";
import type { BoardMappingResponse, ChartResponse, Security, SecurityOverview as SecurityOverviewType } from "../types";
import { DataTable } from "./DataTable";
import { EmptyState } from "./EmptyState";
import { KLineChart } from "./KLineChart";
import { StatusBadge } from "./StatusBadge";

interface SecurityOverviewProps {
  overview: SecurityOverviewType | null;
  loading: boolean;
  error: string | null;
  selectedSymbol: string | null;
  chart: ChartResponse | null;
  chartLoading: boolean;
  chartError: string | null;
  boards: BoardMappingResponse | null;
  boardError: string | null;
  chartIndicators: string[];
  onChartIndicatorsChange: (indicators: string[]) => void;
  chartPeriod: ChartPeriod;
  onChartPeriodChange: (period: ChartPeriod) => void;
  onRefreshMarket: () => void;
  marketRefreshing: boolean;
  searchQuery: string;
  searchResults: Security[];
  isSearching: boolean;
  onSearchQueryChange: (value: string) => void;
  onSelectSymbol: (symbol: string) => void;
  apiHealthError: string | null;
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function SecurityOverview({
  overview,
  loading,
  error,
  selectedSymbol,
  chart,
  chartLoading,
  chartError,
  boards,
  boardError,
  chartIndicators,
  onChartIndicatorsChange,
  chartPeriod,
  onChartPeriodChange,
  onRefreshMarket,
  marketRefreshing,
  searchQuery,
  searchResults,
  isSearching,
  onSearchQueryChange,
  onSelectSymbol,
  apiHealthError
}: SecurityOverviewProps) {
  if (!selectedSymbol) {
    return (
      <div className="security-start-screen">
        <section className="security-start-card">
          <div>
            <span className="start-eyebrow">A-Share K-Line Workspace</span>
            <h1>Search a symbol to start</h1>
            <p>Enter a six-digit code or Chinese name to load local free-stockdb K-line data, indicators, boards and module context.</p>
          </div>
          <div className="start-search-box">
            <input
              aria-label="Search or resolve A-share symbol"
              value={searchQuery}
              placeholder="输入股票代码或中文名，例如 600519 / 贵州茅台"
              onChange={(event) => onSearchQueryChange(event.target.value)}
            />
            {(searchQuery || isSearching) && (
              <div className="start-search-results">
                {isSearching && <div className="start-search-row muted">Searching local free-stockdb directory...</div>}
                {!isSearching && searchResults.length === 0 && searchQuery && (
                  <div className="start-search-row muted">No local free-stockdb match.</div>
                )}
                {searchResults.slice(0, 5).map((result) => (
                  <button key={result.symbol} className="start-search-row" type="button" onClick={() => onSelectSymbol(result.symbol)}>
                    <span>{result.symbol}</span>
                    <strong>{result.name}</strong>
                    <small>{result.exchange}</small>
                  </button>
                ))}
              </div>
            )}
          </div>
          {apiHealthError && (
            <div className="api-diagnostic">
              API is not reachable from this browser. Open http://127.0.0.1:5173/ and make sure the backend is running on 127.0.0.1:8000.
              <small>{apiHealthError}</small>
            </div>
          )}
        </section>
      </div>
    );
  }

  if (loading) {
    return <div className="panel loading-panel">Loading local security context...</div>;
  }

  if (error) {
    return (
      <EmptyState
        title={`No local overview for ${selectedSymbol}`}
        detail="The backend is reachable, but this symbol has not been collected or seeded in the local database."
      />
    );
  }

  if (!overview) {
    return <EmptyState title="No symbol selected" detail="Search a local security to inspect cross-module context." />;
  }

  return (
    <div className="content-grid security-workspace-grid">
      <KLineChart
        rows={chart?.rows ?? []}
        quote={overview.quote}
        security={overview.security}
        boards={boards}
        boardError={boardError}
        enabledIndicators={chartIndicators}
        onIndicatorsChange={onChartIndicatorsChange}
        period={chartPeriod}
        onPeriodChange={onChartPeriodChange}
        indicatorStatus={chart?.indicator_status}
        indicatorError={chart?.indicator_error ?? null}
        loading={chartLoading}
        error={chartError}
        onRefresh={onRefreshMarket}
        refreshing={marketRefreshing}
        searchQuery={searchQuery}
        searchResults={searchResults}
        isSearching={isSearching}
        onSearchQueryChange={onSearchQueryChange}
        onSelectSymbol={onSelectSymbol}
      />

      <section className="metric-row">
        <div className="metric-panel">
          <LineChart aria-hidden="true" size={18} />
          <span>Latest Price</span>
          <strong>{formatNumber(overview.quote?.last_price ?? overview.market?.close)}</strong>
          <small>{overview.quote?.price_time ?? overview.market?.trade_date ?? "No market data"}</small>
        </div>
        <div className="metric-panel">
          <FileText aria-hidden="true" size={18} />
          <span>PE TTM</span>
          <strong>{formatNumber(overview.fundamentals?.pe_ttm)}</strong>
          <small>{overview.fundamentals?.report_period ?? "No fundamentals"}</small>
        </div>
        <div className="metric-panel">
          <WalletCards aria-hidden="true" size={18} />
          <span>Main Inflow</span>
          <strong>{formatNumber(overview.money_flow[0]?.main_net_inflow)}</strong>
          <small>{overview.money_flow[0]?.trade_date ?? "No money flow"}</small>
        </div>
        <div className="metric-panel">
          <Newspaper aria-hidden="true" size={18} />
          <span>Local Events</span>
          <strong>{overview.announcements.length + overview.reports.length}</strong>
          <small>Announcements + reports</small>
        </div>
      </section>

      <section className="panel split-panel">
        <div>
          <h2>Freshness</h2>
          <p>Local collection state by module.</p>
        </div>
        <div className="freshness-grid">
          {Object.entries(overview.freshness).map(([key, status]) => (
            <div key={key} className="freshness-item">
              <span>{key.replaceAll("_", " ")}</span>
              <StatusBadge status={status} />
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Latest Quote</h2>
            <p>Latest cached public-source quote. Refreshing writes to DuckDB before display.</p>
          </div>
        </div>
        <DataTable rows={overview.quote ? [overview.quote] : []} />
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Market Bars</h2>
            <p>Source, trade date, adjustment and fetch time are shown with each local row.</p>
          </div>
        </div>
        <DataTable rows={overview.market ? [overview.market] : []} />
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Fundamentals</h2>
            <p>Fetched on confirmed symbol refresh when the upstream connector is available.</p>
          </div>
        </div>
        <DataTable rows={overview.fundamentals ? [overview.fundamentals] : []} />
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Announcements</h2>
            <p>Fetched on confirmed symbol refresh; unavailable upstream data is shown as an empty state.</p>
          </div>
        </div>
        <DataTable rows={overview.announcements} />
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Research Reports</h2>
            <p>Fetched on confirmed symbol refresh; results keep source and fetch timestamp fields.</p>
          </div>
        </div>
        <DataTable rows={overview.reports} />
      </section>
    </div>
  );
}
