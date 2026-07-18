import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent
} from "react";
import {
  ArrowUpRight,
  Brush,
  ChevronUp,
  Crosshair,
  Eye,
  EyeOff,
  Lock,
  Minus,
  MousePointer2,
  Plus,
  RefreshCw,
  Ruler,
  Search,
  Settings2,
  Square,
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
import type { ChartPeriod } from "../api";
import type { BoardMappingResponse, ChartBar, MarketQuote, Security } from "../types";

interface KLineChartProps {
  rows: ChartBar[];
  quote: MarketQuote | null;
  security?: Security | null;
  boards?: BoardMappingResponse | null;
  boardError?: string | null;
  enabledIndicators: string[];
  onIndicatorsChange: (indicators: string[]) => void;
  period?: ChartPeriod;
  onPeriodChange?: (period: ChartPeriod) => void;
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
  mode?: "security" | "market";
}

type IndicatorPlacement = "overlay" | "pane" | "built_in";
type DrawingTool = "crosshair" | "horizontalSegment" | "segment" | "verticalSegment" | "parallel" | "arrow" | "priceLine" | "text" | "rectangle" | "fibonacci";
type DrawingAction = "lock" | "hide" | "clear";
type DrawingKind = DrawingTool;

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

interface CrosshairState {
  x: number;
  y: number;
  rowIndex: number;
  row: ChartBar;
  valueLabel: string;
  timeLabel: string;
}

interface AxisValueLabel {
  id: string;
  value: string;
  color: string;
  y: number;
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

const toolButtons: Array<{ tool: DrawingTool; title: string; icon: typeof MousePointer2 }> = [
  { tool: "crosshair", title: "Crosshair", icon: Crosshair },
  { tool: "horizontalSegment", title: "Horizontal segment", icon: Minus },
  { tool: "segment", title: "Line segment", icon: TrendingUp },
  { tool: "verticalSegment", title: "Vertical segment", icon: WholeWord },
  { tool: "parallel", title: "Parallel lines", icon: Brush },
  { tool: "arrow", title: "Arrow", icon: ArrowUpRight },
  { tool: "priceLine", title: "Price line", icon: Ruler },
  { tool: "text", title: "Text", icon: TextCursorInput },
  { tool: "rectangle", title: "Rectangle", icon: Square },
  { tool: "fibonacci", title: "Fibonacci retracement", icon: Ruler }
];

const toolActions: Array<{ action: DrawingAction; title: string; icon: typeof MousePointer2 }> = [
  { action: "lock", title: "Lock all drawings", icon: Lock },
  { action: "hide", title: "Hide all drawings", icon: EyeOff },
  { action: "clear", title: "Clear all drawings", icon: Trash2 }
];

const periodOptions: Array<{ value: ChartPeriod; label: string; legendLabel: string }> = [
  { value: "1m", label: "1分", legendLabel: "1 MIN" },
  { value: "5m", label: "5分", legendLabel: "5 MIN" },
  { value: "15m", label: "15分", legendLabel: "15 MIN" },
  { value: "30m", label: "30分", legendLabel: "30 MIN" },
  { value: "60m", label: "1小时", legendLabel: "1 HOUR" },
  { value: "1d", label: "日", legendLabel: "1 DAY" },
  { value: "1w", label: "周", legendLabel: "1 WEEK" },
  { value: "1M", label: "月", legendLabel: "1 MONTH" }
];

const lineColors = ["#f59e0b", "#38bdf8", "#c084fc", "#22c55e", "#f97316", "#e879f9", "#60a5fa"];
const fieldColors: Record<string, string> = {
  ma5: "#f59e0b",
  ma10: "#38bdf8",
  ma20: "#a78bfa",
  dif: "#f59e0b",
  dea: "#38bdf8",
  macd: "#ef4444",
  rsi: "#38bdf8",
  rsi6: "#38bdf8",
  rsi12: "#a78bfa",
  rsi24: "#f59e0b",
  k: "#f59e0b",
  d: "#38bdf8",
  j: "#e879f9",
  volume: "#60a5fa"
};
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

function rowTime(row: ChartBar): Time {
  return (row.chart_time ?? row.trade_date) as Time;
}

function formatLegendNumber(value: number | null | undefined, maximumFractionDigits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "NA";
  }
  return value.toLocaleString(undefined, { maximumFractionDigits });
}

function formatVolume(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "NA";
  }
  if (Math.abs(value) >= 100_000_000) {
    return `${(value / 100_000_000).toFixed(2)}亿`;
  }
  if (Math.abs(value) >= 10_000) {
    return `${(value / 10_000).toFixed(2)}万`;
  }
  return value.toLocaleString();
}

