import { BarChart3, FileText, ListChecks, RadioTower, RefreshCw } from "lucide-react";
import type { BoardMappingResponse, ChartResponse, MarketQuote, ModuleDataResponse, ModuleDefinition } from "../types";
import { DataTable } from "./DataTable";
import { EmptyState } from "./EmptyState";
import { KLineChart } from "./KLineChart";
import { StatusBadge } from "./StatusBadge";

interface ModuleViewProps {
  module: ModuleDefinition | undefined;
  data: ModuleDataResponse | null;
  loading: boolean;
  error: string | null;
  selectedSymbol: string;
  chart: ChartResponse | null;
  chartLoading: boolean;
  chartError: string | null;
  boards: BoardMappingResponse | null;
  boardError: string | null;
  chartIndicators: string[];
  onChartIndicatorsChange: (indicators: string[]) => void;
  quote: MarketQuote | null;
  onRefreshMarket: () => void;
  onRefreshModule: () => void;
  marketRefreshing: boolean;
  moduleRefreshing: boolean;
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
  quote,
  onRefreshMarket,
  onRefreshModule,
  marketRefreshing,
  moduleRefreshing
}: ModuleViewProps) {
  if (!module) {
    return <EmptyState title="Unknown module" detail="Select one of the ten configured navigation modules." />;
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

      {module.id === "market" && (
        <KLineChart
          rows={chart?.rows ?? []}
          quote={quote}
          boards={boards}
          boardError={boardError}
          enabledIndicators={chartIndicators}
          onIndicatorsChange={onChartIndicatorsChange}
          indicatorStatus={chart?.indicator_status}
          indicatorError={chart?.indicator_error ?? null}
          loading={chartLoading}
          error={chartError}
          onRefresh={onRefreshMarket}
          refreshing={marketRefreshing}
        />
      )}

      {module.id === "market" && (
        <section className="panel module-market-strip">
          <div className="section-heading">
            <div>
              <h2>Market Workspace</h2>
              <p>Current V1.1 scope: cached public-source quote, daily K-line, MA overlays and local data lineage.</p>
            </div>
            <BarChart3 aria-hidden="true" size={20} />
          </div>
          <div className="market-placeholders">
            <span>Five-level order book: placeholder</span>
            <span>PE/PB/market cap: fundamentals table</span>
            <span>Index/ETF context: planned connector</span>
          </div>
        </section>
      )}

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
