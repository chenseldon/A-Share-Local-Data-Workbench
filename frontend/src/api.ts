import type {
  AiAnalysisRequest,
  AiAnalysisResponse,
  BoardMappingResponse,
  ChartResponse,
  ConnectorCapability,
  DataJob,
  ModuleDataResponse,
  ModuleDefinition,
  QuoteResponse,
  SecurityUniverseStatus,
  RefreshResponse,
  RowsResponse,
  SearchResponse,
  SecurityOverview,
  SourceHealth
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const GET_TIMEOUT_MS = 25_000;
export type ChartPeriod = "1m" | "5m" | "15m" | "30m" | "60m" | "1d" | "1w" | "1M";

async function apiGet<T>(path: string): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), GET_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, { signal: controller.signal });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(body || `Request failed: ${response.status}`);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`Request timed out after ${GET_TIMEOUT_MS / 1000}s: ${path}`);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

async function apiPost<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: "POST" });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const responseBody = await response.text();
    throw new Error(responseBody || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchModules(): Promise<ModuleDefinition[]> {
  return apiGet<ModuleDefinition[]>("/api/modules");
}

export function fetchHealth(): Promise<{ status: string; database: string }> {
  return apiGet<{ status: string; database: string }>("/api/health");
}

export function searchSecurities(query: string): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query, limit: "5" });
  return apiGet<SearchResponse>(`/api/securities/search?${params.toString()}`);
}

export function fetchSecurityUniverseStatus(): Promise<SecurityUniverseStatus> {
  return apiGet<SecurityUniverseStatus>("/api/securities/universe/status");
}

export function refreshSecurityUniverse(): Promise<RefreshResponse> {
  return apiPost<RefreshResponse>("/api/securities/universe/refresh");
}

export function fetchSecurityOverview(symbol: string): Promise<SecurityOverview> {
  return apiGet<SecurityOverview>(`/api/security/${encodeURIComponent(symbol)}/overview`);
}

export function refreshSecurity(symbol: string, includeModules = true): Promise<RefreshResponse> {
  const params = new URLSearchParams({ include_modules: includeModules ? "true" : "false" });
  return apiPost<RefreshResponse>(`/api/security/${encodeURIComponent(symbol)}/refresh?${params.toString()}`);
}

export function refreshModule(moduleId: string, symbol: string | null): Promise<RefreshResponse> {
  const params = new URLSearchParams();
  if (symbol) {
    params.set("symbol", symbol);
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiPost<RefreshResponse>(`/api/modules/${encodeURIComponent(moduleId)}/refresh${suffix}`);
}

export function fetchConnectorCapabilities(): Promise<RowsResponse<ConnectorCapability>> {
  return apiGet<RowsResponse<ConnectorCapability>>("/api/connectors/capabilities");
}

export function fetchSecurityQuote(symbol: string): Promise<QuoteResponse> {
  return apiGet<QuoteResponse>(`/api/security/${encodeURIComponent(symbol)}/quote`);
}

export function fetchSecurityChart(
  symbol: string,
  indicators: string[] = ["ma"],
  period: ChartPeriod = "1d"
): Promise<ChartResponse> {
  const params = new URLSearchParams({ period, adjustment: "auto", limit: "2000" });
  if (indicators.length > 0) {
    params.set("indicators", indicators.join(","));
  }
  return apiGet<ChartResponse>(`/api/security/${encodeURIComponent(symbol)}/chart?${params.toString()}`);
}

export function fetchSecurityBoards(symbol: string): Promise<BoardMappingResponse> {
  return apiGet<BoardMappingResponse>(`/api/security/${encodeURIComponent(symbol)}/boards`);
}

export function generateAiAnalysis(request: AiAnalysisRequest): Promise<AiAnalysisResponse> {
  return apiPostJson<AiAnalysisResponse>("/api/ai/analyze", request);
}

export function fetchModuleData(moduleId: string, symbol: string | null): Promise<ModuleDataResponse> {
  const params = new URLSearchParams({ limit: "100" });
  if (symbol) {
    params.set("symbol", symbol);
  }
  return apiGet<ModuleDataResponse>(`/api/modules/${moduleId}/data?${params.toString()}`);
}

export function fetchJobs(): Promise<RowsResponse<DataJob>> {
  return apiGet<RowsResponse<DataJob>>("/api/jobs");
}

export function fetchSourceHealth(): Promise<RowsResponse<SourceHealth>> {
  return apiGet<RowsResponse<SourceHealth>>("/api/data-sources/status");
}
