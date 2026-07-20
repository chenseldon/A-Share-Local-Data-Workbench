import type { ChartPeriod } from "../api";
import { RefreshCw } from "lucide-react";
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
  onPrintSecurity: () => void;
  onOpenAiAnalyst: () => void;
  marketRefreshing: boolean;
  searchQuery: string;
  searchResults: Security[];
  isSearching: boolean;
  onSearchQueryChange: (value: string) => void;
  onSelectSymbol: (symbol: string) => void;
  onOpenModuleSnapshot: (moduleId: string, anchorId?: string | null) => void;
  apiHealthError: string | null;
}

function formatSnapshotValue(value: number | string | null | undefined, suffix = "", maximumFractionDigits = 2): string {
  if (value === null || value === undefined || value === "") {
    return "NA";
  }
  if (typeof value === "number") {
    return `${Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits })}${suffix}`;
  }
  return `${value}${suffix}`;
}

function formatSnapshotPercent(value: number | null | undefined): string {
  return formatSnapshotValue(value, "%", 2);
}

function formatSnapshotWan(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "NA";
  }
  return `${(value / 10_000).toLocaleString(undefined, { maximumFractionDigits: 2 })}万`;
}

function formatSnapshotYi(value: number | null | undefined, inputUnit: "yuan" | "wan" | "yi" = "yi"): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "NA";
  }
  const divisor = inputUnit === "yuan" ? 100_000_000 : inputUnit === "wan" ? 10_000 : 1;
  return `${(value / divisor).toLocaleString(undefined, { maximumFractionDigits: 2 })}亿`;
}

function normalizedExternalUrl(url: string): string {
  if (url.includes("cninfo.com.cn") && url.includes("annoId=")) {
    return url.replace("annoId=", "announcementId=");
  }
  return url;
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
  const url = typeof row.url === "string" && row.url ? normalizedExternalUrl(row.url) : null;
  if (!url) {
    return title;
  }
  return (
    <a className="table-title-link" href={url} target="_blank" rel="noreferrer">
      {title}
    </a>
  );
}

function renderSnapshotTitle(
  label: string,
  moduleId: string | null | undefined,
  anchorId: string | null | undefined,
  onOpenModuleSnapshot: (moduleId: string, anchorId?: string | null) => void,
  className: string
) {
  if (!moduleId) {
    return label;
  }
  return (
    <button className={className} type="button" onClick={() => onOpenModuleSnapshot(moduleId, anchorId)}>
      {label}
    </button>
  );
}

function renderModuleSnapshot(
  snapshot: NonNullable<SecurityOverviewType["module_snapshots"]>[number],
  onOpenModuleSnapshot: (moduleId: string, anchorId?: string | null) => void
) {
  const moduleId = snapshot.target_module ?? snapshot.module;
  return (
    <section key={snapshot.module} className="panel security-module-snapshot-panel">
      <div className="section-heading">
        <div>
          <h2>{renderSnapshotTitle(snapshot.title, moduleId, snapshot.target_anchor, onOpenModuleSnapshot, "snapshot-heading-link")}</h2>
        </div>
      </div>
      <div className="security-snapshot-tables">
        {snapshot.tables.map((table) => (
          <div key={table.id} className="security-snapshot-table">
            <h3>{renderSnapshotTitle(table.title, moduleId, table.target_anchor, onOpenModuleSnapshot, "snapshot-subheading-link")}</h3>
            <DataTable rows={table.rows} columns={table.columns} renderCell={renderLinkedTitle} />
          </div>
        ))}
      </div>
    </section>
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
  onPrintSecurity,
  onOpenAiAnalyst,
  marketRefreshing,
  searchQuery,
  searchResults,
  isSearching,
  onSearchQueryChange,
  onSelectSymbol,
  onOpenModuleSnapshot,
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
        action={
          <button className="secondary-button" type="button" onClick={onRefreshMarket} disabled={marketRefreshing}>
            <RefreshCw aria-hidden="true" size={15} />
            {marketRefreshing ? "Refreshing" : "Refresh and reload"}
          </button>
        }
      />
    );
  }

  if (!overview) {
    return <EmptyState title="No symbol selected" detail="Search a local security to inspect cross-module context." />;
  }

  const snapshotItems = overview.quote
    ? [
        { label: "今开", value: formatSnapshotValue(overview.quote.open) },
        { label: "最高", value: formatSnapshotValue(overview.quote.high) },
        { label: "涨停", value: formatSnapshotValue(overview.quote.limit_up) },
        { label: "换手", value: formatSnapshotPercent(overview.quote.turnover_pct) },
        { label: "成交量", value: formatSnapshotWan(overview.quote.volume) },
        { label: "市盈", value: formatSnapshotValue(overview.quote.pe_ttm ?? overview.quote.pe_static) },
        { label: "总市值", value: formatSnapshotYi(overview.quote.total_market_cap) },
        { label: "昨收", value: formatSnapshotValue(overview.quote.previous_close) },
        { label: "最低", value: formatSnapshotValue(overview.quote.low) },
        { label: "跌停", value: formatSnapshotValue(overview.quote.limit_down) },
        { label: "量比", value: formatSnapshotValue(overview.quote.volume_ratio) },
        { label: "成交额", value: formatSnapshotYi(overview.quote.amount, "wan") },
        { label: "市净", value: formatSnapshotValue(overview.quote.pb) },
        { label: "流通市值", value: formatSnapshotYi(overview.quote.float_market_cap) }
      ]
    : [];
  const moduleSnapshots = overview.module_snapshots ?? [];

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
        onPrintSecurity={onPrintSecurity}
        onOpenAiAnalyst={onOpenAiAnalyst}
        refreshing={marketRefreshing}
        searchQuery={searchQuery}
        searchResults={searchResults}
        isSearching={isSearching}
        onSearchQueryChange={onSearchQueryChange}
        onSelectSymbol={onSelectSymbol}
        mode="security"
      />

      {overview.quote && (
        <section className="panel market-snapshot-panel">
          <div className="section-heading">
            <div>
              <h2>Market Snapshot</h2>
            </div>
          </div>
          <div className="snapshot-grid">
            {snapshotItems.map((item) => (
              <div key={item.label}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>
        </section>
      )}

      {moduleSnapshots.map((snapshot) => renderModuleSnapshot(snapshot, onOpenModuleSnapshot))}
    </div>
  );
}
