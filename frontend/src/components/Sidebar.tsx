import { Activity, Database, Gauge, Layers, Server } from "lucide-react";
import type { ModuleDefinition, SourceHealth } from "../types";
import { StatusBadge } from "./StatusBadge";

interface SidebarProps {
  modules: ModuleDefinition[];
  activeView: "security" | "module" | "system";
  activeModule: string;
  onSelectSecurity: () => void;
  onSelectModule: (moduleId: string) => void;
  onSelectSystem: () => void;
  sourceHealth: SourceHealth[];
}

export function Sidebar({
  modules,
  activeView,
  activeModule,
  onSelectSecurity,
  onSelectModule,
  onSelectSystem,
  sourceHealth
}: SidebarProps) {
  const healthByModule = new Map(sourceHealth.map((item) => [item.module, item]));

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          <Activity aria-hidden="true" size={20} />
        </div>
        <div>
          <strong>A-Share Workbench</strong>
          <span>Local research database</span>
        </div>
      </div>

      <nav className="nav-section" aria-label="Workspace views">
        <button className={activeView === "security" ? "nav-item active" : "nav-item"} onClick={onSelectSecurity}>
          <Gauge aria-hidden="true" size={17} />
          <span>Security View</span>
        </button>
        <button className={activeView === "system" ? "nav-item active" : "nav-item"} onClick={onSelectSystem}>
          <Server aria-hidden="true" size={17} />
          <span>System View</span>
        </button>
      </nav>

      <div className="module-list-label">
        <Layers aria-hidden="true" size={15} />
        <span>Ten-layer modules</span>
      </div>

      <nav className="module-list" aria-label="Data modules">
        {modules.map((module) => (
          <button
            key={module.id}
            className={activeView === "module" && activeModule === module.id ? "module-item active" : "module-item"}
            onClick={() => onSelectModule(module.id)}
          >
            <Database aria-hidden="true" size={16} />
            <span className="module-copy">
              <span>{module.label}</span>
              <small>{module.layer}</small>
              <small>{healthByModule.get(module.id)?.updated_at ?? module.sources[0] ?? "No source"}</small>
            </span>
            <StatusBadge status={module.status} />
          </button>
        ))}
      </nav>
    </aside>
  );
}
