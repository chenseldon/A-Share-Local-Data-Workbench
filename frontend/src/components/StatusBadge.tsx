import type { FreshnessState } from "../types";

interface StatusBadgeProps {
  status: FreshnessState | "configured" | "prepared" | "not_found" | "success" | string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const normalized = status.toLowerCase().replaceAll("_", "-");
  return <span className={`status-badge status-${normalized}`}>{status.replaceAll("_", " ")}</span>;
}
