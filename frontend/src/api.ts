import type {
  DataJob,
  ModuleDataResponse,
  ModuleDefinition,
  RowsResponse,
  SearchResponse,
  SecurityOverview,
  SourceHealth
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchModules(): Promise<ModuleDefinition[]> {
  return apiGet<ModuleDefinition[]>("/api/modules");
}

export function searchSecurities(query: string): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query, limit: "12" });
  return apiGet<SearchResponse>(`/api/securities/search?${params.toString()}`);
}

export function fetchSecurityOverview(symbol: string): Promise<SecurityOverview> {
  return apiGet<SecurityOverview>(`/api/security/${encodeURIComponent(symbol)}/overview`);
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
