import type { ChartPeriod } from "../api";
import type { BoardMappingResponse, ChartResponse, DataRow, Security, SecurityOverview as SecurityOverviewType } from "../types";
import { DataTable } from "./DataTable";
import { EmptyState } from "./EmptyState";
import { KLineChart } from "./KLineChart";

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

function formatSnapshotValue(value: number | string | null | undefined, suffix = ""): string {
  if (value === null || value === undefined || value === "") {
    return "NA";
  }
  if (typeof value === "number") {
    return `${Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}`;
  }
  return `${value}${suffix}`;
}

function renderLinkedTitle(value: unknown, column: { key: string }, row: DataRow) {
  if (column.key !== "title") {
    if (value === null || value === undefined) {
      return "-";
    }
    if (typeof value === "number") {
      return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 4 });
    }
    return String(value);
  }
  const title = value === null || value === undefined ? "-" : String(value);
  const url = typeof row.url === "string" && row.url ? row.url : null;
  if (!url) {
    return title;
  }
  return (
    <a className="table-title-link" href={url} target="_blank" rel="noreferrer">
      {title}
    </a>
  );
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

      {overview.quote && (
        <section className="panel market-snapshot-panel">
          <div className="section-heading">
            <div>
              <h2>Market Snapshot</h2>
              <p>Latest local quote fields. Missing values are shown as NA.</p>
            </div>
          </div>
          <div className="snapshot-grid">
            <div><span>换手率</span><strong>{formatSnapshotValue(overview.quote.turnover_pct, "%")}</strong></div>
            <div><span>涨幅%</span><strong>{formatSnapshotValue(overview.quote.change_pct, "%")}</strong></div>
            <div><span>振幅%</span><strong>{formatSnapshotValue(overview.quote.amplitude_pct, "%")}</strong></div>
            <div><span>量比</span><strong>{formatSnapshotValue(overview.quote.volume_ratio)}</strong></div>
            <div><span>总股本</span><strong>NA</strong></div>
            <div><span>流通股本</span><strong>NA</strong></div>
            <div><span>总市值</span><strong>{formatSnapshotValue(overview.quote.total_market_cap)}</strong></div>
            <div><span>流通市值</span><strong>{formatSnapshotValue(overview.quote.float_market_cap)}</strong></div>
            <div><span>市盈率</span><strong>{formatSnapshotValue(overview.quote.pe_ttm ?? overview.quote.pe_static)}</strong></div>
            <div><span>市净率</span><strong>{formatSnapshotValue(overview.quote.pb)}</strong></div>
          </div>
        </section>
      )}

      {overview.announcements.length > 0 && (
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>Announcements</h2>
              <p>Fetched on confirmed symbol refresh; titles link to the source page when available.</p>
            </div>
          </div>
          <DataTable
            rows={overview.announcements}
            columns={[
              { key: "symbol", label: "SYMBOL" },
              { key: "title", label: "TITLE" },
              { key: "published_at", label: "PUBLISHED AT" },
              { key: "source", label: "SOURCE" },
              { key: "fetched_at", label: "FETCHED AT" }
            ]}
            renderCell={renderLinkedTitle}
          />
        </section>
      )}

      {overview.reports.length > 0 && (
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>Research Reports</h2>
              <p>Fetched on confirmed symbol refresh; titles link to the source page when available.</p>
            </div>
          </div>
          <DataTable
            rows={overview.reports}
            columns={[
              { key: "symbol", label: "SYMBOL" },
              { key: "title", label: "TITLE" },
              { key: "institution", label: "INSTITUTION" },
              { key: "analyst", label: "ANALYST" },
              { key: "rating", label: "RATING" },
              { key: "report_date", label: "REPORT DATE" },
              { key: "source", label: "SOURCE" }
            ]}
            renderCell={renderLinkedTitle}
          />
        </section>
      )}
    </div>
  );
}
