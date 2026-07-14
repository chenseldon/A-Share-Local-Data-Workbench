import type { ModuleDataResponse, ModuleDefinition } from "../types";
import { DataTable } from "./DataTable";
import { EmptyState } from "./EmptyState";
import { StatusBadge } from "./StatusBadge";

interface ModuleViewProps {
  module: ModuleDefinition | undefined;
  data: ModuleDataResponse | null;
  loading: boolean;
  error: string | null;
  selectedSymbol: string;
}

export function ModuleView({ module, data, loading, error, selectedSymbol }: ModuleViewProps) {
  if (!module) {
    return <EmptyState title="Unknown module" detail="Select one of the ten configured navigation modules." />;
  }

  return (
    <div className="content-grid">
      <section className="panel hero-panel">
        <div>
          <h1>{module.label}</h1>
          <p>
            {module.layer} · {module.description}
          </p>
        </div>
        <div className="security-meta">
          <span>{selectedSymbol || "All local symbols"}</span>
          <StatusBadge status={module.status} />
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
          <DataTable
            rows={data.rows}
            emptyLabel={
              data.status === "not_configured"
                ? "This module is in the ten-layer navigation but no connector is configured yet."
                : "No local data has been collected for this module yet."
            }
          />
        </section>
      )}
    </div>
  );
}
