import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import {
  BarChart3,
  ChevronUp,
  Crosshair,
  Magnet,
  MousePointer2,
  Pencil,
  Plus,
  Ruler,
  Settings2,
  TextCursorInput,
  TrendingUp,
  ZoomIn
} from "lucide-react";
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

type IndicatorPlacement = "overlay" | "pane" | "built_in";

interface IndicatorOption {
  id: string;
  label: string;
  placement: IndicatorPlacement;
  fields: string[];
  color: string;
  description: string;
}

const indicatorOptions: IndicatorOption[] = [
  { id: "ma", label: "MA", placement: "overlay", fields: ["ma5", "ma10", "ma20"], color: "#f59e0b", description: "Moving average" },
  { id: "ema", label: "EMA", placement: "overlay", fields: ["ema5", "ema10", "ema20", "ema"], color: "#38bdf8", description: "Exponential moving average" },
  { id: "boll", label: "BOLL", placement: "overlay", fields: ["upper", "mid", "lower"], color: "#94a3b8", description: "Bollinger bands" },
  { id: "expma", label: "EXPMA", placement: "overlay", fields: ["exp1", "exp2"], color: "#a78bfa", description: "EXP moving average" },
  { id: "bbi", label: "BBI", placement: "overlay", fields: ["bbi"], color: "#22d3ee", description: "Bull and bear index" },
  { id: "taq", label: "TAQ", placement: "overlay", fields: ["taq_up", "taq_mid", "taq_down"], color: "#cbd5e1", description: "Trend channel" },
  { id: "ktn", label: "KTN", placement: "overlay", fields: ["ktn_up", "ktn_mid", "ktn_down"], color: "#fb7185", description: "Keltner channel" },
  { id: "macd", label: "MACD", placement: "pane", fields: ["dif", "dea", "macd"], color: "#f97316", description: "Trend momentum" },
  { id: "rsi", label: "RSI", placement: "pane", fields: ["rsi", "rsi6", "rsi12", "rsi24"], color: "#e879f9", description: "Relative strength" },
  { id: "kdj", label: "KDJ", placement: "pane", fields: ["k", "d", "j"], color: "#22c55e", description: "Stochastic oscillator" },
  { id: "wr", label: "WR", placement: "pane", fields: ["wr", "wr1"], color: "#60a5fa", description: "Williams %R" },
  { id: "bias", label: "BIAS", placement: "pane", fields: ["bias1", "bias2", "bias3"], color: "#facc15", description: "Price deviation" },
  { id: "psy", label: "PSY", placement: "pane", fields: ["psy", "psyma"], color: "#34d399", description: "Psychological line" },
  { id: "cci", label: "CCI", placement: "pane", fields: ["cci"], color: "#fb7185", description: "Commodity channel" },
  { id: "atr", label: "ATR", placement: "pane", fields: ["atr"], color: "#38bdf8", description: "Average true range" },
  { id: "dmi", label: "DMI", placement: "pane", fields: ["pdi", "mdi", "adx", "adxr"], color: "#f97316", description: "Directional movement" },
  { id: "trix", label: "TRIX", placement: "pane", fields: ["trix", "trma"], color: "#a78bfa", description: "Triple exponential average" },
  { id: "vr", label: "VR", placement: "pane", fields: ["vr"], color: "#60a5fa", description: "Volume ratio" },
  { id: "cr", label: "CR", placement: "pane", fields: ["cr"], color: "#f59e0b", description: "Energy index" },
  { id: "emv", label: "EMV", placement: "pane", fields: ["emv", "maemv"], color: "#2dd4bf", description: "Ease of movement" },
  { id: "dpo", label: "DPO", placement: "pane", fields: ["dpo", "madpo"], color: "#f472b6", description: "Detrended oscillator" },
  { id: "brar", label: "BRAR", placement: "pane", fields: ["ar", "br"], color: "#84cc16", description: "Popularity index" },
  { id: "dfma", label: "DFMA", placement: "pane", fields: ["dfma_dif", "dfma_difma"], color: "#38bdf8", description: "Difference MA" },
  { id: "mtm", label: "MTM", placement: "pane", fields: ["mtm", "mtmma"], color: "#f97316", description: "Momentum" },
  { id: "mass", label: "MASS", placement: "pane", fields: ["mass", "ma"], color: "#a3e635", description: "Mass index" },
  { id: "roc", label: "ROC", placement: "pane", fields: ["roc", "maroc"], color: "#22c55e", description: "Rate of change" },
  { id: "obv", label: "OBV", placement: "pane", fields: ["obv", "maobv"], color: "#60a5fa", description: "On-balance volume" },
  { id: "mfi", label: "MFI", placement: "pane", fields: ["mfi"], color: "#e879f9", description: "Money flow index" },
  { id: "asi", label: "ASI", placement: "pane", fields: ["asi", "asit"], color: "#f59e0b", description: "Accumulation swing" },
  { id: "xsii", label: "XSII", placement: "pane", fields: ["td1", "td2", "td3", "td4"], color: "#c084fc", description: "Xue-Si II" },
  { id: "sma", label: "SMA", placement: "pane", fields: ["sma5", "sma10", "sma20", "sma"], color: "#14b8a6", description: "Simple moving average" },
  { id: "wma", label: "WMA", placement: "pane", fields: ["wma5", "wma10", "wma20", "wma"], color: "#818cf8", description: "Weighted moving average" },
  { id: "dma", label: "DMA", placement: "pane", fields: ["dma10", "dma"], color: "#fb923c", description: "Difference average" },
  { id: "std", label: "STD", placement: "pane", fields: ["std20", "std"], color: "#94a3b8", description: "Standard deviation" },
  { id: "sum", label: "SUM", placement: "pane", fields: ["sum20", "sum"], color: "#facc15", description: "Rolling sum" },
  { id: "hhv", label: "HHV", placement: "pane", fields: ["hhv20", "hhv"], color: "#ef4444", description: "Highest high value" },
  { id: "llv", label: "LLV", placement: "pane", fields: ["llv20", "llv"], color: "#22c55e", description: "Lowest low value" },
  { id: "ref", label: "REF", placement: "pane", fields: ["ref1", "ref"], color: "#38bdf8", description: "Reference value" },
  { id: "volume", label: "Volume", placement: "built_in", fields: ["volume"], color: "rgba(96, 165, 250, 0.42)", description: "Volume bars" }
];

