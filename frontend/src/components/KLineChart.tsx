import { useEffect, useMemo, useRef, useState } from "react";
import { BarChart3, Crosshair, MousePointer2, Ruler, Settings2, TrendingUp } from "lucide-react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  createChart
} from "lightweight-charts";
import type { ChartBar, MarketQuote, Security } from "../types";

interface KLineChartProps {
  rows: ChartBar[];
  quote: MarketQuote | null;
  security?: Security | null;
  loading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
  refreshing?: boolean;
}

const indicatorNames = ["MA5", "MA10", "MA20", "Volume"] as const;

function sourceLabel(rows: ChartBar[], quote: MarketQuote | null): string {
  if (rows.length > 0) {
    return "Local K-line data loaded";
  }
  if (quote) {
    return "Latest cached quote loaded";
  }
  return "No cached free-stockdb K-line source";
}

export function KLineChart({ rows, quote, security, loading, error, onRefresh, refreshing }: KLineChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [indicatorMenuOpen, setIndicatorMenuOpen] = useState(false);
  const [enabledIndicators, setEnabledIndicators] = useState<Set<string>>(
    () => new Set(["MA5", "MA10", "MA20", "Volume"])
  );
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

  function indicatorEnabled(name: string): boolean {
    return enabledIndicators.has(name);
  }

  function toggleIndicator(name: string) {
    setEnabledIndicators((current) => {
      const next = new Set(current);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }

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

    if (indicatorEnabled("Volume")) {
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
    }

    if (indicatorEnabled("MA5")) {
      const ma5 = chart.addSeries(LineSeries, { color: "#f59e0b", lineWidth: 1, priceLineVisible: false });
      ma5.setData(chartRows.filter((row) => row.ma5 !== null).map((row) => ({ time: row.trade_date, value: row.ma5 ?? 0 })));
    }
    if (indicatorEnabled("MA10")) {
      const ma10 = chart.addSeries(LineSeries, { color: "#38bdf8", lineWidth: 1, priceLineVisible: false });
      ma10.setData(chartRows.filter((row) => row.ma10 !== null).map((row) => ({ time: row.trade_date, value: row.ma10 ?? 0 })));
    }
    if (indicatorEnabled("MA20")) {
      const ma20 = chart.addSeries(LineSeries, { color: "#c084fc", lineWidth: 1, priceLineVisible: false });
      ma20.setData(chartRows.filter((row) => row.ma20 !== null).map((row) => ({ time: row.trade_date, value: row.ma20 ?? 0 })));
    }

    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [chartRows, enabledIndicators]);

  return (
    <section className="panel chart-panel">
      <div className="section-heading chart-heading">
        <div className="chart-title-block">
          <span className="chart-kicker">K-Line</span>
          <div className="chart-security-title">
            <h2>{security?.symbol ?? "No symbol selected"}</h2>
            <span>{security?.name ?? sourceLabel(rows, quote)}</span>
          </div>
          {security && (
            <div className="chart-security-meta">
              <span>{security.exchange}</span>
              <span>{security.asset_type}</span>
              <span>{security.sector ?? "No sector"}</span>
            </div>
          )}
        </div>
        <div className="chart-actions">
          <div className="indicator-menu-wrap">
            <button
              className="secondary-button"
              type="button"
              onClick={() => setIndicatorMenuOpen((open) => !open)}
              aria-expanded={indicatorMenuOpen}
            >
              <Settings2 aria-hidden="true" size={15} />
              Indicators
            </button>
            {indicatorMenuOpen && (
              <div className="indicator-menu">
                {indicatorNames.map((indicator) => (
                  <label key={indicator}>
                    <input
                      type="checkbox"
                      checked={enabledIndicators.has(indicator)}
                      onChange={() => toggleIndicator(indicator)}
                    />
                    <span>{indicator}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
          {onRefresh && (
            <button className="secondary-button" onClick={onRefresh} disabled={refreshing}>
              {refreshing ? "Refreshing" : "Refresh market"}
            </button>
          )}
        </div>
      </div>
      <div className="trading-chart-shell">
        <div className="chart-toolrail" aria-label="Chart tools">
          <button type="button" title="Pointer"><MousePointer2 aria-hidden="true" size={17} /></button>
          <button type="button" title="Crosshair"><Crosshair aria-hidden="true" size={17} /></button>
          <button type="button" title="Trend line"><TrendingUp aria-hidden="true" size={17} /></button>
          <button type="button" title="Measure"><Ruler aria-hidden="true" size={17} /></button>
          <button type="button" title="Bars"><BarChart3 aria-hidden="true" size={17} /></button>
        </div>
        <div className="chart-main">
          <div className="chart-legend" aria-label="Chart legend">
            {indicatorEnabled("MA5") && <span className="legend-item legend-ma5">MA5</span>}
            {indicatorEnabled("MA10") && <span className="legend-item legend-ma10">MA10</span>}
            {indicatorEnabled("MA20") && <span className="legend-item legend-ma20">MA20</span>}
            {indicatorEnabled("Volume") && <span>Volume</span>}
          </div>
          {loading && <div className="chart-empty">Loading free-stockdb K-line...</div>}
          {error && <div className="chart-empty chart-error">{error}</div>}
          {!loading && !error && chartRows.length === 0 && (
            <div className="chart-empty">No free-stockdb K-line data yet. Use Refresh market after stockdb.exe is running.</div>
          )}
          {!loading && !error && chartRows.length > 0 && <div ref={containerRef} className="kline-canvas" />}
        </div>
      </div>
    </section>
  );
}
