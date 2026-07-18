import { BarChart3, FileText, ListChecks, RadioTower, RefreshCw } from "lucide-react";
import type { ChartPeriod } from "../api";
import type { BoardMappingResponse, ChartResponse, MarketModuleSection, MarketQuote, ModuleDataResponse, ModuleDefinition, Security } from "../types";
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

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "NA";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toLocaleString() : "NA";
  }
  return String(value);
}

function sectionValue(section: MarketModuleSection | undefined, key: string): unknown {
  return section ? section[key] : null;
}

function formatPercent(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "NA";
  }
  return `${value.toLocaleString()}%`;
}

function formatYi(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "NA";
  }
  return `${value.toLocaleString()}亿`;
}

function formatSourceTime(source?: string | null, fetchedAt?: string | null): string {
  return [source, fetchedAt].filter(Boolean).join(" · ") || "NA";
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

    const marketPayload = data?.market;
    const quoteSnapshot = marketPayload?.quote_snapshot ?? quote;
    const valuation = marketPayload?.valuation;
    const limits = marketPayload?.limits;
    const liquidity = marketPayload?.liquidity;

    const quoteItems = quoteSnapshot
      ? [
          { label: "Last price", value: quoteSnapshot.last_price },
          { label: "Open", value: quoteSnapshot.open },
          { label: "High", value: quoteSnapshot.high },
          { label: "Low", value: quoteSnapshot.low },
          { label: "Previous close", value: quoteSnapshot.previous_close },
          { label: "Price time", value: quoteSnapshot.price_time },
          { label: "Source", value: quoteSnapshot.source },
          { label: "Fetched at", value: quoteSnapshot.fetched_at }
        ]
      : [];

    const valuationItems = [
      { label: "PE TTM", value: sectionValue(valuation, "pe_ttm") },
      { label: "PE static", value: sectionValue(valuation, "pe_static") },
      { label: "PB", value: sectionValue(valuation, "pb") },
      { label: "Total market cap", value: formatYi(sectionValue(valuation, "total_market_cap")) },
      { label: "Float market cap", value: formatYi(sectionValue(valuation, "float_market_cap")) },
      { label: "Source", value: formatSourceTime(valuation?.source, valuation?.fetched_at) }
    ];
    const limitItems = [
      { label: "Limit up", value: sectionValue(limits, "limit_up") },
      { label: "Limit down", value: sectionValue(limits, "limit_down") },
      { label: "Change amount", value: sectionValue(limits, "change_amt") },
      { label: "Change %", value: formatPercent(sectionValue(limits, "change_pct")) },
      { label: "Amplitude %", value: formatPercent(sectionValue(limits, "amplitude_pct")) },
      { label: "Source", value: formatSourceTime(limits?.source, limits?.fetched_at) }
    ];
    const liquidityItems = [
      { label: "Turnover %", value: formatPercent(sectionValue(liquidity, "turnover_pct")) },
      { label: "Volume ratio", value: sectionValue(liquidity, "volume_ratio") },
      { label: "Volume", value: sectionValue(liquidity, "volume") },
      { label: "Amount", value: sectionValue(liquidity, "amount") },
      { label: "Bid1 / Ask1", value: `${displayValue(sectionValue(liquidity, "bid1"))} / ${displayValue(sectionValue(liquidity, "ask1"))}` },
      { label: "Source", value: formatSourceTime(liquidity?.source, liquidity?.fetched_at) }
    ];

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

        {loading && <div className="panel loading-panel">Loading market module data...</div>}
        {error && <EmptyState title="Market module request failed" detail={error} />}

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
                  <strong>{displayValue(item.value)}</strong>
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="panel market-snapshot-panel">
          <div className="section-heading">
            <div>
              <h2>Valuation</h2>
            </div>
          </div>
          <div className="snapshot-grid module-quote-grid">
            {valuationItems.map((item) => (
              <div key={item.label}>
                <span>{item.label}</span>
                <strong>{displayValue(item.value)}</strong>
              </div>
            ))}
          </div>
        </section>

        <section className="panel market-snapshot-panel">
          <div className="section-heading">
            <div>
              <h2>Price Limits</h2>
            </div>
          </div>
          <div className="snapshot-grid module-quote-grid">
            {limitItems.map((item) => (
              <div key={item.label}>
                <span>{item.label}</span>
                <strong>{displayValue(item.value)}</strong>
              </div>
            ))}
          </div>
        </section>

        <section className="panel market-snapshot-panel">
          <div className="section-heading">
            <div>
              <h2>Liquidity</h2>
            </div>
          </div>
          <div className="snapshot-grid module-quote-grid">
            {liquidityItems.map((item) => (
              <div key={item.label}>
                <span>{item.label}</span>
                <strong>{displayValue(item.value)}</strong>
              </div>
            ))}
          </div>
        </section>

        <section className="panel module-market-strip">
          <div className="section-heading">
            <div>
              <h2>Order Book</h2>
            </div>
            <BarChart3 aria-hidden="true" size={20} />
          </div>
          <div className="market-capability-card">
            <StatusBadge status={marketPayload?.order_book.status ?? "not_collected"} />
            <strong>{marketPayload?.order_book.source ?? "mootdx"}</strong>
            <p>{marketPayload?.order_book.note ?? "No five-level order book data is available."}</p>
          </div>
        </section>

        <section className="panel module-market-strip">
          <div className="section-heading">
            <div>
              <h2>Index / ETF Entrance</h2>
            </div>
            <StatusBadge status={marketPayload?.index_etf.status ?? "not_configured"} />
          </div>
          <div className="market-placeholders">
            {(marketPayload?.index_etf.entries ?? []).map((entry) => (
              <span key={entry.symbol}>{entry.label}: {entry.symbol}</span>
            ))}
            {marketPayload?.index_etf.note && <span>{marketPayload.index_etf.note}</span>}
          </div>
        </section>

        <section className="panel module-market-strip">
          <div className="section-heading">
            <div>
              <h2>Source Status</h2>
            </div>
            <RadioTower aria-hidden="true" size={20} />
          </div>
          <div className="market-source-grid">
            {(marketPayload?.source_status ?? []).map((source) => (
              <div key={source.source} className="market-source-card">
                <div>
                  <strong>{source.source}</strong>
                  <StatusBadge status={source.status} />
                </div>
                <span>success: {displayValue(source.last_success_at)}</span>
                <span>failure: {displayValue(source.last_failure_at)}</span>
                {source.last_error && <p>{source.last_error}</p>}
              </div>
            ))}
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
