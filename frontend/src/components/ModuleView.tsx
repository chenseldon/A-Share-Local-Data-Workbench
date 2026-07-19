import { BarChart3, FileText, ListChecks, RadioTower, RefreshCw } from "lucide-react";
import type { ChartPeriod } from "../api";
import type {
  BoardMappingResponse,
  ChartResponse,
  DataRow,
  MarketModuleSection,
  MarketQuote,
  ModuleDataResponse,
  ModuleDefinition,
  ReportModuleTableColumn,
  Security
} from "../types";
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

function formatPanelTime(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "NA";
  }
  const raw = String(value);
  return raw.includes("T") ? raw.replace("T", " ").slice(0, 19) : raw.slice(0, 19);
}

function sourceStatusDetail(source: { status: string; last_success_at?: string | null; last_failure_at?: string | null }): string | null {
  const status = source.status.toLowerCase();
  if (["fresh", "ok", "success", "configured"].includes(status)) {
    return source.last_success_at ? `success: ${formatPanelTime(source.last_success_at)}` : null;
  }
  if (status === "failed") {
    return source.last_failure_at ? `failure: ${formatPanelTime(source.last_failure_at)}` : null;
  }
  return null;
}

function renderReportCell(value: unknown, column: ReportModuleTableColumn, row: DataRow) {
  if (column.key === "title" && typeof row.url === "string" && row.url) {
    return (
      <a className="table-title-link" href={row.url} target="_blank" rel="noreferrer">
        {displayValue(value)}
      </a>
    );
  }
  if (column.key === "fetched_at") {
    return formatPanelTime(value);
  }
  return displayValue(value);
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
          { label: "Previous close", value: quoteSnapshot.previous_close }
        ]
      : [];

    const valuationItems = [
      { label: "PE TTM", value: sectionValue(valuation, "pe_ttm") },
      { label: "PE static", value: sectionValue(valuation, "pe_static") },
      { label: "PB", value: sectionValue(valuation, "pb") },
      { label: "Total market cap", value: formatYi(sectionValue(valuation, "total_market_cap")) },
      { label: "Float market cap", value: formatYi(sectionValue(valuation, "float_market_cap")) }
    ];
    const limitItems = [
      { label: "Limit up", value: sectionValue(limits, "limit_up") },
      { label: "Limit down", value: sectionValue(limits, "limit_down") },
      { label: "Change amount", value: sectionValue(limits, "change_amt") },
      { label: "Change %", value: formatPercent(sectionValue(limits, "change_pct")) },
      { label: "Amplitude %", value: formatPercent(sectionValue(limits, "amplitude_pct")) }
    ];
    const liquidityItems = [
      { label: "Turnover %", value: formatPercent(sectionValue(liquidity, "turnover_pct")) },
      { label: "Volume ratio", value: sectionValue(liquidity, "volume_ratio") },
      { label: "Volume", value: sectionValue(liquidity, "volume") },
      { label: "Amount", value: sectionValue(liquidity, "amount") },
      { label: "Bid1 / Ask1", value: `${displayValue(sectionValue(liquidity, "bid1"))} / ${displayValue(sectionValue(liquidity, "ask1"))}` }
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
              <span className="market-section-meta">
                Source: {displayValue(quoteSnapshot?.source)} <span>Time: {formatPanelTime(quoteSnapshot?.fetched_at)}</span>
              </span>
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
            <span className="market-section-meta">
              Source: {displayValue(valuation?.source)} <span>Time: {formatPanelTime(valuation?.fetched_at)}</span>
            </span>
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
            <span className="market-section-meta">
              Source: {displayValue(limits?.source)} <span>Time: {formatPanelTime(limits?.fetched_at)}</span>
            </span>
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
            <span className="market-section-meta">
              Source: {displayValue(liquidity?.source)} <span>Time: {formatPanelTime(liquidity?.fetched_at)}</span>
            </span>
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
              <button key={entry.symbol} type="button" onClick={() => onSelectSymbol(entry.symbol)}>
                {entry.label}: {entry.symbol}
              </button>
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
                {sourceStatusDetail(source) && <span>{sourceStatusDetail(source)}</span>}
                {source.last_error && <p>{source.last_error}</p>}
              </div>
            ))}
          </div>
        </section>
      </div>
    );
  }

  if (module.id === "announcements") {
    if (!selectedSymbol) {
      return (
        <div className="security-start-screen module-market-start">
          <section className="security-start-card">
            <div>
              <span className="start-eyebrow">Announcements Layer</span>
              <h1>Search a symbol to inspect announcements</h1>
              <p>Announcements uses CNINFO full-text disclosure search as the primary source, with mootdx F10 and official backup routes shown as explicit capabilities.</p>
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

    const announcementsPayload = data?.announcements;
    const announcementSections = announcementsPayload?.sections ?? [];
    const announcementTables = announcementsPayload?.tables ?? [];
    const visibleAnnouncementTables = announcementTables.filter((table) => table.rows.length > 0);

    return (
      <div className="content-grid module-reports-grid module-announcements-grid">
        <section className="panel hero-panel module-dark-hero">
          <div>
            <h1>{module.label}</h1>
            <p>{module.layer} · CNINFO full-text announcements, disclosure detail links, mootdx F10 summary status and official backup-source boundaries.</p>
          </div>
          <div className="security-meta">
            <span>{selectedSymbol}</span>
            <StatusBadge status={data?.status ?? module.status} />
            <button className="secondary-button" onClick={onRefreshModule} disabled={moduleRefreshing}>
              <RefreshCw aria-hidden="true" size={14} />
              {moduleRefreshing ? "Refreshing" : "Refresh module"}
            </button>
          </div>
        </section>

        {loading && <div className="panel loading-panel">Loading announcements module data...</div>}
        {error && <EmptyState title="Announcements request failed" detail={error} />}

        {!loading && !error && (
          <>
            {announcementSections.map((section) => (
              <section key={section.id} className="panel market-snapshot-panel module-report-section">
                <div className="section-heading">
                  <div>
                    <h2>{section.title}</h2>
                  </div>
                  <span className="market-section-meta">
                    Source: {displayValue(section.source)} <span>Time: {formatPanelTime(section.fetched_at)}</span>
                  </span>
                </div>
                <div className="snapshot-grid module-dynamic-grid">
                  {section.cards.map((card) => (
                    <div key={`${section.id}-${card.label}`}>
                      <span>{card.label}</span>
                      <strong>{displayValue(card.value)}</strong>
                      {card.status && <StatusBadge status={card.status} />}
                    </div>
                  ))}
                </div>
              </section>
            ))}

            {visibleAnnouncementTables.map((table) => (
              <section key={table.id} className="panel module-market-strip">
                <div className="section-heading">
                  <div>
                    <h2>{table.title}</h2>
                  </div>
                  <StatusBadge status="fresh" />
                </div>
                <DataTable rows={table.rows} columns={table.columns} renderCell={renderReportCell} />
              </section>
            ))}

            <section className="panel module-market-strip">
              <div className="section-heading">
                <div>
                  <h2>Source Status</h2>
                </div>
                <RadioTower aria-hidden="true" size={20} />
              </div>
              <div className="market-source-grid">
                {(announcementsPayload?.source_status ?? []).map((source) => (
                  <div key={source.source} className="market-source-card">
                    <div>
                      <strong>{source.source}</strong>
                      <StatusBadge status={source.status} />
                    </div>
                    {sourceStatusDetail(source) && <span>{sourceStatusDetail(source)}</span>}
                    {source.last_error && <p>{source.last_error}</p>}
                  </div>
                ))}
              </div>
            </section>

            {announcementSections.length === 0 && visibleAnnouncementTables.length === 0 && (
              <EmptyState title="No announcements payload" detail="The announcements connector returned no structured sections or table rows for this symbol." />
            )}
          </>
        )}
      </div>
    );
  }

  if (module.id === "news") {
    if (!selectedSymbol) {
      return (
        <div className="security-start-screen module-market-start">
          <section className="security-start-card">
            <div>
              <span className="start-eyebrow">News Layer</span>
              <h1>Search a symbol to inspect news context</h1>
              <p>News uses Eastmoney stock news, CLS telegrams and Eastmoney 7x24 global news with explicit source status.</p>
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

    const newsPayload = data?.news;
    const newsSections = newsPayload?.sections ?? [];
    const newsTables = newsPayload?.tables ?? [];
    const visibleNewsTables = newsTables.filter((table) => table.rows.length > 0);

    return (
      <div className="content-grid module-reports-grid module-news-grid">
        <section className="panel hero-panel module-dark-hero">
          <div>
            <h1>{module.label}</h1>
            <p>{module.layer} · Eastmoney stock news, CLS telegrams and Eastmoney global 7x24 news with mutual backup status.</p>
          </div>
          <div className="security-meta">
            <span>{selectedSymbol}</span>
            <StatusBadge status={data?.status ?? module.status} />
            <button className="secondary-button" onClick={onRefreshModule} disabled={moduleRefreshing}>
              <RefreshCw aria-hidden="true" size={14} />
              {moduleRefreshing ? "Refreshing" : "Refresh module"}
            </button>
          </div>
        </section>

        {loading && <div className="panel loading-panel">Loading news module data...</div>}
        {error && <EmptyState title="News request failed" detail={error} />}

        {!loading && !error && (
          <>
            {newsSections.map((section) => (
              <section key={section.id} className="panel market-snapshot-panel module-report-section">
                <div className="section-heading">
                  <div>
                    <h2>{section.title}</h2>
                  </div>
                  <span className="market-section-meta">
                    Source: {displayValue(section.source)} <span>Time: {formatPanelTime(section.fetched_at)}</span>
                  </span>
                </div>
                <div className="snapshot-grid module-dynamic-grid">
                  {section.cards.map((card) => (
                    <div key={`${section.id}-${card.label}`}>
                      <span>{card.label}</span>
                      <strong>{displayValue(card.value)}</strong>
                      {card.status && <StatusBadge status={card.status} />}
                    </div>
                  ))}
                </div>
              </section>
            ))}

            {visibleNewsTables.map((table) => (
              <section key={table.id} className="panel module-market-strip">
                <div className="section-heading">
                  <div>
                    <h2>{table.title}</h2>
                  </div>
                  <StatusBadge status="fresh" />
                </div>
                <DataTable rows={table.rows} columns={table.columns} renderCell={renderReportCell} />
              </section>
            ))}

            <section className="panel module-market-strip">
              <div className="section-heading">
                <div>
                  <h2>Source Status</h2>
                </div>
                <RadioTower aria-hidden="true" size={20} />
              </div>
              <div className="market-source-grid">
                {(newsPayload?.source_status ?? []).map((source) => (
                  <div key={source.source} className="market-source-card">
                    <div>
                      <strong>{source.source}</strong>
                      <StatusBadge status={source.status} />
                    </div>
                    {sourceStatusDetail(source) && <span>{sourceStatusDetail(source)}</span>}
                    {source.last_error && <p>{source.last_error}</p>}
                  </div>
                ))}
              </div>
            </section>

            {newsSections.length === 0 && visibleNewsTables.length === 0 && (
              <EmptyState title="No news payload" detail="The news connectors returned no structured sections or table rows for this symbol." />
            )}
          </>
        )}
      </div>
    );
  }

  if (module.id === "reports") {
    if (!selectedSymbol) {
      return (
        <div className="security-start-screen module-market-start">
          <section className="security-start-card">
            <div>
              <span className="start-eyebrow">Research Reports Layer</span>
              <h1>Search a symbol to inspect research reports</h1>
              <p>Research Reports uses Eastmoney reportapi as the main source, with optional 10jqka EPS and iwencai capabilities shown explicitly.</p>
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

    const reportsPayload = data?.reports;
    const reportSections = reportsPayload?.sections ?? [];
    const reportTables = reportsPayload?.tables ?? [];
    const visibleTables = reportTables.filter((table) => table.rows.length > 0);

    return (
      <div className="content-grid module-reports-grid">
        <section className="panel hero-panel module-dark-hero">
          <div>
            <h1>{module.label}</h1>
            <p>{module.layer} · Eastmoney reportapi company and industry reports, PDF URL metadata, optional consensus EPS and iwencai status.</p>
          </div>
          <div className="security-meta">
            <span>{selectedSymbol}</span>
            <StatusBadge status={data?.status ?? module.status} />
            <button className="secondary-button" onClick={onRefreshModule} disabled={moduleRefreshing}>
              <RefreshCw aria-hidden="true" size={14} />
              {moduleRefreshing ? "Refreshing" : "Refresh module"}
            </button>
          </div>
        </section>

        {loading && <div className="panel loading-panel">Loading research reports module data...</div>}
        {error && <EmptyState title="Research reports request failed" detail={error} />}

        {!loading && !error && (
          <>
            {reportSections.map((section) => (
              <section key={section.id} className="panel market-snapshot-panel module-report-section">
                <div className="section-heading">
                  <div>
                    <h2>{section.title}</h2>
                  </div>
                  <span className="market-section-meta">
                    Source: {displayValue(section.source)} <span>Time: {formatPanelTime(section.fetched_at)}</span>
                  </span>
                </div>
                <div className="snapshot-grid module-dynamic-grid">
                  {section.cards.map((card) => (
                    <div key={`${section.id}-${card.label}`}>
                      <span>{card.label}</span>
                      <strong>{displayValue(card.value)}</strong>
                      {card.status && <StatusBadge status={card.status} />}
                    </div>
                  ))}
                </div>
              </section>
            ))}

            {visibleTables.map((table) => (
              <section key={table.id} className="panel module-market-strip">
                <div className="section-heading">
                  <div>
                    <h2>{table.title}</h2>
                  </div>
                  <StatusBadge status="fresh" />
                </div>
                <DataTable rows={table.rows} columns={table.columns} renderCell={renderReportCell} />
              </section>
            ))}

            <section className="panel module-market-strip">
              <div className="section-heading">
                <div>
                  <h2>Source Status</h2>
                </div>
                <RadioTower aria-hidden="true" size={20} />
              </div>
              <div className="market-source-grid">
                {(reportsPayload?.source_status ?? []).map((source) => (
                  <div key={source.source} className="market-source-card">
                    <div>
                      <strong>{source.source}</strong>
                      <StatusBadge status={source.status} />
                    </div>
                    {sourceStatusDetail(source) && <span>{sourceStatusDetail(source)}</span>}
                    {source.last_error && <p>{source.last_error}</p>}
                  </div>
                ))}
              </div>
            </section>

            {reportSections.length === 0 && visibleTables.length === 0 && (
              <EmptyState title="No research report payload" detail="The reports connector returned no structured sections or table rows for this symbol." />
            )}
          </>
        )}
      </div>
    );
  }

  if (module.id === "signals") {
    if (!selectedSymbol) {
      return (
        <div className="security-start-screen module-market-start">
          <section className="security-start-card">
            <div>
              <span className="start-eyebrow">Signals Layer</span>
              <h1>Search a symbol to inspect signal data</h1>
              <p>Signals uses Eastmoney concept ownership, intraday fund flow, dragon-tiger records and industry ranking where the source is available.</p>
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

    const signalsPayload = data?.signals;
    const signalSections = signalsPayload?.sections ?? [];
    const signalTables = signalsPayload?.tables ?? [];
    const visibleSignalTables = signalTables.filter((table) => table.rows.length > 0);

    return (
      <div className="content-grid module-reports-grid module-signals-grid">
        <section className="panel hero-panel module-dark-hero">
          <div>
            <h1>{module.label}</h1>
            <p>{module.layer} · Eastmoney block ownership, intraday fund flow, dragon-tiger records, industry rotation and explicit source boundaries.</p>
          </div>
          <div className="security-meta">
            <span>{selectedSymbol}</span>
            <StatusBadge status={data?.status ?? module.status} />
            <button className="secondary-button" onClick={onRefreshModule} disabled={moduleRefreshing}>
              <RefreshCw aria-hidden="true" size={14} />
              {moduleRefreshing ? "Refreshing" : "Refresh module"}
            </button>
          </div>
        </section>

        {loading && <div className="panel loading-panel">Loading signals module data...</div>}
        {error && <EmptyState title="Signals request failed" detail={error} />}

        {!loading && !error && (
          <>
            {signalSections.map((section) => (
              <section key={section.id} className="panel market-snapshot-panel module-report-section">
                <div className="section-heading">
                  <div>
                    <h2>{section.title}</h2>
                  </div>
                  <span className="market-section-meta">
                    Source: {displayValue(section.source)} <span>Time: {formatPanelTime(section.fetched_at)}</span>
                  </span>
                </div>
                <div className="snapshot-grid module-dynamic-grid">
                  {section.cards.map((card) => (
                    <div key={`${section.id}-${card.label}`}>
                      <span>{card.label}</span>
                      <strong>{displayValue(card.value)}</strong>
                      {card.status && <StatusBadge status={card.status} />}
                    </div>
                  ))}
                </div>
              </section>
            ))}

            {visibleSignalTables.map((table) => (
              <section key={table.id} className="panel module-market-strip">
                <div className="section-heading">
                  <div>
                    <h2>{table.title}</h2>
                  </div>
                  <StatusBadge status="fresh" />
                </div>
                <DataTable rows={table.rows} columns={table.columns} renderCell={renderReportCell} />
              </section>
            ))}

            <section className="panel module-market-strip">
              <div className="section-heading">
                <div>
                  <h2>Source Status</h2>
                </div>
                <RadioTower aria-hidden="true" size={20} />
              </div>
              <div className="market-source-grid">
                {(signalsPayload?.source_status ?? []).map((source) => (
                  <div key={source.source} className="market-source-card">
                    <div>
                      <strong>{source.source}</strong>
                      <StatusBadge status={source.status} />
                    </div>
                    {sourceStatusDetail(source) && <span>{sourceStatusDetail(source)}</span>}
                    {source.last_error && <p>{source.last_error}</p>}
                  </div>
                ))}
              </div>
            </section>

            {signalSections.length === 0 && visibleSignalTables.length === 0 && (
              <EmptyState title="No signals payload" detail="The signals connector returned no structured sections or table rows for this symbol." />
            )}
          </>
        )}
      </div>
    );
  }

  if (module.id === "chip_liquidity") {
    if (!selectedSymbol) {
      return (
        <div className="security-start-screen module-market-start">
          <section className="security-start-card">
            <div>
              <span className="start-eyebrow">Chip And Liquidity Layer</span>
              <h1>Search a symbol to inspect chip and liquidity data</h1>
              <p>Chip/Liquidity uses Eastmoney margin financing, block trades, holder count, dividends and 120-day daily fund flow where sources are available.</p>
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

    const chipPayload = data?.chip_liquidity;
    const chipSections = chipPayload?.sections ?? [];
    const chipTables = chipPayload?.tables ?? [];
    const visibleChipTables = chipTables.filter((table) => table.rows.length > 0);

    return (
      <div className="content-grid module-reports-grid module-chip-grid">
        <section className="panel hero-panel module-dark-hero">
          <div>
            <h1>{module.label}</h1>
            <p>{module.layer} · Eastmoney datacenter margin, block trade, shareholder, dividend and 120-day fund-flow sources with explicit cache status.</p>
          </div>
          <div className="security-meta">
            <span>{selectedSymbol}</span>
            <StatusBadge status={data?.status ?? module.status} />
            <button className="secondary-button" onClick={onRefreshModule} disabled={moduleRefreshing}>
              <RefreshCw aria-hidden="true" size={14} />
              {moduleRefreshing ? "Refreshing" : "Refresh module"}
            </button>
          </div>
        </section>

        {loading && <div className="panel loading-panel">Loading chip and liquidity module data...</div>}
        {error && <EmptyState title="Chip and liquidity request failed" detail={error} />}

        {!loading && !error && (
          <>
            {chipSections.map((section) => (
              <section key={section.id} className="panel market-snapshot-panel module-report-section">
                <div className="section-heading">
                  <div>
                    <h2>{section.title}</h2>
                  </div>
                  <span className="market-section-meta">
                    Source: {displayValue(section.source)} <span>Time: {formatPanelTime(section.fetched_at)}</span>
                  </span>
                </div>
                <div className="snapshot-grid module-dynamic-grid">
                  {section.cards.map((card) => (
                    <div key={`${section.id}-${card.label}`}>
                      <span>{card.label}</span>
                      <strong>{displayValue(card.value)}</strong>
                      {card.status && <StatusBadge status={card.status} />}
                    </div>
                  ))}
                </div>
              </section>
            ))}

            {visibleChipTables.map((table) => (
              <section key={table.id} className="panel module-market-strip">
                <div className="section-heading">
                  <div>
                    <h2>{table.title}</h2>
                  </div>
                  <StatusBadge status="fresh" />
                </div>
                <DataTable rows={table.rows} columns={table.columns} renderCell={renderReportCell} />
              </section>
            ))}

            <section className="panel module-market-strip">
              <div className="section-heading">
                <div>
                  <h2>Source Status</h2>
                </div>
                <RadioTower aria-hidden="true" size={20} />
              </div>
              <div className="market-source-grid">
                {(chipPayload?.source_status ?? []).map((source) => (
                  <div key={source.source} className="market-source-card">
                    <div>
                      <strong>{source.source}</strong>
                      <StatusBadge status={source.status} />
                    </div>
                    {sourceStatusDetail(source) && <span>{sourceStatusDetail(source)}</span>}
                    {source.last_error && <p>{source.last_error}</p>}
                  </div>
                ))}
              </div>
            </section>

            {chipSections.length === 0 && visibleChipTables.length === 0 && (
              <EmptyState title="No chip/liquidity payload" detail="The chip and liquidity connector returned no structured sections or table rows for this symbol." />
            )}
          </>
        )}
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