function fieldColor(field: string, fallback: string, value?: number | null): string {
  if (field === "macd" && typeof value === "number") {
    return value >= 0 ? "#ef4444" : "#22c55e";
  }
  return fieldColors[field] ?? fallback;
}

function fieldLabel(field: string): string {
  if (field.startsWith("ma") || field.startsWith("rsi")) {
    return field.toUpperCase();
  }
  if (field === "dif") {
    return "DIF";
  }
  if (field === "dea") {
    return "DEA";
  }
  if (field === "macd") {
    return "MACD";
  }
  return field;
}

function rowChangePercent(row: ChartBar): number | null {
  if (row.open === null || row.open === undefined || row.open === 0 || row.close === null || row.close === undefined) {
    return null;
  }
  return ((row.close - row.open) / row.open) * 100;
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
    period = "1d",
    onPeriodChange,
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
    onSelectSymbol,
    mode = "security"
  } = props;
  const mainContainerRef = useRef<HTMLDivElement | null>(null);
  const chartStackRef = useRef<HTMLDivElement | null>(null);
  const paneContainerRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const mainChartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const mainSeriesRefs = useRef<Array<{ id: string; field: string; color: string; series: ISeriesApi<"Line"> }>>([]);
  const paneSeriesRefs = useRef<Record<string, Array<{ id: string; field: string; color: string; series: ISeriesApi<"Line"> | ISeriesApi<"Histogram"> }>>>({});
  const [indicatorMenuOpen, setIndicatorMenuOpen] = useState(false);
  const [legendCollapsed, setLegendCollapsed] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [activeTool, setActiveTool] = useState<DrawingTool>("crosshair");
  const [drawingsLocked, setDrawingsLocked] = useState(false);
  const [drawingsHidden, setDrawingsHidden] = useState(false);
  const [drawings, setDrawings] = useState<Drawing[]>([]);
  const [draftDrawing, setDraftDrawing] = useState<Drawing | null>(null);
  const [crosshair, setCrosshair] = useState<CrosshairState | null>(null);
  const [axisValueLabels, setAxisValueLabels] = useState<AxisValueLabel[]>([]);
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
  const boardTags = [security?.exchange, security?.asset_type, primarySector, ...(boards?.concepts ?? [])].filter(
    (tag): tag is string => Boolean(tag)
  );
  const visibleBoardTags = boardTags.slice(0, 3);
  const hiddenBoardTagCount = Math.max(0, boardTags.length - visibleBoardTags.length);
  const boardTitle = boardTags.join(" / ");
  const visibleSearchResults = searchResults.slice(0, 5);
  const legendRow = crosshair?.row ?? chartRows[chartRows.length - 1] ?? null;
  const legendChange = legendRow ? rowChangePercent(legendRow) : null;
  const displaySymbol = security?.symbol ?? quote?.symbol ?? "No symbol selected";
  const displayName = security?.name ?? sourceLabel(rows, quote);
  const mainLegendRows = selectedIndicators
    .filter((indicator) => indicator.placement === "overlay")
    .map((indicator) => ({
      indicator,
      fields: firstAvailableFields(chartRows, indicator.fields)
    }))
    .filter((item) => item.fields.length > 0);

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
      .map((row) => ({ time: rowTime(row), value: numericValue(row, field) ?? 0 }));
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

  function updateAxisValueLabels(row: ChartBar | null) {
    const stack = chartStackRef.current;
    const mainContainer = mainContainerRef.current;
    const candleSeries = candleSeriesRef.current;
    if (!row || !stack || !mainContainer || !candleSeries) {
      setAxisValueLabels([]);
      return;
    }

    const stackTop = stack.getBoundingClientRect().top;
    const labels: AxisValueLabel[] = [];
    const mainTop = mainContainer.getBoundingClientRect().top - stackTop;
    const closeY = row.close === null || row.close === undefined ? null : candleSeries.priceToCoordinate(row.close);
    if (closeY !== null) {
      labels.push({
        id: "close",
        value: formatLegendNumber(row.close),
        color: (row.close ?? 0) >= (row.open ?? row.close ?? 0) ? "#ef4444" : "#22c55e",
        y: mainTop + closeY
      });
    }

    mainSeriesRefs.current.forEach((item) => {
      const value = numericValue(row, item.field);
      const y = value === null ? null : item.series.priceToCoordinate(value);
      if (value !== null && y !== null) {
        labels.push({
          id: item.id,
          value: formatLegendNumber(value, 2),
          color: fieldColor(item.field, item.color, value),
          y: mainTop + y
        });
      }
    });

    const volumeValue = row.volume;
    if (volumeValue !== null && volumeValue !== undefined && Number.isFinite(volumeValue)) {
      labels.push({
        id: "volume",
        value: formatVolume(volumeValue),
        color: fieldColors.volume,
        y: mainTop + mainContainer.getBoundingClientRect().height - 18
      });
    }

    paneIndicators.forEach((indicator) => {
      const pane = paneContainerRefs.current[indicator.id];
      if (!pane) {
        return;
      }
      const paneTop = pane.getBoundingClientRect().top - stackTop;
      (paneSeriesRefs.current[indicator.id] ?? []).forEach((item) => {
        const value = numericValue(row, item.field);
        const y = value === null ? null : item.series.priceToCoordinate(value);
        if (value !== null && y !== null) {
          labels.push({
            id: item.id,
            value: formatLegendNumber(value, 2),
            color: fieldColor(item.field, item.color, value),
            y: paneTop + y
          });
        }
      });
    });

    setAxisValueLabels(labels);
  }

  function handleToolClick(tool: DrawingTool) {
    setActiveTool(tool);
    setDraftDrawing(null);
  }

  function handleToolAction(action: DrawingAction) {
    if (action === "lock") {
      setDrawingsLocked((locked) => !locked);
      setDraftDrawing(null);
      return;
    }
    if (action === "hide") {
      setDrawingsHidden((hidden) => !hidden);
      setDraftDrawing(null);
      return;
    }
    setDrawings([]);
    setDraftDrawing(null);
  }

  function handleDrawingPointerDown(event: PointerEvent<SVGSVGElement>) {
    if (activeTool === "crosshair" || drawingsLocked) {
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

  function handleChartPointerMove(event: PointerEvent<HTMLDivElement>) {
    if (activeTool !== "crosshair") {
      return;
    }
    const chart = mainChartRef.current;
    const series = candleSeriesRef.current;
    const mainContainer = mainContainerRef.current;
    const stack = chartStackRef.current;
    if (!chart || !series || !mainContainer || !stack || chartRows.length === 0) {
      return;
    }
    const mainRect = mainContainer.getBoundingClientRect();
    const stackRect = stack.getBoundingClientRect();
    const x = event.clientX - mainRect.left;
    const logical = chart.timeScale().coordinateToLogical(x);
    if (logical === null) {
      setCrosshair(null);
      return;
    }
    const rowIndex = Math.max(0, Math.min(chartRows.length - 1, Math.round(logical)));
    const row = chartRows[rowIndex];
    const stackY = event.clientY - stackRect.top;
    const mainY = event.clientY - mainRect.top;
    const price = mainY >= 0 && mainY <= mainRect.height ? series.coordinateToPrice(mainY) : null;
    let valueLabel = formatLegendNumber(price ?? row.close);
    if (price === null) {
      for (const indicator of paneIndicators) {
        const pane = paneContainerRefs.current[indicator.id];
        if (!pane) {
          continue;
        }
        const paneRect = pane.getBoundingClientRect();
        if (event.clientY < paneRect.top || event.clientY > paneRect.bottom) {
          continue;
        }
        const field = firstAvailableFields(chartRows, indicator.fields)[0];
        valueLabel = field ? formatLegendNumber(numericValue(row, field), 3) : "NA";
        break;
      }
    }
    setCrosshair({
      x,
      y: Math.max(0, Math.min(stackRect.height, stackY)),
      rowIndex,
      row,
      valueLabel,
      timeLabel: row.trade_date
    });
    updateAxisValueLabels(row);
  }

  function clearCrosshair() {
    setCrosshair(null);
    updateAxisValueLabels(chartRows[chartRows.length - 1] ?? null);
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
    mainSeriesRefs.current = [];
    paneSeriesRefs.current = {};
    volumeSeriesRef.current = null;
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
      timeScale: { borderColor: "rgba(159, 176, 189, 0.2)", visible: paneIndicators.length === 0 },
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
      wickDownColor: "#22c55e",
      priceLineVisible: false,
      lastValueVisible: false
    });
    candleSeriesRef.current = candles;
    candles.setData(
      chartRows.map((row) => ({
        time: rowTime(row),
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
        color: "rgba(96, 165, 250, 0.35)",
        priceLineVisible: false,
        lastValueVisible: false
      });
      volumeSeriesRef.current = volume;
      volume.priceScale().applyOptions({
        scaleMargins: { top: 0.84, bottom: 0 }
      });
      volume.setData(
        chartRows.map((row) => ({
          time: rowTime(row),
          value: row.volume ?? 0,
          color: (row.close ?? 0) >= (row.open ?? 0) ? "rgba(239, 68, 68, 0.38)" : "rgba(34, 197, 94, 0.38)"
        }))
      );
    }

    overlayIndicators.forEach((indicator, indicatorIndex) => {
      const fields = firstAvailableFields(chartRows, indicator.fields);
      fields.forEach((field, fieldIndex) => {
        const series = mainChart.addSeries(LineSeries, {
          color: fieldColor(field, lineColors[(indicatorIndex + fieldIndex) % lineColors.length]),
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false
        });
        mainSeriesRefs.current.push({
          id: `${indicator.id}-${field}`,
          field,
          color: fieldColor(field, lineColors[(indicatorIndex + fieldIndex) % lineColors.length]),
          series
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
        timeScale: {
          borderColor: "rgba(159, 176, 189, 0.2)",
          visible: indicatorIndex === paneIndicators.length - 1
        },
        crosshair: { mode: 1 }
      });
      allCharts.push(paneChart);

      const fields = firstAvailableFields(chartRows, indicator.fields);
      fields.forEach((field, fieldIndex) => {
        if (indicator.id === "macd" && field === "macd") {
          const series = paneChart.addSeries(HistogramSeries, {
            priceLineVisible: false,
            lastValueVisible: false,
            color: lineColors[(indicatorIndex + fieldIndex) % lineColors.length]
          });
          paneSeriesRefs.current[indicator.id] = [
            ...(paneSeriesRefs.current[indicator.id] ?? []),
            {
              id: `${indicator.id}-${field}`,
              field,
              color: lineColors[(indicatorIndex + fieldIndex) % lineColors.length],
              series
            }
          ];
          series.setData(
            chartRows
                .filter((row) => numericValue(row, field) !== null)
                .map((row) => ({
                time: rowTime(row),
                value: numericValue(row, field) ?? 0,
                color: (numericValue(row, field) ?? 0) >= 0 ? "rgba(239, 68, 68, 0.7)" : "rgba(34, 197, 94, 0.7)"
              }))
          );
          return;
        }
        const series = paneChart.addSeries(LineSeries, {
          color: fieldColor(field, lineColors[(indicatorIndex + fieldIndex) % lineColors.length]),
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false
        });
        paneSeriesRefs.current[indicator.id] = [
          ...(paneSeriesRefs.current[indicator.id] ?? []),
          {
            id: `${indicator.id}-${field}`,
            field,
            color: fieldColor(field, lineColors[(indicatorIndex + fieldIndex) % lineColors.length]),
            series
          }
        ];
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
    window.setTimeout(() => updateAxisValueLabels(chartRows[chartRows.length - 1] ?? null), 0);

    return () => {
      unsubscribeHandlers.forEach(({ chart, handler }) => chart.timeScale().unsubscribeVisibleLogicalRangeChange(handler));
      allCharts.forEach((chart) => chart.remove());
      mainChartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      mainSeriesRefs.current = [];
      paneSeriesRefs.current = {};
    };
  }, [chartRows, enabledIndicators, mainChartHeight, paneHeight]);

  function renderDrawing(drawing: Drawing, isDraft = false) {
    const points = drawing.points.map(pointToCoordinate).filter((point): point is { x: number; y: number } => Boolean(point));
    if (points.length === 0) {
      return null;
    }
    const className = isDraft ? "chart-drawing draft" : "chart-drawing";
    const start = points[0];
    const end = points[1] ?? points[0];
    const minX = Math.min(start.x, end.x);
    const maxX = Math.max(start.x, end.x);
    const minY = Math.min(start.y, end.y);
    const maxY = Math.max(start.y, end.y);
    const priceText = drawing.points[0]?.price.toFixed(2) ?? "";

    if (drawing.kind === "text") {
      return (
        <text key={drawing.id} className="chart-drawing-text" x={points[0].x + 8} y={points[0].y - 8}>
          {drawing.text}
        </text>
      );
    }

    if (drawing.kind === "horizontalSegment") {
      return <line key={drawing.id} className={className} x1={start.x} y1={start.y} x2={end.x} y2={start.y} />;
    }

    if (drawing.kind === "verticalSegment") {
      return <line key={drawing.id} className={className} x1={start.x} y1={start.y} x2={start.x} y2={end.y} />;
    }

    if (drawing.kind === "priceLine") {
      return (
        <g key={drawing.id}>
          <line className={className} x1={0} y1={start.y} x2={overlaySize.width} y2={start.y} />
          <text className="chart-price-label" x={Math.max(8, overlaySize.width - 62)} y={start.y - 6}>
            {priceText}
          </text>
        </g>
      );
    }

    if (drawing.kind === "rectangle") {
      return <rect key={drawing.id} className="chart-drawing chart-drawing-fill" x={minX} y={minY} width={maxX - minX} height={maxY - minY} />;
    }

    if (drawing.kind === "parallel") {
      const offset = 34;
      return (
        <g key={drawing.id}>
          <line className={className} x1={start.x} y1={start.y} x2={end.x} y2={end.y} />
          <line className={className} x1={start.x} y1={start.y + offset} x2={end.x} y2={end.y + offset} />
        </g>
      );
    }

    if (drawing.kind === "fibonacci") {
      const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
      return (
        <g key={drawing.id}>
          {levels.map((level) => {
            const y = start.y + (end.y - start.y) * level;
            return (
              <g key={level}>
                <line className={className} x1={minX} y1={y} x2={maxX} y2={y} />
                <text className="chart-fib-label" x={minX + 5} y={y - 4}>
                  {(level * 100).toFixed(level === 0 || level === 1 ? 0 : 1)}%
                </text>
              </g>
            );
          })}
        </g>
      );
    }

    if (drawing.kind === "arrow") {
      const angle = Math.atan2(end.y - start.y, end.x - start.x);
      const arrowLength = 12;
      const left = {
        x: end.x - arrowLength * Math.cos(angle - Math.PI / 6),
        y: end.y - arrowLength * Math.sin(angle - Math.PI / 6)
      };
      const right = {
        x: end.x - arrowLength * Math.cos(angle + Math.PI / 6),
        y: end.y - arrowLength * Math.sin(angle + Math.PI / 6)
      };
      return (
        <g key={drawing.id}>
          <line className={className} x1={start.x} y1={start.y} x2={end.x} y2={end.y} />
          <polyline className={className} points={`${left.x},${left.y} ${end.x},${end.y} ${right.x},${right.y}`} />
        </g>
      );
    }

    return (
      <g key={drawing.id}>
        <line className={className} x1={start.x} y1={start.y} x2={end.x} y2={end.y} />
      </g>
    );
  }

  return (
    <section className={`panel chart-panel chart-panel-${mode}`}>
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
              <span>{displaySymbol}</span>
              <strong>{displayName}</strong>
            </button>
          )}
          {security && (
            <div className="chart-security-meta" title={boardTitle}>
              {visibleBoardTags.map((tag, index) => (
                <span key={`${tag}-${index}`}>{tag}</span>
              ))}
              {hiddenBoardTagCount > 0 && <span>+{hiddenBoardTagCount}</span>}
              {boardError && <span>Board mapping failed</span>}
            </div>
          )}
        </div>
        <div className="chart-periods" aria-label="K-line period">
          {periodOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              className={option.value === period ? "active" : ""}
              onClick={() => onPeriodChange?.(option.value)}
            >
              {option.label}
            </button>
          ))}
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
          <div className="tool-separator" />
          {toolActions.map((tool) => {
            const Icon = tool.action === "hide" && drawingsHidden ? Eye : tool.icon;
            const active = (tool.action === "lock" && drawingsLocked) || (tool.action === "hide" && drawingsHidden);
            return (
              <button
                type="button"
                title={tool.title}
                key={tool.action}
                className={active ? "active" : ""}
                onClick={() => handleToolAction(tool.action)}
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
            <div className="legend-content">
              <div className="legend-quote-row">
                <strong>{security?.symbol ?? "K-Line"}</strong>
                {security?.name && <span>{security.name}</span>}
                <span>{periodOptions.find((option) => option.value === period)?.legendLabel ?? period.toUpperCase()}</span>
                {legendRow && (
                  <>
                    <span>O {formatLegendNumber(legendRow.open)}</span>
                    <span>H {formatLegendNumber(legendRow.high)}</span>
                    <span>L {formatLegendNumber(legendRow.low)}</span>
                    <span>C {formatLegendNumber(legendRow.close)}</span>
                    <span className={legendChange !== null && legendChange >= 0 ? "legend-up" : "legend-down"}>
                      {legendChange === null ? "CHG NA" : `${legendChange >= 0 ? "+" : ""}${legendChange.toFixed(2)}%`}
                    </span>
                    <span>VOL {formatVolume(legendRow.volume)}</span>
                  </>
                )}
              </div>
              {!legendCollapsed && mainLegendRows.length > 0 && (
                <div className="legend-indicator-grid">
                  {mainLegendRows.map(({ indicator, fields }) => (
                    <div className="legend-indicator-row" key={indicator.id}>
                      <span>{indicator.label}</span>
                      {fields.map((field, fieldIndex) => {
                        const value = legendRow ? numericValue(legendRow, field) : null;
                        return (
                          <small key={field} style={{ color: fieldColor(field, lineColors[fieldIndex % lineColors.length], value) }}>
                            {fieldLabel(field)} {formatLegendNumber(value, 3)}
                          </small>
                        );
                      })}
                    </div>
                  ))}
                </div>
              )}
              {indicatorStatus === "failed" && <span className="chart-warning">{indicatorError ?? "Indicator calculation failed"}</span>}
            </div>
          </div>
          {loading && <div className="chart-empty">Loading free-stockdb K-line...</div>}
          {error && <div className="chart-empty chart-error">{error}</div>}
          {!loading && !error && chartRows.length === 0 && (
            <div className="chart-empty">No free-stockdb K-line data yet. Use Refresh market after stockdb.exe is running.</div>
          )}
          {!loading && !error && chartRows.length > 0 && (
            <div
              ref={chartStackRef}
              className="chart-stack"
              onPointerMove={handleChartPointerMove}
              onPointerLeave={clearCrosshair}
            >
              {crosshair && (
                <div className="chart-crosshair-layer" aria-hidden="true">
                  <span className="chart-crosshair-x" style={{ left: crosshair.x }} />
                  <span className="chart-crosshair-y" style={{ top: crosshair.y }} />
                  <span className="chart-crosshair-price" style={{ top: crosshair.y }}>
                    {crosshair.valueLabel}
                  </span>
                  <span className="chart-crosshair-time" style={{ left: crosshair.x }}>
                    {crosshair.timeLabel}
                  </span>
                </div>
              )}
              {axisValueLabels.length > 0 && (
                <div className="chart-axis-value-labels" aria-hidden="true">
                  {axisValueLabels.map((label) => (
                    <span key={label.id} style={{ top: label.y, background: label.color }}>
                      {label.value}
                    </span>
                  ))}
                </div>
              )}
              <div className="main-chart-wrap" style={{ height: mainChartHeight }}>
                <div ref={mainContainerRef} className="kline-canvas" />
                <svg
                  className={activeTool === "crosshair" || drawingsLocked ? "drawing-layer drawing-layer-passive" : "drawing-layer"}
                  width={overlaySize.width}
                  height={overlaySize.height}
                  viewBox={`0 0 ${overlaySize.width} ${overlaySize.height}`}
                  onPointerDown={handleDrawingPointerDown}
                  onPointerMove={handleDrawingPointerMove}
                  onPointerUp={handleDrawingPointerUp}
                  onPointerLeave={handleDrawingPointerUp}
                  aria-hidden="true"
                >
                  {!drawingsHidden && drawings.map((drawing) => renderDrawing(drawing))}
                  {!drawingsHidden && draftDrawing && renderDrawing(draftDrawing, true)}
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
                          {fields.length ? (
                            fields.map((field, fieldIndex) => {
                              const value = legendRow ? numericValue(legendRow, field) : null;
                              return (
                                <small key={field} style={{ color: fieldColor(field, lineColors[fieldIndex % lineColors.length], value) }}>
                                  {fieldLabel(field)} {formatLegendNumber(value, 3)}
                                </small>
                              );
                            })
                          ) : (
                            <small>No values returned</small>
                          )}
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
