import { AlertTriangle, FileText, LineChart, Newspaper, WalletCards } from "lucide-react";
import type { ChartResponse, SecurityOverview as SecurityOverviewType } from "../types";
import { DataTable } from "./DataTable";
import { EmptyState } from "./EmptyState";
import { KLineChart } from "./KLineChart";
import { StatusBadge } from "./StatusBadge";

interface SecurityOverviewProps {
  overview: SecurityOverviewType | null;
  loading: boolean;
  error: string | null;
  selectedSymbol: string;
  chart: ChartResponse | null;
  chartLoading: boolean;
  chartError: string | null;
  onRefreshMarket: () => void;
  marketRefreshing: boolean;
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
  onRefreshMarket,
  marketRefreshing
}: SecurityOverviewProps) {
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

  const security = overview.security;

  return (
    <div className="content-grid">
      <section className="panel hero-panel">
        <div>
          <h1>{security.symbol}</h1>
          <p>{security.name}</p>
        </div>
        <div className="security-meta">
          <span>{security.exchange}</span>
          <span>{security.asset_type}</span>
          <span>{security.sector ?? "No sector"}</span>
          <StatusBadge status={security.source === "local_fixture" ? "not_collected" : "fresh"} />
        </div>
      </section>

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

      {security.source === "local_fixture" && (
        <section className="notice-panel">
          <AlertTriangle aria-hidden="true" size={18} />
          <span>Fixture data is loaded for development only. Do not treat it as current market data.</span>
        </section>
      )}

      <KLineChart
        rows={chart?.rows ?? []}
        quote={overview.quote}
        status={chart?.status ?? "not_collected"}
        loading={chartLoading}
        error={chartError}
        onRefresh={onRefreshMarket}
        refreshing={marketRefreshing}
      />

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
            <p>Financial snapshot and valuation fields from local storage.</p>
          </div>
        </div>
        <DataTable rows={overview.fundamentals ? [overview.fundamentals] : []} />
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Announcements</h2>
            <p>Announcement titles and publication timestamps.</p>
          </div>
        </div>
        <DataTable rows={overview.announcements} />
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Research Reports</h2>
            <p>Report metadata and rating context from local storage.</p>
          </div>
        </div>
        <DataTable rows={overview.reports} />
      </section>
    </div>
  );
}
