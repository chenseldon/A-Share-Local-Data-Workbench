import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent
} from "react";
import {
  Brush,
  ChevronUp,
  Minus,
  MousePointer2,
  Plus,
  RefreshCw,
  Ruler,
  Search,
  Settings2,
  TextCursorInput,
  Trash2,
  TrendingUp,
  WholeWord
} from "lucide-react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type LogicalRange,
  type LogicalRangeChangeEventHandler,
  type Time
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
  searchQuery?: string;
  searchResults?: Security[];
  isSearching?: boolean;
  onSearchQueryChange?: (value: string) => void;
  onSelectSymbol?: (symbol: string) => void;
}

type IndicatorPlacement = "overlay" | "pane" | "built_in";
type DrawingTool = "cursor" | "trend" | "horizontal" | "vertical" | "brush" | "text" | "measure";
type DrawingKind = Exclude<DrawingTool, "cursor">;

interface IndicatorOption {
  id: string;
  label: string;
  placement: IndicatorPlacement;
  fields: string[];
  color: string;
  description: string;
}

interface DrawingPoint {
  time: Time;
  price: number;
}

interface Drawing {
  id: string;
  kind: DrawingKind;
  points: DrawingPoint[];
  text?: string;
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

const toolButtons: Array<{ tool: DrawingTool | "clear"; title: string; icon: typeof MousePointer2 }> = [
  { tool: "cursor", title: "Cursor", icon: MousePointer2 },
  { tool: "trend", title: "Trend line", icon: TrendingUp },
  { tool: "horizontal", title: "Horizontal line", icon: Minus },
  { tool: "vertical", title: "Vertical line", icon: WholeWord },
  { tool: "brush", title: "Brush", icon: Brush },
  { tool: "text", title: "Text note", icon: TextCursorInput },
  { tool: "measure", title: "Measure", icon: Ruler },
  { tool: "clear", title: "Clear drawings", icon: Trash2 }
];

const lineColors = ["#f59e0b", "#38bdf8", "#c084fc", "#22c55e", "#f97316", "#e879f9", "#60a5fa"];
const mainChartBaseHeight = 690;

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

function drawingId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function hasSearchProps(props: KLineChartProps): boolean {
  return Boolean(props.onSearchQueryChange && props.onSelectSymbol);
}

function formatMeasure(start: DrawingPoint, end: DrawingPoint): string {
  const priceDelta = end.price - start.price;
  const percent = start.price === 0 ? 0 : (priceDelta / start.price) * 100;
  return `${priceDelta.toFixed(2)} / ${percent.toFixed(2)}%`;
}

export function KLineChart(props: KLineChartProps) {
  const {
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
    refreshing,
    searchQuery = "",
    searchResults = [],
    isSearching = false,
    onSearchQueryChange,
    onSelectSymbol
  } = props;
  const mainContainerRef = useRef<HTMLDivElement | null>(null);
  const paneContainerRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const mainChartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [indicatorMenuOpen, setIndicatorMenuOpen] = useState(false);
  const [legendCollapsed, setLegendCollapsed] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [activeTool, setActiveTool] = useState<DrawingTool>("cursor");
  const [drawings, setDrawings] = useState<Drawing[]>([]);
  const [draftDrawing, setDraftDrawing] = useState<Drawing | null>(null);
  const [overlaySize, setOverlaySize] = useState({ width: 0, height: 0 });
  const [, setOverlayVersion] = useState(0);
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
  const paneHeight = paneIndicators.length > 2 ? 96 : 122;
  const mainChartHeight = Math.max(360, mainChartBaseHeight - paneIndicators.length * paneHeight);
  const canSearch = hasSearchProps(props);
  const primarySector = boards?.sw_l1[0] ?? security?.sector ?? "No sector";
  const conceptPreview = boards?.concepts.slice(0, 3) ?? [];
  const visibleSearchResults = searchResults.slice(0, 5);

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

  function pointFromEvent(event: PointerEvent<SVGSVGElement>): DrawingPoint | null {
    const chart = mainChartRef.current;
    const series = candleSeriesRef.current;
    const container = mainContainerRef.current;
    if (!chart || !series || !container) {
      return null;
    }
    const rect = container.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const time = chart.timeScale().coordinateToTime(x);
    const price = series.coordinateToPrice(y);
    if (!time || price === null || !Number.isFinite(price)) {
      return null;
    }
    return { time, price };
  }

  function pointToCoordinate(point: DrawingPoint): { x: number; y: number } | null {
    const chart = mainChartRef.current;
    const series = candleSeriesRef.current;
    if (!chart || !series) {
      return null;
    }
    const x = chart.timeScale().timeToCoordinate(point.time);
    const y = series.priceToCoordinate(point.price);
    if (x === null || y === null) {
      return null;
    }
    return { x, y };
  }

  function beginSearch() {
    if (!canSearch) {
      return;
    }
    setSearchOpen(true);
    onSearchQueryChange?.("");
    window.setTimeout(() => searchInputRef.current?.focus(), 0);
  }

  function selectSearchResult(symbol: string) {
    setSearchOpen(false);
    onSelectSymbol?.(symbol);
  }

  function handleToolClick(tool: DrawingTool | "clear") {
    if (tool === "clear") {
      setDrawings([]);
      setDraftDrawing(null);
      setActiveTool("cursor");
      return;
    }
    setActiveTool(tool);
    setDraftDrawing(null);
  }

  function handleDrawingPointerDown(event: PointerEvent<SVGSVGElement>) {
    if (activeTool === "cursor") {
      return;
    }
    const point = pointFromEvent(event);
    if (!point) {
      return;
    }
    event.currentTarget.setPointerCapture(event.pointerId);
    if (activeTool === "text") {
      setDrawings((current) => [...current, { id: drawingId(), kind: "text", points: [point], text: "Note" }]);
      return;
    }
    const drawing: Drawing = { id: drawingId(), kind: activeTool, points: [point, point] };
    setDraftDrawing(drawing);
  }

  function handleDrawingPointerMove(event: PointerEvent<SVGSVGElement>) {
    if (!draftDrawing) {
      return;
    }
    const point = pointFromEvent(event);
    if (!point) {
      return;
    }
    setDraftDrawing((current) => {
      if (!current) {
        return current;
      }
      if (current.kind === "brush") {
        return { ...current, points: [...current.points, point] };
      }
      return { ...current, points: [current.points[0], point] };
    });
  }

  function handleDrawingPointerUp() {
    if (!draftDrawing) {
      return;
    }
    setDrawings((current) => [...current, draftDrawing]);
    setDraftDrawing(null);
  }

  useEffect(() => {
    if (searchOpen) {
      searchInputRef.current?.focus();
    }
  }, [searchOpen]);

  useEffect(() => {
    const container = mainContainerRef.current;
    if (!container) {
      return;
    }
    const observer = new ResizeObserver(([entry]) => {
      setOverlaySize({
        width: entry.contentRect.width,
        height: entry.contentRect.height
      });
      setOverlayVersion((version) => version + 1);
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const mainContainer = mainContainerRef.current;
    if (!mainContainer || chartRows.length === 0) {
      mainChartRef.current = null;
      candleSeriesRef.current = null;
      return;
    }

    const allCharts: IChartApi[] = [];
    const unsubscribeHandlers: Array<{ chart: IChartApi; handler: LogicalRangeChangeEventHandler }> = [];
    let syncing = false;
    const syncRange = (source: IChartApi, range: LogicalRange | null) => {
      if (syncing || !range) {
        return;
      }
      syncing = true;
      allCharts.forEach((chart) => {
        if (chart !== source) {
          chart.timeScale().setVisibleLogicalRange(range);
        }
      });
      syncing = false;
      setOverlayVersion((version) => version + 1);
    };

    const mainChart = createChart(mainContainer, {
      autoSize: true,
      height: mainChartHeight,
      layout: {
        background: { type: ColorType.Solid, color: "#0f1720" },
        textColor: "#9fb0bd",
        attributionLogo: false
      },
      grid: {
        vertLines: { color: "rgba(159, 176, 189, 0.12)" },
        horzLines: { color: "rgba(159, 176, 189, 0.12)" }
      },
      rightPriceScale: { borderColor: "rgba(159, 176, 189, 0.2)" },
      timeScale: { borderColor: "rgba(159, 176, 189, 0.2)" },
      crosshair: { mode: 1 }
    });
    allCharts.push(mainChart);
    mainChartRef.current = mainChart;

    const candles = mainChart.addSeries(CandlestickSeries, {
      upColor: "#ef4444",
      downColor: "#22c55e",
      borderUpColor: "#ef4444",
      borderDownColor: "#22c55e",
      wickUpColor: "#ef4444",
      wickDownColor: "#22c55e"
    });
    candleSeriesRef.current = candles;
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
      const volume = mainChart.addSeries(HistogramSeries, {
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
        const series = mainChart.addSeries(LineSeries, {
          color: lineColors[(indicatorIndex + fieldIndex) % lineColors.length],
          lineWidth: 1,
          priceLineVisible: false
        });
        series.setData(lineData(field));
      });
    });

    paneIndicators.forEach((indicator, indicatorIndex) => {
      const paneContainer = paneContainerRefs.current[indicator.id];
      if (!paneContainer) {
        return;
      }
      const paneChart = createChart(paneContainer, {
        autoSize: true,
        height: paneHeight,
        layout: {
          background: { type: ColorType.Solid, color: "#0f1720" },
          textColor: "#9fb0bd",
          attributionLogo: false
        },
        grid: {
          vertLines: { color: "rgba(159, 176, 189, 0.11)" },
          horzLines: { color: "rgba(159, 176, 189, 0.11)" }
        },
        rightPriceScale: { borderColor: "rgba(159, 176, 189, 0.2)" },
        timeScale: { borderColor: "rgba(159, 176, 189, 0.2)" },
        crosshair: { mode: 1 }
      });
      allCharts.push(paneChart);

      const fields = firstAvailableFields(chartRows, indicator.fields);
      fields.forEach((field, fieldIndex) => {
        if (indicator.id === "macd" && field === "macd") {
          const series = paneChart.addSeries(HistogramSeries, {
            priceLineVisible: false,
            color: lineColors[(indicatorIndex + fieldIndex) % lineColors.length]
          });
          series.setData(
            chartRows
              .filter((row) => numericValue(row, field) !== null)
              .map((row) => ({
                time: row.trade_date,
                value: numericValue(row, field) ?? 0,
                color: (numericValue(row, field) ?? 0) >= 0 ? "rgba(239, 68, 68, 0.7)" : "rgba(34, 197, 94, 0.7)"
              }))
          );
          return;
        }
        const series = paneChart.addSeries(LineSeries, {
          color: lineColors[(indicatorIndex + fieldIndex) % lineColors.length],
          lineWidth: 1,
          priceLineVisible: false
        });
        series.setData(lineData(field));
      });
    });

    allCharts.forEach((chart) => {
      const handler: LogicalRangeChangeEventHandler = (range) => syncRange(chart, range);
      chart.timeScale().subscribeVisibleLogicalRangeChange(handler);
      unsubscribeHandlers.push({ chart, handler });
    });
    mainChart.timeScale().fitContent();
    const currentRange = mainChart.timeScale().getVisibleLogicalRange();
    if (currentRange) {
      allCharts.slice(1).forEach((chart) => chart.timeScale().setVisibleLogicalRange(currentRange));
    }

    return () => {
      unsubscribeHandlers.forEach(({ chart, handler }) => chart.timeScale().unsubscribeVisibleLogicalRangeChange(handler));
      allCharts.forEach((chart) => chart.remove());
      mainChartRef.current = null;
      candleSeriesRef.current = null;
    };
  }, [chartRows, enabledIndicators, mainChartHeight, paneHeight]);

  function renderDrawing(drawing: Drawing, isDraft = false) {
    const points = drawing.points.map(pointToCoordinate).filter((point): point is { x: number; y: number } => Boolean(point));
    if (points.length === 0) {
      return null;
    }
    const className = isDraft ? "chart-drawing draft" : "chart-drawing";
    if (drawing.kind === "horizontal") {
      return <line key={drawing.id} className={className} x1={0} x2={overlaySize.width} y1={points[0].y} y2={points[0].y} />;
    }
    if (drawing.kind === "vertical") {
      return <line key={drawing.id} className={className} x1={points[0].x} x2={points[0].x} y1={0} y2={overlaySize.height} />;
    }
    if (drawing.kind === "brush") {
      const path = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ");
      return <path key={drawing.id} className={className} d={path} />;
    }
    if (drawing.kind === "text") {
      return (
        <text key={drawing.id} className="chart-drawing-text" x={points[0].x + 8} y={points[0].y - 8}>
          {drawing.text}
        </text>
      );
    }
    const start = points[0];
    const end = points[1] ?? points[0];
    return (
      <g key={drawing.id}>
        <line className={className} x1={start.x} y1={start.y} x2={end.x} y2={end.y} />
        {drawing.kind === "measure" && drawing.points[1] && (
          <text className="chart-measure-label" x={(start.x + end.x) / 2 + 8} y={(start.y + end.y) / 2 - 8}>
            {formatMeasure(drawing.points[0], drawing.points[1])}
          </text>
        )}
      </g>
    );
  }

  return (
    <section className="panel chart-panel">
      <div className="section-heading chart-heading">
        <div className="chart-title-block">
          {searchOpen && canSearch ? (
            <div className="chart-title-search">
              <Search aria-hidden="true" size={18} />
              <input
                ref={searchInputRef}
                aria-label="Search or resolve A-share symbol"
                value={searchQuery}
                placeholder="Search symbol, name, or type 600519"
                onChange={(event) => onSearchQueryChange?.(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    setSearchOpen(false);
                    onSearchQueryChange?.("");
                  }
                }}
              />
              {searchQuery && (
                <div className="chart-search-results">
                  {isSearching && <div className="chart-search-row muted">Searching local free-stockdb directory...</div>}
                  {!isSearching && visibleSearchResults.length === 0 && (
                    <div className="chart-search-row muted">No local free-stockdb match.</div>
                  )}
                  {visibleSearchResults.map((result) => (
                    <button key={result.symbol} className="chart-search-row" type="button" onClick={() => selectSearchResult(result.symbol)}>
                      <span>{result.symbol}</span>
                      <strong>{result.name}</strong>
                      <small>{result.exchange}</small>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <button className="chart-security-title-button" type="button" onClick={beginSearch} disabled={!canSearch}>
              <span>{security?.symbol ?? "No symbol selected"}</span>
              <strong>{security?.name ?? sourceLabel(rows, quote)}</strong>
            </button>
          )}
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
              <RefreshCw aria-hidden="true" size={15} />
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
              <button
                type="button"
                title={tool.title}
                key={tool.title}
                className={tool.tool === activeTool ? "active" : ""}
                onClick={() => handleToolClick(tool.tool)}
              >
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
            <div className="chart-stack">
              <div className="main-chart-wrap" style={{ height: mainChartHeight }}>
                <div ref={mainContainerRef} className="kline-canvas" />
                <svg
                  className={activeTool === "cursor" ? "drawing-layer drawing-layer-passive" : "drawing-layer"}
                  width={overlaySize.width}
                  height={overlaySize.height}
                  viewBox={`0 0 ${overlaySize.width} ${overlaySize.height}`}
                  onPointerDown={handleDrawingPointerDown}
                  onPointerMove={handleDrawingPointerMove}
                  onPointerUp={handleDrawingPointerUp}
                  onPointerLeave={handleDrawingPointerUp}
                  aria-hidden="true"
                >
                  {drawings.map((drawing) => renderDrawing(drawing))}
                  {draftDrawing && renderDrawing(draftDrawing, true)}
                </svg>
              </div>
              {paneIndicators.length > 0 && (
                <div className="indicator-pane-stack">
                  {paneIndicators.map((indicator) => {
                    const fields = firstAvailableFields(chartRows, indicator.fields);
                    return (
                      <div className="indicator-pane" key={indicator.id} style={{ height: paneHeight }}>
                        <div className="indicator-pane-title">
                          <span>{indicator.label}</span>
                          <small>{fields.length ? fields.join(" / ") : "No values returned"}</small>
                        </div>
                        <div
                          className="indicator-pane-canvas"
                          ref={(node) => {
                            paneContainerRefs.current[indicator.id] = node;
                          }}
                        />
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
