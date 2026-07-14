import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchJobs,
  fetchModuleData,
  fetchModules,
  fetchSecurityOverview,
  fetchSourceHealth,
  searchSecurities
} from "./api";
import { ModuleView } from "./components/ModuleView";
import { SecurityOverview } from "./components/SecurityOverview";
import { Sidebar } from "./components/Sidebar";
import { SystemView } from "./components/SystemView";
import { TopBar } from "./components/TopBar";
import { fallbackModules } from "./data/fallbackModules";
import type {
  DataJob,
  ModuleDataResponse,
  ModuleDefinition,
  SearchResponse,
  Security,
  SecurityOverview as SecurityOverviewType,
  SourceHealth
} from "./types";

type ActiveView = "security" | "module" | "system";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown request failure.";
}

export default function App() {
  const [modules, setModules] = useState<ModuleDefinition[]>(fallbackModules);
  const [activeView, setActiveView] = useState<ActiveView>("security");
  const [activeModule, setActiveModule] = useState("market");
  const [selectedSymbol, setSelectedSymbol] = useState("600519.SH");
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Security[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  const [overview, setOverview] = useState<SecurityOverviewType | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [overviewError, setOverviewError] = useState<string | null>(null);

  const [moduleData, setModuleData] = useState<ModuleDataResponse | null>(null);
  const [moduleLoading, setModuleLoading] = useState(false);
  const [moduleError, setModuleError] = useState<string | null>(null);

  const [sources, setSources] = useState<SourceHealth[]>([]);
  const [jobs, setJobs] = useState<DataJob[]>([]);
  const [systemLoading, setSystemLoading] = useState(false);
  const [systemError, setSystemError] = useState<string | null>(null);

  const selectedModule = useMemo(
    () => modules.find((module) => module.id === activeModule),
    [activeModule, modules]
  );

  useEffect(() => {
    fetchModules()
      .then(setModules)
      .catch(() => setModules(fallbackModules));
  }, []);

  useEffect(() => {
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }

    let cancelled = false;
    setIsSearching(true);
    searchSecurities(query)
      .then((response: SearchResponse) => {
        if (!cancelled) {
          setSearchResults(response.rows);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSearchResults([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsSearching(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [query]);

  const loadSecurity = useCallback(() => {
    if (!selectedSymbol) {
      return;
    }
    setOverviewLoading(true);
    setOverviewError(null);
    fetchSecurityOverview(selectedSymbol)
      .then(setOverview)
      .catch((error: unknown) => {
        setOverview(null);
        setOverviewError(errorMessage(error));
      })
      .finally(() => setOverviewLoading(false));
  }, [selectedSymbol]);

  const loadModule = useCallback(() => {
    setModuleLoading(true);
    setModuleError(null);
    fetchModuleData(activeModule, selectedSymbol)
      .then(setModuleData)
      .catch((error: unknown) => {
        setModuleData(null);
        setModuleError(errorMessage(error));
      })
      .finally(() => setModuleLoading(false));
  }, [activeModule, selectedSymbol]);

  const loadSystem = useCallback(() => {
    setSystemLoading(true);
    setSystemError(null);
    Promise.all([fetchSourceHealth(), fetchJobs()])
      .then(([sourceResponse, jobResponse]) => {
        setSources(sourceResponse.rows);
        setJobs(jobResponse.rows);
      })
      .catch((error: unknown) => {
        setSources([]);
        setJobs([]);
        setSystemError(errorMessage(error));
      })
      .finally(() => setSystemLoading(false));
  }, []);

  useEffect(() => {
    if (activeView === "security") {
      loadSecurity();
    }
  }, [activeView, loadSecurity]);

  useEffect(() => {
    if (activeView === "module") {
      loadModule();
    }
  }, [activeView, loadModule]);

  useEffect(() => {
    if (activeView === "system") {
      loadSystem();
    }
  }, [activeView, loadSystem]);

  function handleSelectSymbol(symbol: string) {
    setSelectedSymbol(symbol);
    setQuery("");
    setSearchResults([]);
    setActiveView("security");
  }

  function refreshCurrentView() {
    if (activeView === "security") {
      loadSecurity();
    } else if (activeView === "module") {
      loadModule();
    } else {
      loadSystem();
    }
  }

  return (
    <div className="app-shell">
      <Sidebar
        modules={modules}
        activeView={activeView}
        activeModule={activeModule}
        onSelectSecurity={() => setActiveView("security")}
        onSelectModule={(moduleId) => {
          setActiveModule(moduleId);
          setActiveView("module");
        }}
        onSelectSystem={() => setActiveView("system")}
      />
      <main className="workspace">
        <TopBar
          query={query}
          selectedSymbol={selectedSymbol}
          searchResults={searchResults}
          isSearching={isSearching}
          onQueryChange={setQuery}
          onSelectSymbol={handleSelectSymbol}
          onRefresh={refreshCurrentView}
        />
        <div className="workspace-body">
          {activeView === "security" && (
            <SecurityOverview
              overview={overview}
              loading={overviewLoading}
              error={overviewError}
              selectedSymbol={selectedSymbol}
            />
          )}
          {activeView === "module" && (
            <ModuleView
              module={selectedModule}
              data={moduleData}
              loading={moduleLoading}
              error={moduleError}
              selectedSymbol={selectedSymbol}
            />
          )}
          {activeView === "system" && (
            <SystemView sources={sources} jobs={jobs} loading={systemLoading} error={systemError} />
          )}
        </div>
      </main>
    </div>
  );
}
