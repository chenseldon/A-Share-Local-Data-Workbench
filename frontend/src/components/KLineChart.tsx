import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { BarChart3, Crosshair, MousePointer2, Ruler, Settings2, TrendingUp } from "lucide-react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  createChart
} from "lightweight-charts";
import type { BoardMappingResponse, ChartBar, MarketQuote, Security } from "../types";

interface KLineChartProps {
  rows: ChartBar[];
  quote: MarketQuote | null;
  security?: Security | null;
  boards?: BoardMappingResponse | null;
  boardError?: string | null;
  enabledIndicators: string[];
  onIndicatorsChange: (indicators: string[]) => void;
  indicatorStatus?: string;
  indicatorError?: string | null;
  loading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
  refreshing?: boolean;
}

const indicatorOptions = [
  { id: "ma", label: "MA5/10/20", color: "#f59e0b" },
  { id: "macd", label: "MACD", color: "#f97316" },
  { id: "kdj", label: "KDJ", color: "#22c55e" },
  { id: "rsi", label: "RSI", color: "#e879f9" },
  { id: "boll", label: "BOLL", color: "#94a3b8" },
  { id: "volume", label: "Volume", color: "rgba(96, 165, 250, 0.42)" },
] as const;

function sourceLabel(rows: ChartBar[], quote: MarketQuote | null): string {
  if (rows.length > 0) {
    return "Local K-line data loaded";
  }
  if (quote) {
    return "Latest cached quote loaded";
  }
  return "No cached free-stockdb K-line source";
}

export function KLineChart({
  rows,
  quote,
  security,
  boards,
  boardError,
  enabledIndicators,
  onIndicatorsChange,
  indicatorStatus,
  indicatorError,
  loading,
  error,
  onRefresh,
  refreshing
}: KLineChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [indicatorMenuOpen, setIndicatorMenuOpen] = useState(false);
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
    return enabledIndicators.includes(name);
  }

  function toggleIndicator(name: string) {
    const next = indicatorEnabled(name)
      ? enabledIndicators.filter((item) => item !== name)
      : [...enabledIndicators, name];
    onIndicatorsChange(next);
  }

  function lineData(field: keyof ChartBar) {
    return chartRows
      .filter((row) => typeof row[field] === "number")
      .map((row) => ({ time: row.trade_date, value: row[field] as number }));
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

    if (indicatorEnabled("volume")) {
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

    if (indicatorEnabled("ma")) {
      const ma5 = chart.addSeries(LineSeries, { color: "#f59e0b", lineWidth: 1, priceLineVisible: false });
      ma5.setData(lineData("ma5"));
      const ma10 = chart.addSeries(LineSeries, { color: "#38bdf8", lineWidth: 1, priceLineVisible: false });
      ma10.setData(lineData("ma10"));
      const ma20 = chart.addSeries(LineSeries, { color: "#c084fc", lineWidth: 1, priceLineVisible: false });
      ma20.setData(lineData("ma20"));
    }

    if (indicatorEnabled("boll")) {
      const upper = chart.addSeries(LineSeries, { color: "#94a3b8", lineWidth: 1, priceLineVisible: false });
      upper.setData(lineData("upper"));
      const mid = chart.addSeries(LineSeries, { color: "#cbd5e1", lineWidth: 1, priceLineVisible: false });
      mid.setData(lineData("mid"));
      const lower = chart.addSeries(LineSeries, { color: "#94a3b8", lineWidth: 1, priceLineVisible: false });
      lower.setData(lineData("lower"));
    }

    if (indicatorEnabled("macd")) {
      const macdScale = "macd";
      const dif = chart.addSeries(LineSeries, { color: "#38bdf8", lineWidth: 1, priceLineVisible: false, priceScaleId: macdScale });
      dif.setData(lineData("dif"));
      const dea = chart.addSeries(LineSeries, { color: "#f97316", lineWidth: 1, priceLineVisible: false, priceScaleId: macdScale });
      dea.setData(lineData("dea"));
      const macd = chart.addSeries(HistogramSeries, { priceScaleId: macdScale, color: "rgba(249, 115, 22, 0.45)" });
      chart.priceScale(macdScale).applyOptions({ scaleMargins: { top: 0.68, bottom: 0.16 } });
      macd.setData(lineData("macd").map((item) => ({ ...item, color: item.value >= 0 ? "rgba(239, 68, 68, 0.45)" : "rgba(34, 197, 94, 0.45)" })));
    }

    if (indicatorEnabled("kdj")) {
      const kdjScale = "oscillator";
      chart.priceScale(kdjScale).applyOptions({ scaleMargins: { top: 0.62, bottom: 0.08 } });
      const k = chart.addSeries(LineSeries, { color: "#22c55e", lineWidth: 1, priceLineVisible: false, priceScaleId: kdjScale });
      k.setData(lineData("k"));
      const d = chart.addSeries(LineSeries, { color: "#38bdf8", lineWidth: 1, priceLineVisible: false, priceScaleId: kdjScale });
      d.setData(lineData("d"));
      const j = chart.addSeries(LineSeries, { color: "#f59e0b", lineWidth: 1, priceLineVisible: false, priceScaleId: kdjScale });
      j.setData(lineData("j"));
    }

    if (indicatorEnabled("rsi")) {
      const rsiScale = "oscillator";
      chart.priceScale(rsiScale).applyOptions({ scaleMargins: { top: 0.62, bottom: 0.08 } });
      const rsi = chart.addSeries(LineSeries, { color: "#e879f9", lineWidth: 1, priceLineVisible: false, priceScaleId: rsiScale });
      rsi.setData(lineData("rsi"));
    }

    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [chartRows, enabledIndicators]);

  const primarySector = boards?.sw_l1[0] ?? security?.sector ?? "No sector";
  const conceptPreview = boards?.concepts.slice(0, 3) ?? [];

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
              <span>{primarySector}</span>
              {conceptPreview.map((concept) => (
                <span key={concept}>{concept}</span>
              ))}
              {boardError && <span>Board mapping failed</span>}
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
                {indicatorOptions.map((indicator) => (
                  <label key={indicator.id}>
                    <input
                      type="checkbox"
                      checked={indicatorEnabled(indicator.id)}
                      onChange={() => toggleIndicator(indicator.id)}
                    />
                    <span>{indicator.label}</span>
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
            {indicatorEnabled("ma") && <span className="legend-item" style={{ "--legend-color": "#f59e0b" } as CSSProperties}>MA5/10/20</span>}
            {indicatorEnabled("boll") && <span className="legend-item" style={{ "--legend-color": "#94a3b8" } as CSSProperties}>BOLL</span>}
            {indicatorEnabled("macd") && <span className="legend-item" style={{ "--legend-color": "#f97316" } as CSSProperties}>MACD</span>}
            {indicatorEnabled("kdj") && <span className="legend-item" style={{ "--legend-color": "#22c55e" } as CSSProperties}>KDJ</span>}
            {indicatorEnabled("rsi") && <span className="legend-item" style={{ "--legend-color": "#e879f9" } as CSSProperties}>RSI</span>}
            {indicatorEnabled("volume") && <span className="legend-item" style={{ "--legend-color": "rgba(96, 165, 250, 0.42)" } as CSSProperties}>Volume</span>}
            {indicatorStatus === "failed" && <span className="chart-warning">{indicatorError ?? "Indicator calculation failed"}</span>}
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
