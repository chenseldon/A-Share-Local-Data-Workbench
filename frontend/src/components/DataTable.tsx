import type { DataRow } from "../types";

interface Column {
  key: string;
  label: string;
}

interface DataTableProps {
  rows: ReadonlyArray<object>;
  columns?: Column[];
  emptyLabel?: string;
}

function formatCell(value: unknown): string {
  if (value === null) {
    return "-";
  }
  if (value === undefined) {
    return "-";
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 4 });
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value);
}

function inferColumns(rows: ReadonlyArray<object>): Column[] {
  const first = rows[0];
  if (!first) {
    return [];
  }
  return Object.keys(first).map((key) => ({
    key,
    label: key.replaceAll("_", " ")
  }));
}

export function DataTable({ rows, columns, emptyLabel = "No local data yet." }: DataTableProps) {
  const resolvedColumns = columns ?? inferColumns(rows);

  if (rows.length === 0) {
    return <div className="table-empty">{emptyLabel}</div>;
  }

  return (
    <div className="table-frame">
      <table>
        <thead>
          <tr>
            {resolvedColumns.map((column) => (
              <th key={column.key}>{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${String((row as DataRow).id ?? (row as DataRow).symbol ?? "row")}-${index}`}>
              {resolvedColumns.map((column) => (
                <td key={column.key}>{formatCell((row as DataRow)[column.key] ?? null)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
