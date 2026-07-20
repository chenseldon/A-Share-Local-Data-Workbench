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
  generateAiAnalysis,
  refreshModule,
  refreshSecurity,
  refreshSecurityUniverse,
  searchSecurities
} from "./api";
import { AiRightRail } from "./components/AiRightRail";
import { ModuleView } from "./components/ModuleView";
import { SecurityOverview } from "./components/SecurityOverview";
import { Sidebar } from "./components/Sidebar";
import { SystemView } from "./components/SystemView";
import { TopBar } from "./components/TopBar";
import { fallbackModules } from "./data/fallbackModules";
import type {
  AiAnalysisResponse,
  AiAnalysisScope,
  AiProvider,
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
const backgroundRefreshModules = ["fundamentals", "announcements", "news", "reports", "chip_liquidity", "signals"];
const modulePrefetchModules = ["market", "fundamentals", "announcements", "news", "reports", "chip_liquidity", "signals", "etf_options"];
const etfOptionUnderlyings = new Set(["510050.SH", "510300.SH", "588000.SH", "510500.SH"]);
const universeReadyCount = 7400;
const aiDefaultModels: Record<AiProvider, string> = {
  openai: "gpt-5",
  anthropic: "claude-sonnet-5",
  deepseek: "deepseek-v4-flash"
};

interface UpdateProgress {
  active: boolean;
  percent: number;
  message: string;
}

interface ToastState {
  kind: "success" | "failed";
  message: string;
}

interface AiAnalystState {
  provider: AiProvider;
  model: string;
  apiKey: string;
  scope: AiAnalysisScope;
  moduleId: string;
  includeLatestRefresh: boolean;
  loading: boolean;
  error: string | null;
  result: AiAnalysisResponse | null;
}

type RightPanel = "settings" | "ai" | null;

type SettledRequest<T> = { status: "fulfilled"; value: T } | { status: "rejected"; reason: unknown };

function settleRequest<T>(promise: Promise<T>): Promise<SettledRequest<T>> {
  return promise.then(
    (value) => ({ status: "fulfilled", value }),
    (reason: unknown) => ({ status: "rejected", reason })
  );
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown request failure.";
}

function moduleCacheKey(moduleId: string, symbol: string | null): string {
  return `${moduleId}:${symbol ?? ""}`;
}

function shouldRefreshEtfOptions(moduleId: string, symbol: string | null): boolean {
  return moduleId === "etf_options" || (symbol !== null && etfOptionUnderlyings.has(symbol.toUpperCase()));
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function snapshotSignature(overview: SecurityOverviewType): string {
  return (overview.module_snapshots ?? [])
    .map((snapshot) => `${snapshot.module}:${snapshot.tables.map((table) => `${table.id}:${table.rows.length}`).join(",")}`)
    .join("|");
}

function collectVisibleTables(root: HTMLElement | null) {
  if (!root) {
    return [];
  }
  return Array.from(root.querySelectorAll("table")).slice(0, 24).map((table) => {
    const caption = table.closest("section, .security-snapshot-table")?.querySelector("h2, h3")?.textContent?.trim() ?? "";
    const headers = Array.from(table.querySelectorAll("th")).map((cell) => cell.textContent?.trim() ?? "");
    const rows = Array.from(table.querySelectorAll("tbody tr")).slice(0, 40).map((row) =>
      Array.from(row.querySelectorAll("td")).map((cell) => cell.textContent?.trim() ?? "")
    );
    return { caption, headers, rows };
  });
}

function collectVisibleLinks(root: HTMLElement | null) {
  if (!root) {
    return [];
  }
  return Array.from(root.querySelectorAll<HTMLAnchorElement>("a[href]")).slice(0, 120).map((anchor) => ({
    text: anchor.textContent?.trim() ?? "",
    href: anchor.href,
  }));
}

async function captureElementScreenshotBase64(element: HTMLElement): Promise<string | null> {
  const rect = element.getBoundingClientRect();
  const width = Math.max(320, Math.min(1400, Math.ceil(rect.width)));
  const height = Math.max(320, Math.min(2200, Math.ceil(rect.height)));
  const clone = element.cloneNode(true) as HTMLElement;
  clone.querySelectorAll(".chart-actions, .chart-toolrail, .indicator-menu, .start-search-results, .drawing-layer").forEach((node) => node.remove());
  clone.style.width = `${width}px`;
  clone.style.height = `${height}px`;
  clone.style.overflow = "hidden";
  const serialized = new XMLSerializer().serializeToString(clone);
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
      <foreignObject width="100%" height="100%">
        <div xmlns="http://www.w3.org/1999/xhtml" style="background:#0b1118;color:#eef4f7;font-family:Inter,Arial,sans-serif;width:${width}px;height:${height}px;overflow:hidden;">
          ${serialized}
        </div>
      </foreignObject>
    </svg>`;
  return new Promise((resolve) => {
    const image = new Image();
    image.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const context = canvas.getContext("2d");
        if (!context) {
          resolve(null);
          return;
        }
        context.drawImage(image, 0, 0);
        resolve(canvas.toDataURL("image/png").split(",")[1] ?? null);
      } catch {
        resolve(null);
      }
    };
    image.onerror = () => resolve(null);
    image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  });
}

function standaloneAiReportHtml(reportHtml: string): string {
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI Analyst Report</title>
  <style>${aiReportCss()}</style>
</head>
<body>
  <main class="ai-report-print-shell">${reportHtml}</main>
</body>
</html>`;
}

function aiReportCss(): string {
  return `
    :root{color-scheme:dark;--bg:#071018;--surface:#101923;--surface-strong:#142638;--ink:#eef4f7;--muted:#9fb0bd;--line:rgba(216,224,232,.16);--accent:#38bdf8;--danger:#fb7185;--success:#2dd4bf}
    *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    .ai-report-print-shell{max-width:1040px;margin:0 auto;padding:28px}
    .ai-report-document{display:grid;gap:14px}
    .ai-report-document h1{margin:0 0 8px;font-size:26px;line-height:1.2;color:#f8fafc}
    .ai-report-document h2{margin:14px 0 4px;font-size:17px;color:#67e8f9}
    .ai-report-document h3{margin:10px 0 2px;font-size:14px;color:#cbd5e1}
    .ai-report-document p,.ai-report-document li{color:#d8e0e8;line-height:1.65;font-size:13px}
    .ai-report-document section,.ai-report-document .card{border:1px solid var(--line);border-radius:8px;background:var(--surface);padding:14px}
    .ai-report-document table{width:100%;border-collapse:collapse;background:var(--surface);font-size:12px}
    .ai-report-document th,.ai-report-document td{border-bottom:1px solid var(--line);padding:8px;text-align:left;vertical-align:top}
    .ai-report-document th{background:var(--surface-strong);color:#ccd8df;text-transform:uppercase}
    .ai-report-document a{color:#67e8f9;text-decoration:none}
    @media print{body{background:var(--bg);-webkit-print-color-adjust:exact;print-color-adjust:exact}.ai-report-print-shell{padding:0}.ai-report-document section,.ai-report-document .card{break-inside:avoid}}
  `;
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
  const moduleDataCacheRef = useRef<Record<string, ModuleDataResponse>>({});
  const cachePrimingSymbolRef = useRef<string | null>(null);
  const [pendingModuleAnchor, setPendingModuleAnchor] = useState<string | null>(null);
  const workspaceBodyRef = useRef<HTMLDivElement | null>(null);
  const [dashboardCollapsed, setDashboardCollapsed] = useState(false);
  const [rightPanelOpen, setRightPanelOpen] = useState(false);
  const [rightPanel, setRightPanel] = useState<RightPanel>(null);

  const [sources, setSources] = useState<SourceHealth[]>([]);
  const [jobs, setJobs] = useState<DataJob[]>([]);
  const [capabilities, setCapabilities] = useState<ConnectorCapability[]>([]);
  const [systemLoading, setSystemLoading] = useState(false);
  const [systemError, setSystemError] = useState<string | null>(null);
  const [updateProgress, setUpdateProgress] = useState<UpdateProgress | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [apiHealthError, setApiHealthError] = useState<string | null>(null);
  const [aiAnalyst, setAiAnalyst] = useState<AiAnalystState>({
    provider: "openai",
    model: aiDefaultModels.openai,
    apiKey: "",
    scope: "current_page",
    moduleId: "market",
    includeLatestRefresh: false,
    loading: false,
    error: null,
    result: null,
  });

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
    if (cachePrimingSymbolRef.current === selectedSymbol) {
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

  const loadSymbolCache = useCallback(async (symbol: string | null) => {
    if (!symbol) {
      return;
    }
    setOverviewLoading(true);
    setChartLoading(true);
    setOverviewError(null);
    setChartError(null);
    setBoardError(null);
    try {
      const [overviewResult, chartResult, boardsResult, moduleResults] = await Promise.all([
        settleRequest(fetchSecurityOverview(symbol)),
        settleRequest(fetchSecurityChart(symbol, chartIndicators, chartPeriod)),
        settleRequest(fetchSecurityBoards(symbol)),
        settleRequest(Promise.allSettled(modulePrefetchModules.map((moduleId) => fetchModuleData(moduleId, symbol)))),
      ]);
      if (overviewResult.status === "fulfilled") {
        setOverview(overviewResult.value);
      } else {
        setOverview(null);
        setOverviewError(errorMessage(overviewResult.reason));
      }
      if (chartResult.status === "fulfilled") {
        setChart(chartResult.value);
      } else {
        setChart(null);
        setChartError(errorMessage(chartResult.reason));
      }
      if (boardsResult.status === "fulfilled") {
        setBoards(boardsResult.value);
        setBoardError(null);
      } else {
        setBoards(null);
        setBoardError(errorMessage(boardsResult.reason));
      }
      const prefetched: Record<string, ModuleDataResponse> = {};
      const settledModuleResults = moduleResults.status === "fulfilled" ? moduleResults.value : [];
      settledModuleResults.forEach((result, index) => {
        if (result.status === "fulfilled") {
          const moduleId = modulePrefetchModules[index];
          prefetched[moduleCacheKey(moduleId, symbol)] = result.value;
        }
      });
      if (Object.keys(prefetched).length > 0) {
        moduleDataCacheRef.current = { ...moduleDataCacheRef.current, ...prefetched };
        const activePrefetched = prefetched[moduleCacheKey(activeModule, symbol)];
        if (activeView === "module" && activePrefetched) {
          setModuleData(activePrefetched);
          setModuleError(null);
        }
      }
    } catch (error: unknown) {
      const message = errorMessage(error);
      setOverviewError(message);
      setChartError(message);
    } finally {
      setOverviewLoading(false);
      setChartLoading(false);
      if (cachePrimingSymbolRef.current === symbol) {
        cachePrimingSymbolRef.current = null;
      }
    }
  }, [activeModule, activeView, chartIndicators, chartIndicatorKey, chartPeriod]);

  const loadModule = useCallback(() => {
    const cacheKey = moduleCacheKey(activeModule, selectedSymbol);
    const cached = moduleDataCacheRef.current[cacheKey];
    if (cached) {
      setModuleData(cached);
    }
    setModuleLoading(true);
    setModuleError(null);
    fetchModuleData(activeModule, selectedSymbol)
      .then((response) => {
        setModuleData(response);
        moduleDataCacheRef.current = { ...moduleDataCacheRef.current, [cacheKey]: response };
      })
      .catch((error: unknown) => {
        if (!cached) {
          setModuleData(null);
        }
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
    if (activeView !== "module" || !pendingModuleAnchor || moduleLoading) {
      return;
    }
    let cancelled = false;
    let retryTimer: number | null = null;
    let attempts = 0;
    const scrollToAnchor = () => {
      if (cancelled) {
        return;
      }
      const target = document.getElementById(pendingModuleAnchor);
      if (!target) {
        attempts += 1;
        if (attempts < 24) {
          retryTimer = window.setTimeout(scrollToAnchor, 150);
        }
        return;
      }
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      target.classList.add("module-anchor-highlight");
      window.setTimeout(() => target.classList.remove("module-anchor-highlight"), 1600);
      setPendingModuleAnchor(null);
    };
    retryTimer = window.setTimeout(scrollToAnchor, 80);
    return () => {
      cancelled = true;
      if (retryTimer !== null) {
        window.clearTimeout(retryTimer);
      }
    };
  }, [activeView, pendingModuleAnchor, moduleLoading, moduleData]);

  useEffect(() => {
    if (activeView === "system") {
      loadSystem();
    }
  }, [activeView, loadSystem]);

  function handleSelectSymbol(symbol: string, keepCurrentModule = false) {
    cachePrimingSymbolRef.current = symbol;
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
    void loadSymbolCache(symbol).finally(() => {
      void runFullRefresh(symbol);
    });
  }

  function refreshCurrentView() {
    void runFullRefresh();
  }

  function openModuleSnapshot(moduleId: string, anchorId?: string | null) {
    setActiveModule(moduleId);
    setActiveView("module");
    setPendingModuleAnchor(anchorId ?? `module-${moduleId}-top`);
  }

  async function readBackSecurityContext(targetSymbol: string): Promise<string | null> {
    const [overviewResult, chartResult, boardsResult, prefetchResult] = await Promise.all([
      settleRequest(fetchSecurityOverview(targetSymbol)),
      settleRequest(fetchSecurityChart(targetSymbol, chartIndicators, chartPeriod)),
      settleRequest(fetchSecurityBoards(targetSymbol)),
      settleRequest(Promise.allSettled(modulePrefetchModules.map((moduleId) => fetchModuleData(moduleId, targetSymbol))))
    ]);
    if (overviewResult.status === "fulfilled") {
      setOverview(overviewResult.value);
      setOverviewError(null);
    } else {
      setOverviewError(errorMessage(overviewResult.reason));
    }
    if (chartResult.status === "fulfilled") {
      setChart(chartResult.value);
      setChartError(null);
    } else {
      setChartError(errorMessage(chartResult.reason));
    }
    if (boardsResult.status === "fulfilled") {
      setBoards(boardsResult.value);
      setBoardError(null);
    } else {
      setBoardError(errorMessage(boardsResult.reason));
    }
    const prefetched: Record<string, ModuleDataResponse> = {};
    const prefetchResults = prefetchResult.status === "fulfilled" ? prefetchResult.value : [];
    prefetchResults.forEach((result, index) => {
      if (result.status === "fulfilled") {
        const moduleId = modulePrefetchModules[index];
        prefetched[moduleCacheKey(moduleId, targetSymbol)] = result.value;
      } else if (modulePrefetchModules[index] === activeModule && activeView === "module") {
        setModuleError(errorMessage(result.reason));
      }
    });
    moduleDataCacheRef.current = { ...moduleDataCacheRef.current, ...prefetched };
    if (activeView === "module") {
      const activePrefetched = prefetched[moduleCacheKey(activeModule, targetSymbol)];
      if (activePrefetched) {
        setModuleData(activePrefetched);
        setModuleError(null);
      }
    }
    return overviewResult.status === "fulfilled" ? snapshotSignature(overviewResult.value) : null;
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
      setUpdateProgress({ active: true, percent: 35, message: "Refreshing market and module data..." });
      const refreshModules = shouldRefreshEtfOptions(activeModule, targetSymbol)
        ? [...backgroundRefreshModules, "etf_options"]
        : backgroundRefreshModules;
      const refreshTasks = [
        { id: "market", task: refreshSecurity(targetSymbol, false) },
        ...refreshModules.map((moduleId) => ({ id: moduleId, task: refreshModule(moduleId, targetSymbol) })),
      ];
      const refreshResults = await Promise.allSettled(refreshTasks.map((entry) => entry.task));
      refreshResults.forEach((result, index) => {
        if (result.status === "rejected") {
          failures.push(refreshTasks[index].id);
        }
      });
      setUpdateProgress({ active: true, percent: 78, message: "Updating cached snapshots..." });
      let previousSignature = await readBackSecurityContext(targetSymbol);
      let stabilized = false;
      for (let attempt = 1; attempt <= 5; attempt += 1) {
        setUpdateProgress({
          active: true,
          percent: Math.min(95, 78 + attempt * 3),
          message: `Waiting for module snapshots (${attempt * 10}s)...`,
        });
        await sleep(10_000);
        const nextSignature = await readBackSecurityContext(targetSymbol);
        if (nextSignature && nextSignature === previousSignature) {
          stabilized = true;
          break;
        }
        previousSignature = nextSignature;
      }
      if (!stabilized) {
        setUpdateProgress({ active: true, percent: 97, message: "Final snapshot readback..." });
        await sleep(10_000);
        await readBackSecurityContext(targetSymbol);
      }
      await fetchSourceHealth()
        .then((response) => setSources(response.rows))
        .catch(() => setSources([]));
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
        if (activeModule === "market") {
          loadSecurity();
        }
        fetchSourceHealth()
          .then((response) => setSources(response.rows))
          .catch(() => setSources([]));
      })
      .catch((error: unknown) => setModuleError(errorMessage(error)))
      .finally(() => setModuleRefreshing(false));
  }

  function openRightPanel(panel: "settings" | "ai") {
    setRightPanel(panel);
    setRightPanelOpen(true);
  }

  function toggleRightPanelOpen() {
    setRightPanelOpen((open) => {
      if (open) {
        setAiAnalyst((current) => ({ ...current, apiKey: "" }));
        return false;
      }
      setRightPanel((panel) => panel ?? "ai");
      return true;
    });
  }

  function updateAiSettings(settings: Pick<AiAnalystState, "provider" | "model" | "apiKey">) {
    setAiAnalyst((current) => ({
      ...current,
      ...settings,
      error: null,
    }));
  }

  async function runAiAnalyst() {
    if (!aiAnalyst.apiKey.trim()) {
      setAiAnalyst((current) => ({ ...current, error: "API key is required for this one-time request." }));
      openRightPanel("settings");
      return;
    }
    const scope = aiAnalyst.scope;
    const moduleId = scope === "module" ? aiAnalyst.moduleId || activeModule : null;
    const requiresSymbol = scope === "security_full" || scope === "all_modules";
    if (requiresSymbol && !selectedSymbol) {
      setAiAnalyst((current) => ({ ...current, error: "Select a symbol before running this analysis scope." }));
      return;
    }
    setAiAnalyst((current) => ({ ...current, loading: true, error: null, result: null }));
    try {
      if (aiAnalyst.includeLatestRefresh) {
        await refreshForAiScope(scope, moduleId);
      }
      const pageContent = collectAnalysisContent(scope, moduleId);
      const screenshotBase64 = await captureWorkspaceScreenshot();
      const result = await generateAiAnalysis({
        provider: aiAnalyst.provider,
        api_key: aiAnalyst.apiKey,
        model: aiAnalyst.model,
        scope,
        symbol: selectedSymbol,
        module_id: moduleId,
        include_latest_refresh: aiAnalyst.includeLatestRefresh,
        page_content: pageContent,
        screenshot_base64: screenshotBase64,
        period: chartPeriod,
      });
      setAiAnalyst((current) => ({ ...current, loading: false, result, error: null }));
      openRightPanel("ai");
    } catch (error: unknown) {
      setAiAnalyst((current) => ({ ...current, loading: false, error: errorMessage(error) }));
    }
  }

  async function refreshForAiScope(scope: AiAnalysisScope, moduleId: string | null) {
    if (scope === "module" && moduleId) {
      await refreshModule(moduleId, selectedSymbol);
      if (selectedSymbol) {
        await readBackSecurityContext(selectedSymbol);
      }
      return;
    }
    if (selectedSymbol && (scope === "security_full" || scope === "all_modules" || activeView === "security")) {
      await runFullRefresh(selectedSymbol);
    }
  }

  function collectAnalysisContent(scope: AiAnalysisScope, moduleId: string | null) {
    const root = workspaceBodyRef.current;
    return {
      scope,
      active_view: activeView,
      active_module: activeModule,
      requested_module: moduleId,
      selected_symbol: selectedSymbol,
      chart_period: chartPeriod,
      visible_text: root?.innerText.slice(0, 60_000) ?? "",
      visible_tables: collectVisibleTables(root),
      visible_links: collectVisibleLinks(root),
      security: {
        overview,
        chart: chart ? { ...chart, rows: chart.rows.slice(-500) } : null,
        boards,
      },
      current_module_data: activeView === "module" ? moduleData : null,
      module_cache_keys: Object.keys(moduleDataCacheRef.current),
    };
  }

  async function captureWorkspaceScreenshot(): Promise<string | null> {
    const root = workspaceBodyRef.current;
    if (!root) {
      return null;
    }
    return captureElementScreenshotBase64(root);
  }

  function copyAiReport() {
    if (aiAnalyst.result) {
      void navigator.clipboard.writeText(aiAnalyst.result.report_text);
    }
  }

  function printAiReport() {
    if (!aiAnalyst.result) {
      return;
    }
    const printWindow = window.open("", "_blank", "noopener,noreferrer,width=980,height=1200");
    if (!printWindow) {
      setAiAnalyst((current) => ({ ...current, error: "Browser blocked the print window." }));
      return;
    }
    printWindow.document.write(standaloneAiReportHtml(aiAnalyst.result.report_html));
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
  }

  function downloadAiReport() {
    if (!aiAnalyst.result) {
      return;
    }
    const blob = new Blob([standaloneAiReportHtml(aiAnalyst.result.report_html)], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${selectedSymbol ?? "current-page"}-ai-report.html`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function printWorkspace() {
    document.body.dataset.printMode = "workspace";
    window.print();
    window.setTimeout(() => {
      delete document.body.dataset.printMode;
    }, 500);
  }

  const darkModuleActive = activeView === "module";
  const darkWorkspaceActive = activeView === "security" || darkModuleActive;
  const shellClass = [
    "app-shell",
    dashboardCollapsed ? "dashboard-collapsed" : "",
    rightPanelOpen ? "right-panel-open" : "",
  ].filter(Boolean).join(" ");

  return (
    <div className={shellClass}>
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
        collapsed={dashboardCollapsed}
        onToggleCollapsed={() => setDashboardCollapsed((collapsed) => !collapsed)}
      />
      <main className={darkWorkspaceActive ? "workspace workspace-chart-only" : "workspace"}>
        {!darkWorkspaceActive && (
          <TopBar
            query={query}
            searchResults={searchResults}
            isSearching={isSearching}
            onQueryChange={setQuery}
            onSelectSymbol={handleSelectSymbol}
          />
        )}
        <div className="workspace-body" ref={workspaceBodyRef}>
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
              onPrintSecurity={printWorkspace}
              marketRefreshing={marketRefreshing}
              searchQuery={query}
              searchResults={searchResults}
              isSearching={isSearching}
              onSearchQueryChange={setQuery}
              onSelectSymbol={(symbol) => handleSelectSymbol(symbol)}
              onOpenModuleSnapshot={openModuleSnapshot}
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
      <AiRightRail
        open={rightPanelOpen}
        activePanel={rightPanel}
        settings={{ provider: aiAnalyst.provider, model: aiAnalyst.model, apiKey: aiAnalyst.apiKey }}
        modules={modules}
        activeModule={activeModule}
        scope={aiAnalyst.scope}
        moduleId={aiAnalyst.moduleId}
        includeLatestRefresh={aiAnalyst.includeLatestRefresh}
        loading={aiAnalyst.loading}
        error={aiAnalyst.error}
        result={aiAnalyst.result}
        onToggleOpen={toggleRightPanelOpen}
        onSelectPanel={openRightPanel}
        onSettingsChange={updateAiSettings}
        onScopeChange={(scope) => setAiAnalyst((current) => ({ ...current, scope, error: null }))}
        onModuleIdChange={(moduleId) => setAiAnalyst((current) => ({ ...current, moduleId }))}
        onIncludeLatestRefreshChange={(enabled) => setAiAnalyst((current) => ({ ...current, includeLatestRefresh: enabled }))}
        onRunAnalysis={runAiAnalyst}
        onCopyReport={copyAiReport}
        onPrintReport={printAiReport}
        onDownloadReport={downloadAiReport}
      />
    </div>
  );
}
