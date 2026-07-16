import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchConnectorCapabilities,
  fetchSecurityChart,
  fetchJobs,
  fetchModuleData,
  fetchModules,
  fetchSecurityOverview,
  fetchSourceHealth,
  refreshModule,
  refreshSecurity,
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
  ChartResponse,
  ConnectorCapability,
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

function isCompleteSymbolQuery(value: string): boolean {
  const query = value.trim().toUpperCase();
  return /^\d{6}$/.test(query) || /^\d{6}\.(SH|SZ|BJ)$/.test(query);
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
  const [chart, setChart] = useState<ChartResponse | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState<string | null>(null);
  const [marketRefreshing, setMarketRefreshing] = useState(false);
  const [moduleRefreshing, setModuleRefreshing] = useState(false);

  const [moduleData, setModuleData] = useState<ModuleDataResponse | null>(null);
  const [moduleLoading, setModuleLoading] = useState(false);
  const [moduleError, setModuleError] = useState<string | null>(null);

  const [sources, setSources] = useState<SourceHealth[]>([]);
  const [jobs, setJobs] = useState<DataJob[]>([]);
  const [capabilities, setCapabilities] = useState<ConnectorCapability[]>([]);
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
    fetchSourceHealth()
      .then((response) => setSources(response.rows))
      .catch(() => setSources([]));
    fetchConnectorCapabilities()
      .then((response) => setCapabilities(response.rows))
      .catch(() => setCapabilities([]));
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
          if (isCompleteSymbolQuery(query) && response.rows.length === 1) {
            handleSelectSymbol(response.rows[0].symbol);
          }
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
    setChartLoading(true);
    setOverviewError(null);
    setChartError(null);
    Promise.all([fetchSecurityOverview(selectedSymbol), fetchSecurityChart(selectedSymbol)])
      .then(([overviewResponse, chartResponse]) => {
        setOverview(overviewResponse);
        setChart(chartResponse);
      })
      .catch((error: unknown) => {
        setOverview(null);
        setChart(null);
        setOverviewError(errorMessage(error));
      })
      .finally(() => {
        setOverviewLoading(false);
        setChartLoading(false);
      });
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
    Promise.all([fetchSourceHealth(), fetchJobs(), fetchConnectorCapabilities()])
      .then(([sourceResponse, jobResponse, capabilityResponse]) => {
        setSources(sourceResponse.rows);
        setJobs(jobResponse.rows);
        setCapabilities(capabilityResponse.rows);
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
    setMarketRefreshing(true);
    setOverviewLoading(true);
    setChartLoading(true);
    setOverviewError(null);
    setChartError(null);
    refreshSecurity(symbol, true)
      .then(() => Promise.all([fetchSecurityOverview(symbol), fetchSecurityChart(symbol)]))
      .then(([overviewResponse, chartResponse]) => {
        setOverview(overviewResponse);
        setChart(chartResponse);
      })
      .catch((error: unknown) => {
        const message = errorMessage(error);
        setOverviewError(message);
        setChartError(message);
      })
      .finally(() => {
        setOverviewLoading(false);
        setChartLoading(false);
        setMarketRefreshing(false);
      });
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

  function refreshMarketData() {
    if (!selectedSymbol) {
      return;
    }
    setMarketRefreshing(true);
    setOverviewError(null);
    setChartError(null);
    refreshSecurity(selectedSymbol)
      .then(() => {
        loadSecurity();
        if (activeView === "module") {
          loadModule();
        }
      })
      .catch((error: unknown) => {
        const message = errorMessage(error);
        setOverviewError(message);
        setChartError(message);
      })
      .finally(() => setMarketRefreshing(false));
  }

  function refreshActiveModule() {
    if (!activeModule) {
      return;
    }
    setModuleRefreshing(true);
    setModuleError(null);
    refreshModule(activeModule, selectedSymbol)
      .then(() => {
        loadModule();
        fetchSourceHealth()
          .then((response) => setSources(response.rows))
          .catch(() => setSources([]));
      })
      .catch((error: unknown) => setModuleError(errorMessage(error)))
      .finally(() => setModuleRefreshing(false));
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
        sourceHealth={sources}
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
              chart={chart}
              chartLoading={chartLoading}
              chartError={chartError}
              onRefreshMarket={refreshMarketData}
              marketRefreshing={marketRefreshing}
            />
          )}
          {activeView === "module" && (
            <ModuleView
              module={selectedModule}
              data={moduleData}
              loading={moduleLoading}
              error={moduleError}
              selectedSymbol={selectedSymbol}
              chart={chart}
              chartLoading={chartLoading}
              chartError={chartError}
              quote={overview?.quote ?? null}
              onRefreshMarket={refreshMarketData}
              onRefreshModule={refreshActiveModule}
              marketRefreshing={marketRefreshing}
              moduleRefreshing={moduleRefreshing}
            />
          )}
          {activeView === "system" && (
            <SystemView sources={sources} jobs={jobs} capabilities={capabilities} loading={systemLoading} error={systemError} />
          )}
        </div>
      </main>
    </div>
  );
}
