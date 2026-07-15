import { useEffect, useMemo, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  createChart
} from "lightweight-charts";
import type { ChartBar, FreshnessState, MarketQuote } from "../types";
import { StatusBadge } from "./StatusBadge";

interface KLineChartProps {
  rows: ChartBar[];
  quote: MarketQuote | null;
  status: FreshnessState;
  loading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
  refreshing?: boolean;
}

function sourceLabel(rows: ChartBar[], quote: MarketQuote | null): string {
  if (quote) {
    return `${quote.source} · ${quote.fetched_at}`;
  }
  const latest = rows.at(-1);
  if (latest) {
    return `${latest.source} · ${latest.fetched_at}`;
  }
  return "No cached market source";
}

export function KLineChart({ rows, quote, status, loading, error, onRefresh, refreshing }: KLineChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRows = useMemo(
    () =>
      rows.filter(
        (row) =>
          row.open !== null &&
          row.high !== null &&
          row.low !== null &&
          row.close !== null &&
          row.trade_date
      ),
    [rows]
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container || chartRows.length === 0) {
      return;
    }

    const chart = createChart(container, {
      autoSize: true,
      height: 430,
      layout: {
        background: { type: ColorType.Solid, color: "#0f1720" },
        textColor: "#9fb0bd"
      },
      grid: {
        vertLines: { color: "rgba(159, 176, 189, 0.12)" },
        horzLines: { color: "rgba(159, 176, 189, 0.12)" }
      },
      rightPriceScale: { borderColor: "rgba(159, 176, 189, 0.2)" },
      timeScale: { borderColor: "rgba(159, 176, 189, 0.2)" },
      crosshair: { mode: 1 }
    });

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#ef4444",
      downColor: "#22c55e",
      borderUpColor: "#ef4444",
      borderDownColor: "#22c55e",
      wickUpColor: "#ef4444",
      wickDownColor: "#22c55e"
    });
    candles.setData(
      chartRows.map((row) => ({
        time: row.trade_date,
        open: row.open ?? 0,
        high: row.high ?? 0,
        low: row.low ?? 0,
        close: row.close ?? 0
      }))
    );

    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "",
      color: "rgba(96, 165, 250, 0.35)"
    });
    volume.priceScale().applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 }
    });
    volume.setData(
      chartRows.map((row) => ({
        time: row.trade_date,
        value: row.volume ?? 0,
        color: (row.close ?? 0) >= (row.open ?? 0) ? "rgba(239, 68, 68, 0.38)" : "rgba(34, 197, 94, 0.38)"
      }))
    );

    const ma5 = chart.addSeries(LineSeries, { color: "#f59e0b", lineWidth: 1, priceLineVisible: false });
    const ma10 = chart.addSeries(LineSeries, { color: "#38bdf8", lineWidth: 1, priceLineVisible: false });
    const ma20 = chart.addSeries(LineSeries, { color: "#c084fc", lineWidth: 1, priceLineVisible: false });
    ma5.setData(chartRows.filter((row) => row.ma5 !== null).map((row) => ({ time: row.trade_date, value: row.ma5 ?? 0 })));
    ma10.setData(chartRows.filter((row) => row.ma10 !== null).map((row) => ({ time: row.trade_date, value: row.ma10 ?? 0 })));
    ma20.setData(chartRows.filter((row) => row.ma20 !== null).map((row) => ({ time: row.trade_date, value: row.ma20 ?? 0 })));

    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [chartRows]);

  return (
    <section className="panel chart-panel">
      <div className="section-heading chart-heading">
        <div>
          <h2>K-Line</h2>
          <p>{sourceLabel(rows, quote)} · adjustment none · public-source fetch is not trading-grade real time.</p>
        </div>
        <div className="chart-actions">
          <StatusBadge status={status} />
          {onRefresh && (
            <button className="secondary-button" onClick={onRefresh} disabled={refreshing}>
              {refreshing ? "Refreshing" : "Refresh market"}
            </button>
          )}
        </div>
      </div>
      <div className="chart-legend" aria-label="Chart legend">
        <span className="legend-item legend-ma5">MA5</span>
        <span className="legend-item legend-ma10">MA10</span>
        <span className="legend-item legend-ma20">MA20</span>
        <span>Volume</span>
      </div>
      {loading && <div className="chart-empty">Loading cached K-line...</div>}
      {error && <div className="chart-empty chart-error">{error}</div>}
      {!loading && !error && chartRows.length === 0 && (
        <div className="chart-empty">No local K-line data yet. Use Refresh market to fetch and cache public-source data.</div>
      )}
      {!loading && !error && chartRows.length > 0 && <div ref={containerRef} className="kline-canvas" />}
    </section>
  );
}