const toolButtons = [
  { title: "Cursor", icon: MousePointer2 },
  { title: "Crosshair", icon: Crosshair },
  { title: "Trend line", icon: TrendingUp },
  { title: "Brush", icon: Pencil },
  { title: "Text note", icon: TextCursorInput },
  { title: "Measure", icon: Ruler },
  { title: "Magnet", icon: Magnet },
  { title: "Zoom", icon: ZoomIn },
  { title: "Bars", icon: BarChart3 }
];

const lineColors = ["#f59e0b", "#38bdf8", "#c084fc", "#22c55e", "#f97316", "#e879f9", "#60a5fa"];

function sourceLabel(rows: ChartBar[], quote: MarketQuote | null): string {
  if (rows.length > 0) {
    return "Local K-line data loaded";
  }
  if (quote) {
    return "Latest cached quote loaded";
  }
  return "No cached free-stockdb K-line source";
}

function numericValue(row: ChartBar, field: string): number | null {
  const value = row[field];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function firstAvailableFields(rows: ChartBar[], fields: string[]): string[] {
  return fields.filter((field) => rows.some((row) => numericValue(row, field) !== null));
}

function seriesValues(rows: ChartBar[], fields: string[]): number[][] {
  return fields.map((field) => rows.map((row) => numericValue(row, field) ?? Number.NaN));
}

function linePath(values: number[], width: number, height: number, min: number, max: number): string {
  const range = max - min || 1;
  const points = values
    .map((value, index) => {
      if (!Number.isFinite(value)) {
        return null;
      }
      const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter(Boolean);
  return points.length ? `M ${points.join(" L ")}` : "";
}

function IndicatorPane({ indicator, rows }: { indicator: IndicatorOption; rows: ChartBar[] }) {
  const fields = firstAvailableFields(rows, indicator.fields);
  if (fields.length === 0) {
    return (
      <div className="indicator-pane">
        <div className="indicator-pane-title">
          <span>{indicator.label}</span>
          <small>No values returned</small>
        </div>
      </div>
    );
  }

  const width = 960;
  const height = 108;
  const values = seriesValues(rows, fields);
  const flat = values.flat().filter((value) => Number.isFinite(value));
  const min = Math.min(...flat);
  const max = Math.max(...flat);

  return (
    <div className="indicator-pane">
      <div className="indicator-pane-title">
        <span>{indicator.label}</span>
        <small>{fields.join(" / ")}</small>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
        <line x1="0" y1={height / 2} x2={width} y2={height / 2} />
        {fields.map((field, index) => (
          <path
            key={field}
            d={linePath(values[index], width, height, min, max)}
            style={{ stroke: lineColors[index % lineColors.length] }}
          />
        ))}
      </svg>
    </div>
  );
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
  const [legendCollapsed, setLegendCollapsed] = useState(false);
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

  const selectedIndicators = useMemo(
    () => indicatorOptions.filter((indicator) => enabledIndicators.includes(indicator.id)),
    [enabledIndicators]
  );
  const overlayIndicators = selectedIndicators.filter((indicator) => indicator.placement === "overlay");
  const paneIndicators = selectedIndicators.filter((indicator) => indicator.placement === "pane");
  const mainChartHeight = Math.max(430, 700 - paneIndicators.length * 92);

  function indicatorEnabled(name: string): boolean {
    return enabledIndicators.includes(name);
  }

  function toggleIndicator(name: string) {
    const next = indicatorEnabled(name)
      ? enabledIndicators.filter((item) => item !== name)
      : [...enabledIndicators, name];
    onIndicatorsChange(next);
  }

  function lineData(field: string) {
    return chartRows
      .filter((row) => numericValue(row, field) !== null)
      .map((row) => ({ time: row.trade_date, value: numericValue(row, field) ?? 0 }));
  }

  useEffect(() => {
    const container = containerRef.current;
    if (!container || chartRows.length === 0) {
      return;
    }

    const chart = createChart(container, {
      autoSize: true,
      height: mainChartHeight,
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
        scaleMargins: { top: 0.84, bottom: 0 }
      });
      volume.setData(
        chartRows.map((row) => ({
          time: row.trade_date,
          value: row.volume ?? 0,
          color: (row.close ?? 0) >= (row.open ?? 0) ? "rgba(239, 68, 68, 0.38)" : "rgba(34, 197, 94, 0.38)"
        }))
      );
    }

    overlayIndicators.forEach((indicator, indicatorIndex) => {
      const fields = firstAvailableFields(chartRows, indicator.fields);
      fields.forEach((field, fieldIndex) => {
        const series = chart.addSeries(LineSeries, {
          color: lineColors[(indicatorIndex + fieldIndex) % lineColors.length],
          lineWidth: 1,
          priceLineVisible: false
        });
        series.setData(lineData(field));
      });
    });

    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [chartRows, enabledIndicators, mainChartHeight]);

  const primarySector = boards?.sw_l1[0] ?? security?.sector ?? "No sector";
  const conceptPreview = boards?.concepts.slice(0, 3) ?? [];

  return (
    <section className="panel chart-panel">
      <div className="section-heading chart-heading">
        <div className="chart-title-block">
          <div className="chart-security-title">
            <h2>{security?.symbol ?? "No symbol selected"}</h2>
            <strong>{security?.name ?? sourceLabel(rows, quote)}</strong>
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
                <div className="indicator-menu-header">
                  <strong>Indicators</strong>
                  <small>{indicatorOptions.length - 1} free-stockdb SDK indicators</small>
                </div>
                {indicatorOptions.map((indicator) => (
                  <label key={indicator.id}>
                    <input
                      type="checkbox"
                      checked={indicatorEnabled(indicator.id)}
                      onChange={() => toggleIndicator(indicator.id)}
                    />
                    <span>{indicator.label}</span>
                    <small>{indicator.placement === "overlay" ? "Main" : indicator.placement === "pane" ? "Pane" : "Built-in"}</small>
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
          {toolButtons.map((tool) => {
            const Icon = tool.icon;
            return (
              <button type="button" title={tool.title} key={tool.title}>
                <Icon aria-hidden="true" size={17} />
              </button>
            );
          })}
        </div>
        <div className="chart-main">
          <div className={legendCollapsed ? "chart-legend collapsed" : "chart-legend"} aria-label="Chart legend">
            <button
              className="legend-collapse"
              type="button"
              onClick={() => setLegendCollapsed((collapsed) => !collapsed)}
              title={legendCollapsed ? "Show indicators" : "Hide indicators"}
            >
              {legendCollapsed ? <Plus aria-hidden="true" size={14} /> : <ChevronUp aria-hidden="true" size={14} />}
            </button>
            {!legendCollapsed && (
              <>
                {selectedIndicators.map((indicator) => (
                  <span className="legend-item" key={indicator.id} style={{ "--legend-color": indicator.color } as CSSProperties}>
                    {indicator.label}
                  </span>
                ))}
                {indicatorStatus === "failed" && <span className="chart-warning">{indicatorError ?? "Indicator calculation failed"}</span>}
              </>
            )}
          </div>
          {loading && <div className="chart-empty">Loading free-stockdb K-line...</div>}
          {error && <div className="chart-empty chart-error">{error}</div>}
          {!loading && !error && chartRows.length === 0 && (
            <div className="chart-empty">No free-stockdb K-line data yet. Use Refresh market after stockdb.exe is running.</div>
          )}
          {!loading && !error && chartRows.length > 0 && (
            <>
              <div ref={containerRef} className="kline-canvas" />
              <div className="indicator-pane-stack">
                {paneIndicators.map((indicator) => (
                  <IndicatorPane key={indicator.id} indicator={indicator} rows={chartRows} />
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
