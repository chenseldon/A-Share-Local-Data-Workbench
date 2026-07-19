import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  type ChartPeriod,
  fetchConnectorCapabilities,
  fetchHealth,
  fetchSecurityBoards,
  fetchSecurityChart,
  fetchJobs,
  fetchModuleData,
  fetchModules,
  fetchSecurityUniverseStatus,
  fetchSecurityOverview,
  fetchSourceHealth,
  refreshModule,
  refreshSecurity,
  refreshSecurityUniverse,
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
  BoardMappingResponse,
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
const backgroundRefreshModules = ["fundamentals", "announcements", "reports", "signals", "chip_liquidity", "news"];
const universeReadyCount = 7400;

interface UpdateProgress {
  active: boolean;
  percent: number;
  message: string;
}

interface ToastState {
  kind: "success" | "failed";
  message: string;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown request failure.";
}

export default function App() {
  const [modules, setModules] = useState<ModuleDefinition[]>(fallbackModules);
  const [activeView, setActiveView] = useState<ActiveView>("security");
  const [activeModule, setActiveModule] = useState("market");
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Security[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  const [overview, setOverview] = useState<SecurityOverviewType | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [overviewError, setOverviewError] = useState<string | null>(null);
  const [chart, setChart] = useState<ChartResponse | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState<string | null>(null);
  const [boards, setBoards] = useState<BoardMappingResponse | null>(null);
  const [boardError, setBoardError] = useState<string | null>(null);
  const [chartIndicators, setChartIndicators] = useState<string[]>(["ma", "volume", "macd", "rsi"]);
  const [chartPeriod, setChartPeriod] = useState<ChartPeriod>("1d");
  const [marketRefreshing, setMarketRefreshing] = useState(false);
  const [moduleRefreshing, setModuleRefreshing] = useState(false);

  const [moduleData, setModuleData] = useState<ModuleDataResponse | null>(null);
  const [moduleLoading, setModuleLoading] = useState(false);
  const [moduleError, setModuleError] = useState<string | null>(null);
  const refreshFirstSymbolRef = useRef<string | null>(null);

  const [sources, setSources] = useState<SourceHealth[]>([]);
  const [jobs, setJobs] = useState<DataJob[]>([]);
  const [capabilities, setCapabilities] = useState<ConnectorCapability[]>([]);
  const [systemLoading, setSystemLoading] = useState(false);
  const [systemError, setSystemError] = useState<string | null>(null);
  const [updateProgress, setUpdateProgress] = useState<UpdateProgress | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [apiHealthError, setApiHealthError] = useState<string | null>(null);

  const selectedModule = useMemo(
    () => modules.find((module) => module.id === activeModule),
    [activeModule, modules]
  );
  const chartIndicatorKey = useMemo(() => chartIndicators.join(","), [chartIndicators]);

  useEffect(() => {
    fetchHealth()
      .then(() => setApiHealthError(null))
      .catch((error: unknown) => setApiHealthError(errorMessage(error)));
    fetchModules()
      .then(setModules)
      .catch(() => setModules(fallbackModules));
    fetchSourceHealth()
      .then((response) => setSources(response.rows))
      .catch(() => setSources([]));
    fetchConnectorCapabilities()
      .then((response) => setCapabilities(response.rows))
      .catch(() => setCapabilities([]));
    fetchSecurityUniverseStatus()
      .then((status) => {
        if (status.count < universeReadyCount) {
          setUpdateProgress({ active: true, percent: 8, message: "Building free-stockdb symbol directory..." });
          return refreshSecurityUniverse()
            .then(() => setUpdateProgress({ active: true, percent: 100, message: "Symbol directory ready." }))
            .catch(() => setToast({ kind: "failed", message: "Symbol directory refresh failed." }))
            .finally(() => setTimeout(() => setUpdateProgress(null), 700));
        }
        return undefined;
      })
      .catch(() => undefined);
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
      setOverview(null);
      setChart(null);
      return;
    }
    if (refreshFirstSymbolRef.current === selectedSymbol) {
      return;
    }
    setOverviewLoading(true);
    setChartLoading(true);
    setOverviewError(null);
    setChartError(null);
    fetchSecurityOverview(selectedSymbol)
      .then((overviewResponse) => {
        setOverview(overviewResponse);
      })
      .catch((error: unknown) => {
        setOverview(null);
        setOverviewError(errorMessage(error));
      })
      .finally(() => {
        setOverviewLoading(false);
      });
    fetchSecurityChart(selectedSymbol, chartIndicators, chartPeriod)
      .then(setChart)
      .catch((error: unknown) => {
        setChart(null);
        setChartError(errorMessage(error));
      })
      .finally(() => setChartLoading(false));
    fetchSecurityBoards(selectedSymbol)
      .then((response) => {
        setBoards(response);
        setBoardError(null);
      })
      .catch((error: unknown) => {
        setBoards(null);
        setBoardError(errorMessage(error));
      });
  }, [selectedSymbol, chartIndicatorKey, chartPeriod]);

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

  function handleSelectSymbol(symbol: string, keepCurrentModule = false) {
    refreshFirstSymbolRef.current = symbol;
    setSelectedSymbol(symbol);
    setQuery("");
    setSearchResults([]);
    setActiveView(keepCurrentModule && activeView === "module" ? "module" : "security");
    setOverview(null);
    setChart(null);
    setBoards(null);
    setOverviewLoading(true);
    setChartLoading(true);
    setOverviewError(null);
    setChartError(null);
    setBoardError(null);
    void runFullRefresh(symbol);
  }

  function refreshCurrentView() {
    void runFullRefresh();
  }

  async function runFullRefresh(targetSymbol = selectedSymbol) {
    if (!targetSymbol) {
      return;
    }
    setToast(null);
    setMarketRefreshing(true);
    setOverviewError(null);
    setChartError(null);
    setUpdateProgress({ active: true, percent: 5, message: "Checking symbol directory..." });
    const failures: string[] = [];
    try {
      const universe = await fetchSecurityUniverseStatus();
      if (universe.count < universeReadyCount) {
        setUpdateProgress({ active: true, percent: 12, message: "Building free-stockdb symbol directory..." });
        await refreshSecurityUniverse();
      }
      setUpdateProgress({ active: true, percent: 35, message: "Refreshing market and K-line data..." });
      await refreshSecurity(targetSymbol, false);
      setUpdateProgress({ active: true, percent: 55, message: "Refreshing module data..." });
      const moduleResults = await Promise.allSettled(backgroundRefreshModules.map((moduleId) => refreshModule(moduleId, targetSymbol)));
      moduleResults.forEach((result, index) => {
        if (result.status === "rejected") {
          failures.push(backgroundRefreshModules[index]);
        }
      });
      setUpdateProgress({ active: true, percent: 85, message: "Updating view..." });
      const [overviewResponse, chartResponse] = await Promise.all([
        fetchSecurityOverview(targetSymbol),
        fetchSecurityChart(targetSymbol, chartIndicators, chartPeriod)
      ]);
      setOverview(overviewResponse);
      setChart(chartResponse);
      await fetchSecurityBoards(targetSymbol)
        .then((response) => {
          setBoards(response);
          setBoardError(null);
        })
        .catch((error: unknown) => {
          setBoards(null);
          setBoardError(errorMessage(error));
        });
      await fetchSourceHealth()
        .then((response) => setSources(response.rows))
        .catch(() => setSources([]));
      if (activeView === "module") {
        await fetchModuleData(activeModule, targetSymbol)
          .then(setModuleData)
          .catch((error: unknown) => setModuleError(errorMessage(error)));
      }
      setUpdateProgress({ active: true, percent: 100, message: failures.length ? "Update finished with failed modules." : "Update complete." });
      setToast({
        kind: failures.length ? "failed" : "success",
        message: failures.length ? `${failures.join(", ")} \u90e8\u5206\u63d0\u53d6\u5931\u8d25` : "\u66f4\u65b0\u6210\u529f",
      });
    } catch (error: unknown) {
      const message = errorMessage(error);
      setOverviewError(message);
      setChartError(message);
      setToast({ kind: "failed", message });
    } finally {
      if (refreshFirstSymbolRef.current === targetSymbol) {
        refreshFirstSymbolRef.current = null;
      }
      setOverviewLoading(false);
      setChartLoading(false);
      setMarketRefreshing(false);
      setTimeout(() => setUpdateProgress(null), 900);
      setTimeout(() => setToast(null), 4200);
    }
  }

  function handleChartIndicatorsChange(nextIndicators: string[]) {
    setChartIndicators(nextIndicators);
  }

  function handleChartPeriodChange(nextPeriod: ChartPeriod) {
    setChartPeriod(nextPeriod);
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

  const darkModuleActive = activeView === "module" && ["market", "fundamentals", "reports", "signals", "chip_liquidity", "news", "announcements", "limit_up", "etf_options", "sentiment"].includes(activeModule);
  const darkWorkspaceActive = activeView === "security" || darkModuleActive;

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
      <main className={darkWorkspaceActive ? "workspace workspace-chart-only" : "workspace"}>
        {!darkWorkspaceActive && (
          <TopBar
            query={query}
            searchResults={searchResults}
            isSearching={isSearching}
            onQueryChange={setQuery}
            onSelectSymbol={handleSelectSymbol}
            onRefresh={refreshCurrentView}
          />
        )}
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
              boards={boards}
              boardError={boardError}
              chartIndicators={chartIndicators}
              onChartIndicatorsChange={handleChartIndicatorsChange}
              chartPeriod={chartPeriod}
              onChartPeriodChange={handleChartPeriodChange}
              onRefreshMarket={refreshCurrentView}
              marketRefreshing={marketRefreshing}
              searchQuery={query}
              searchResults={searchResults}
              isSearching={isSearching}
              onSearchQueryChange={setQuery}
              onSelectSymbol={(symbol) => handleSelectSymbol(symbol)}
              apiHealthError={apiHealthError}
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
              boards={boards}
              boardError={boardError}
              chartIndicators={chartIndicators}
              onChartIndicatorsChange={handleChartIndicatorsChange}
              chartPeriod={chartPeriod}
              onChartPeriodChange={handleChartPeriodChange}
              security={overview?.security ?? null}
              quote={overview?.quote ?? null}
              onRefreshMarket={refreshCurrentView}
              onRefreshModule={refreshActiveModule}
              marketRefreshing={marketRefreshing}
              moduleRefreshing={moduleRefreshing}
              searchQuery={query}
              searchResults={searchResults}
              isSearching={isSearching}
              onSearchQueryChange={setQuery}
              onSelectSymbol={(symbol) => handleSelectSymbol(symbol, true)}
            />
          )}
          {activeView === "system" && (
            <SystemView sources={sources} jobs={jobs} capabilities={capabilities} loading={systemLoading} error={systemError} />
          )}
        </div>
        {updateProgress?.active && (
          <div className="update-progress" role="status" aria-live="polite">
            <div className="update-progress-card">
              <strong>{updateProgress.message}</strong>
              <div className="progress-track">
                <span style={{ width: `${updateProgress.percent}%` }} />
              </div>
              <small>{updateProgress.percent}%</small>
            </div>
          </div>
        )}
        {toast && <div className={`toast toast-${toast.kind}`}>{toast.message}</div>}
      </main>
    </div>
  );
}
