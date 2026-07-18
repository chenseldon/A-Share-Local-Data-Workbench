import { BarChart3, FileText, ListChecks, RadioTower, RefreshCw } from "lucide-react";
import type { ChartPeriod } from "../api";
import type { BoardMappingResponse, ChartResponse, MarketQuote, ModuleDataResponse, ModuleDefinition, Security } from "../types";
import { DataTable } from "./DataTable";
import { EmptyState } from "./EmptyState";
import { KLineChart } from "./KLineChart";
import { StatusBadge } from "./StatusBadge";

interface ModuleViewProps {
  module: ModuleDefinition | undefined;
  data: ModuleDataResponse | null;
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
  security: Security | null;
  quote: MarketQuote | null;
  onRefreshMarket: () => void;
  onRefreshModule: () => void;
  marketRefreshing: boolean;
  moduleRefreshing: boolean;
  searchQuery: string;
  searchResults: Security[];
  isSearching: boolean;
  onSearchQueryChange: (value: string) => void;
  onSelectSymbol: (symbol: string) => void;
}

function moduleEmptyLabel(module: ModuleDefinition, status: string): string {
  if (status === "not_configured") {
    return `${module.layer} is mapped in the V3.4.0 architecture, but no connector is enabled yet.`;
  }
  return `No cached rows for ${module.layer} yet. Trigger collection or switch to a seeded symbol.`;
}

export function ModuleView({
  module,
  data,
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
  security,
  quote,
  onRefreshMarket,
  onRefreshModule,
  marketRefreshing,
  moduleRefreshing,
  searchQuery,
  searchResults,
  isSearching,
  onSearchQueryChange,
  onSelectSymbol
}: ModuleViewProps) {
  if (!module) {
    return <EmptyState title="Unknown module" detail="Select one of the ten configured navigation modules." />;
  }

  if (module.id === "market") {
    if (!selectedSymbol) {
      return (
        <div className="security-start-screen module-market-start">
          <section className="security-start-card">
            <div>
              <span className="start-eyebrow">Market Layer</span>
              <h1>Search a symbol to inspect market data</h1>
              <p>Market module reads local free-stockdb K-line data, quote fields and source status after a symbol is selected.</p>
            </div>
            <div className="start-search-box">
              <input
                aria-label="Search or resolve A-share symbol"
                value={searchQuery}
                placeholder="Search symbol or Chinese name"
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
          </section>
        </div>
      );
    }

    const quoteItems = quote
      ? [
          { label: "Last price", value: quote.last_price },
          { label: "Open", value: quote.open },
          { label: "High", value: quote.high },
          { label: "Low", value: quote.low },
          { label: "Volume", value: quote.volume?.toLocaleString() ?? "NA" },
          { label: "Amount", value: quote.amount?.toLocaleString() ?? "NA" },
          { label: "PE TTM", value: quote.pe_ttm ?? quote.pe_static ?? "NA" },
          { label: "PB", value: quote.pb ?? "NA" },
          { label: "Source", value: quote.source },
          { label: "Fetched at", value: quote.fetched_at }
        ]
      : [];

    return (
      <div className="content-grid security-workspace-grid module-market-grid">
        <KLineChart
          rows={chart?.rows ?? []}
          quote={quote}
          security={security}
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
          mode="market"
        />

        {quoteItems.length > 0 && (
          <section className="panel market-snapshot-panel">
            <div className="section-heading">
              <div>
                <h2>Market Quote Snapshot</h2>
              </div>
            </div>
            <div className="snapshot-grid module-quote-grid">
              {quoteItems.map((item) => (
                <div key={item.label}>
                  <span>{item.label}</span>
                  <strong>{item.value === null || item.value === undefined || item.value === "" ? "NA" : item.value}</strong>
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="panel module-market-strip">
          <div className="section-heading">
            <div>
              <h2>Market Layer Coverage</h2>
              <p>Unavailable upstream areas are shown explicitly instead of rendered as data.</p>
            </div>
            <BarChart3 aria-hidden="true" size={20} />
          </div>
          <div className="market-placeholders">
            <span>K-line: free-stockdb</span>
            <span>Quote: public snapshot cache</span>
            <span>Five-level order book: Not configured</span>
            <span>Index/ETF entrance: Not configured</span>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="content-grid">
      <section className="panel hero-panel">
        <div>
          <h1>{module.label}</h1>
          <p>{module.layer} · {module.description}</p>
        </div>
        <div className="security-meta">
          <span>{selectedSymbol || "All local symbols"}</span>
          <StatusBadge status={module.status} />
          <button className="secondary-button" onClick={onRefreshModule} disabled={moduleRefreshing}>
            <RefreshCw aria-hidden="true" size={14} />
            {moduleRefreshing ? "Refreshing" : "Refresh module"}
          </button>
        </div>
      </section>

      <section className="module-detail-grid">
        <div className="panel module-info-card">
          <RadioTower aria-hidden="true" size={18} />
          <h2>Sources</h2>
          <div className="tag-list">
            {module.sources.map((source) => (
              <span key={source}>{source}</span>
            ))}
          </div>
        </div>
        <div className="panel module-info-card">
          <ListChecks aria-hidden="true" size={18} />
          <h2>Planned Fields</h2>
          <div className="tag-list">
            {module.planned_fields.map((field) => (
              <span key={field}>{field}</span>
            ))}
          </div>
        </div>
        <div className="panel module-info-card">
          <FileText aria-hidden="true" size={18} />
          <h2>Local Tables</h2>
          <div className="tag-list">
            {(module.tables.length ? module.tables : ["No local table yet"]).map((table) => (
              <span key={table}>{table}</span>
            ))}
          </div>
        </div>
        <div className="panel module-info-card">
          <RadioTower aria-hidden="true" size={18} />
          <h2>Capabilities</h2>
          <div className="tag-list">
            {Object.entries(module.capabilities ?? {}).length ? (
              Object.entries(module.capabilities ?? {}).map(([status, count]) => (
                <span key={status}>{status.replaceAll("_", " ")}: {count}</span>
              ))
            ) : (
              <span>No registry status</span>
            )}
          </div>
        </div>
      </section>

      {loading && <div className="panel loading-panel">Loading local module rows...</div>}
      {error && <EmptyState title="Module request failed" detail={error} />}
      {!loading && !error && data && (
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>Local Rows</h2>
              <p>Status: {data.status.replaceAll("_", " ")}. Rows are read from DuckDB through the local API.</p>
            </div>
            <StatusBadge status={data.status} />
          </div>
          <DataTable rows={data.rows} emptyLabel={moduleEmptyLabel(module, data.status)} />
        </section>
      )}
    </div>
  );
}
