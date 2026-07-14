import { ServerCog } from "lucide-react";
import type { DataJob, SourceHealth } from "../types";
import { DataTable } from "./DataTable";
import { EmptyState } from "./EmptyState";

interface SystemViewProps {
  sources: SourceHealth[];
  jobs: DataJob[];
  loading: boolean;
  error: string | null;
}

export function SystemView({ sources, jobs, loading, error }: SystemViewProps) {
  if (loading) {
    return <div className="panel loading-panel">Loading system state...</div>;
  }

  if (error) {
    return <EmptyState title="System API unavailable" detail={error} />;
  }

  return (
    <div className="content-grid">
      <section className="panel hero-panel">
        <div>
          <h1>System View</h1>
          <p>Data source health, collection jobs, failure messages and freshness state.</p>
        </div>
        <div className="system-glyph">
          <ServerCog aria-hidden="true" size={28} />
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Data Sources</h2>
            <p>Latest known health state for each local connector source.</p>
          </div>
        </div>
        <DataTable rows={sources} emptyLabel="No source health rows yet." />
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Jobs</h2>
            <p>Collection, seed and backfill job history.</p>
          </div>
        </div>
        <DataTable rows={jobs} emptyLabel="No jobs have been recorded yet." />
      </section>
    </div>
  );
}
