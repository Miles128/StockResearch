import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  createChart,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type LogicalRange,
  type Time,
} from "lightweight-charts";
import { api, type ChartOverlaySet, type KlineChart } from "./api";
import { mergeKlineBars, maSeries, type KlineBar } from "./chartIndicators";
import { detectTrendLines } from "./chartTrendlines";
import { subscribeChartOverlays } from "./chartOverlayBus";
import { useI18n } from "./i18n";
import { getCachedKline, patchCachedKline, setCachedKline } from "./klineCache";
import { baseChartOptions, applyChartEdgeAlignment, readChartColors } from "./ui/chartTheme";

export type MarketChartVariant = "stock" | "index";

const INITIAL_DAYS = 90;
const LOAD_CHUNK = 90;
const MAX_BARS = 500;
/** Sina returns up to ~1023 bars — expand window from same source for seamless joins. */
const SINA_EXPAND_LIMIT = 1000;
const LOAD_TRIGGER_BARS = 18;
const MA_PERIODS = [5, 10, 20, 60, 120, 180] as const;
const MA_COLORS: Record<number, string> = {
  5: "#9ca3af",
  10: "#a8a29e",
  20: "#d4a017",
  60: "#5b9bd5",
  120: "#9b7fd4",
  180: "#e87878",
};

interface MarketChartProps {
  symbol: string;
  compact?: boolean;
  variant?: MarketChartVariant;
}

interface ChartRuntime {
  mainChart?: IChartApi;
  subCharts: IChartApi[];
  candles?: ISeriesApi<"Candlestick">;
  maLines: Map<number, ISeriesApi<"Line">>;
  volume?: ISeriesApi<"Histogram">;
  macdHist?: ISeriesApi<"Histogram">;
  macdLine?: ISeriesApi<"Line">;
  macdSignal?: ISeriesApi<"Line">;
  rsi?: ISeriesApi<"Line">;
  trendLines: ISeriesApi<"Line">[];
  aiOverlays: ISeriesApi<"Line">[];
  mounted: { el: HTMLElement; chart: IChartApi; h: number }[];
}

function barTime(date: string): Time {
  return date.slice(0, 10) as Time;
}

function paneWidth(el: HTMLElement | null): number {
  if (!el) return 0;
  return el.clientWidth || el.parentElement?.clientWidth || 0;
}

/**
 * Normalize wheel events before lightweight-charts sees them.
 * The library clamps zoomScale to ±1 and treats deltaMode=PAGE as ×100, so
 * trackpad pinches / small deltas (~±3) zoom <1% per event — zoom-in feels dead.
 * Re-dispatch in pixel mode with an amplified delta for usable zoom.
 */
function installWheelZoomNormalizer(el: HTMLElement): () => void {
  const onWheel = (e: WheelEvent) => {
    if ((e as WheelEvent & { __normalized?: boolean }).__normalized) return;
    if (e.deltaY === 0 && e.deltaX === 0) return;
    e.preventDefault();
    e.stopPropagation();
    let dy = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
    let dx = e.deltaMode === 1 ? e.deltaX * 16 : e.deltaX;
    dy = Math.max(-100, Math.min(100, dy));
    dx = Math.max(-100, Math.min(100, dx));
    // Only amplify when the vertical (zoom) gesture dominates, so horizontal
    // two-finger panning keeps its natural speed.
    if (dy !== 0 && Math.abs(dy) >= Math.abs(dx)) {
      dy = Math.sign(dy) * Math.max(Math.abs(dy), 30);
    }
    const forwarded = new WheelEvent("wheel", {
      deltaY: dy,
      deltaX: dx,
      deltaMode: 0,
      clientX: e.clientX,
      clientY: e.clientY,
      bubbles: true,
      cancelable: true,
    });
    (forwarded as WheelEvent & { __normalized?: boolean }).__normalized = true;
    // dispatch on the chart widget root (child of container) so the library handler receives it
    const target = el.firstElementChild ?? el;
    target.dispatchEvent(forwarded);
  };
  el.addEventListener("wheel", onWheel, { capture: true, passive: false });
  return () => el.removeEventListener("wheel", onWheel, { capture: true });
}

function visibleWindow(barCount: number, compact: boolean): LogicalRange {
  const span = compact ? 42 : 55;
  const pad = 2;
  const to = barCount - 1 + pad;
  const from = Math.max(0, barCount - span);
  return { from, to } as LogicalRange;
}

/** Unified K-line chart with volume, optional MACD/RSI, and scroll-back loading. */
export function MarketChart({ symbol, compact = false, variant = "stock" }: MarketChartProps) {
  const { t } = useI18n();
  const rootRef = useRef<HTMLDivElement>(null);
  const mainRef = useRef<HTMLDivElement>(null);
  const macdRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<ChartRuntime>({
    subCharts: [],
    mounted: [],
    maLines: new Map(),
    trendLines: [],
    aiOverlays: [],
  });
  const visibleRangeRef = useRef<LogicalRange | null>(null);
  const loadingMoreRef = useRef(false);
  const exhaustedRef = useRef(false);
  const initialPaintRef = useRef(true);
  const skipDataEffectRef = useRef(false);
  const syncingRangeRef = useRef(false);
  const barsRef = useRef<KlineBar[]>([]);
  const symbolRef = useRef(symbol);

  const [data, setData] = useState<KlineChart | null>(() => getCachedKline(symbol));
  const dataRef = useRef<KlineChart | null>(data);
  const [loading, setLoading] = useState(() => getCachedKline(symbol) == null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [showMacd, setShowMacd] = useState(false);
  const [showRsi, setShowRsi] = useState(false);
  const [showTrend, setShowTrend] = useState(true);
  const [selectedMa, setSelectedMa] = useState<number[]>([20]);
  const [maMenuOpen, setMaMenuOpen] = useState(false);

  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  const allCharts = useCallback((): IChartApi[] => {
    const rt = runtimeRef.current;
    return rt.mainChart ? [rt.mainChart, ...rt.subCharts] : rt.subCharts;
  }, []);

  const syncVisibleRange = useCallback(
    (range: LogicalRange | null, source?: IChartApi) => {
      if (!range || syncingRangeRef.current) return;
      syncingRangeRef.current = true;
      try {
        allCharts().forEach((chart) => {
          if (chart !== source) {
            chart.timeScale().setVisibleLogicalRange(range);
          }
        });
      } finally {
        syncingRangeRef.current = false;
      }
    },
    [allCharts],
  );

  const setAllVisibleRange = useCallback(
    (range: LogicalRange) => {
      visibleRangeRef.current = range;
      syncingRangeRef.current = true;
      try {
        allCharts().forEach((chart) => chart.timeScale().setVisibleLogicalRange(range));
      } finally {
        syncingRangeRef.current = false;
      }
    },
    [allCharts],
  );

  const applyChart = useCallback(
    (chart: KlineChart, opts?: { preserveRange?: boolean; added?: number; initial?: boolean }) => {
      const rt = runtimeRef.current;
      const { up: chartUp, down: chartDown } = readChartColors();

      const candleData = chart.bars.map((b) => ({
        time: barTime(b.date),
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      }));
      const closes = chart.bars.map((b) => b.close);
      const volumeData = chart.bars.map((b) => ({
        time: barTime(b.date),
        value: b.volume,
        color: b.close >= b.open ? `${chartUp}88` : `${chartDown}88`,
      }));
      rt.candles?.setData(candleData);
      rt.maLines.forEach((series, period) => {
        const ma = maSeries(closes, period);
        const maData = chart.bars
          .map((b, i) => ({ time: barTime(b.date), value: ma[i] }))
          .filter((p): p is { time: Time; value: number } => p.value != null);
        series.setData(maData);
      });
      rt.volume?.setData(volumeData);

      if (rt.macdHist && rt.macdLine && rt.macdSignal) {
        rt.macdHist.setData(
          chart.bars
            .map((b, i) => ({
              time: barTime(b.date),
              value: chart.indicators.macd_histogram[i] ?? 0,
              color:
                (chart.indicators.macd_histogram[i] ?? 0) >= 0 ? `${chartUp}88` : `${chartDown}88`,
            }))
            .filter((_, i) => chart.indicators.macd_histogram[i] != null),
        );
        rt.macdLine.setData(
          chart.bars
            .map((b, i) => ({
              time: barTime(b.date),
              value: chart.indicators.macd[i],
            }))
            .filter((p): p is { time: Time; value: number } => p.value != null),
        );
        rt.macdSignal.setData(
          chart.bars
            .map((b, i) => ({
              time: barTime(b.date),
              value: chart.indicators.macd_signal[i],
            }))
            .filter((p): p is { time: Time; value: number } => p.value != null),
        );
      }

      rt.rsi?.setData(
        chart.bars
          .map((b, i) => ({
            time: barTime(b.date),
            value: chart.indicators.rsi[i],
          }))
          .filter((p): p is { time: Time; value: number } => p.value != null),
      );

      const main = rt.mainChart;
      if (!main) return;

      if (opts?.preserveRange && opts.added && opts.added > 0) {
        const prev = visibleRangeRef.current;
        if (prev) {
          setAllVisibleRange({
            from: prev.from + opts.added,
            to: prev.to + opts.added,
          } as LogicalRange);
        }
      } else if (opts?.initial || initialPaintRef.current) {
        setAllVisibleRange(visibleWindow(chart.bars.length, compact));
        initialPaintRef.current = false;
      }
    },
    [compact, setAllVisibleRange],
  );

  const requestMoreHistory = useCallback(() => {
    if (loadingMoreRef.current || exhaustedRef.current) return;
    const bars = barsRef.current;
    if (bars.length >= MAX_BARS) {
      exhaustedRef.current = true;
      return;
    }
    const earliest = bars[0]?.date;
    if (!earliest) return;

    const requestedSymbol = symbol;
    const nextDays = Math.min(bars.length + LOAD_CHUNK, MAX_BARS);
    const useSinaExpand = nextDays <= SINA_EXPAND_LIMIT;

    loadingMoreRef.current = true;
    setLoadingMore(true);

    const fetchPromise = useSinaExpand
      ? api.klineChart(symbol, nextDays)
      : api.klineChart(symbol, LOAD_CHUNK, earliest);

    fetchPromise
      .then((chunk) => {
        // The user switched stocks while this page request was in flight —
        // discard the stale chunk so it cannot pollute the new symbol's bars.
        if (symbolRef.current !== requestedSymbol) return;
        if (!chunk.bars.length) {
          exhaustedRef.current = true;
          return;
        }

        let merged: KlineBar[];
        if (useSinaExpand) {
          merged = chunk.bars;
        } else {
          merged = mergeKlineBars(
            chunk.bars.filter((b) => b.date < earliest),
            bars,
          );
        }

        const added = merged.length - bars.length;
        if (added <= 0) {
          exhaustedRef.current = true;
          return;
        }

        barsRef.current = merged;
        if (merged.length >= MAX_BARS) exhaustedRef.current = true;
        const next = patchCachedKline(symbol, merged);
        skipDataEffectRef.current = true;
        setData(next);
        applyChart(next, { preserveRange: true, added: added });
      })
      .catch(() => {
        exhaustedRef.current = true;
      })
      .finally(() => {
        loadingMoreRef.current = false;
        setLoadingMore(false);
      });
  }, [applyChart, symbol]);

  useEffect(() => {
    symbolRef.current = symbol;
    exhaustedRef.current = false;
    loadingMoreRef.current = false;
    initialPaintRef.current = true;
    visibleRangeRef.current = null;
    barsRef.current = [];

    const cached = getCachedKline(symbol);
    if (cached) {
      barsRef.current = cached.bars;
      setData(cached);
      setLoading(false);
      setError("");
    } else {
      setData(null);
      setLoading(true);
      setError("");
    }

    let cancelled = false;
    api
      .klineChart(symbol, INITIAL_DAYS)
      .then((d) => {
        if (cancelled) return;
        barsRef.current = d.bars;
        const chart = setCachedKline(symbol, d.bars);
        setData(chart);
        setError("");
      })
      .catch((e) => {
        if (!cancelled && !getCachedKline(symbol)) setError(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [symbol]);

  useLayoutEffect(() => {
    const dispose = () => {
      runtimeRef.current.mainChart?.remove();
      runtimeRef.current.subCharts.forEach((c) => c.remove());
      runtimeRef.current = {
        subCharts: [],
        mounted: [],
        maLines: new Map(),
        trendLines: [],
        aiOverlays: [],
      };
    };
    dispose();

    const { up: chartUp, down: chartDown } = readChartColors();
    const mainH = compact ? 252 : 328;
    const subH = compact ? 72 : 88;
    const rt = runtimeRef.current;
    let detachWheel: (() => void) | null = null;

    const mountSubChart = (
      el: HTMLDivElement | null,
      height: number,
      build: (chart: IChartApi) => void,
    ) => {
      if (!el) return;
      el.style.height = `${height}px`;
      const width = Math.max(paneWidth(el), 280);
      const chart = createChart(el, baseChartOptions(width, height));
      build(chart);
      rt.subCharts.push(chart);
      rt.mounted.push({ el, chart, h: height });
      chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (!range || syncingRangeRef.current) return;
        visibleRangeRef.current = range;
        syncVisibleRange(range, chart);
      });
    };

    if (mainRef.current) {
      mainRef.current.style.height = `${mainH}px`;
      const width = Math.max(paneWidth(mainRef.current), 280);
      const chart = createChart(mainRef.current, baseChartOptions(width, mainH));
      rt.mainChart = chart;
      rt.mounted.push({ el: mainRef.current, chart, h: mainH });
      const detachWheelHere = installWheelZoomNormalizer(mainRef.current);
      detachWheel = detachWheelHere;

      rt.candles = chart.addCandlestickSeries({
        upColor: chartUp,
        downColor: chartDown,
        borderVisible: false,
        wickUpColor: chartUp,
        wickDownColor: chartDown,
      });
      chart.priceScale("right").applyOptions({ scaleMargins: { top: 0.06, bottom: 0.28 } });
      rt.maLines = new Map();
      for (const period of selectedMa) {
        rt.maLines.set(
          period,
          chart.addLineSeries({
            color: MA_COLORS[period] ?? "#d4a017",
            lineWidth: 1,
            title: `MA${period}`,
          }),
        );
      }
      rt.volume = chart.addHistogramSeries({
        title: t("chart.volumeUnit"),
        priceFormat: { type: "volume" },
        priceScaleId: "",
      });
      rt.volume.priceScale().applyOptions({ scaleMargins: { top: 0.78, bottom: 0 } });
      applyChartEdgeAlignment(chart);

      chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (!range || syncingRangeRef.current) return;
        visibleRangeRef.current = range;
        syncVisibleRange(range, chart);
        if (range.from < LOAD_TRIGGER_BARS) requestMoreHistory();
      });
    }

    if (showMacd && macdRef.current && variant === "stock") {
      mountSubChart(macdRef.current, subH, (chart) => {
        rt.macdHist = chart.addHistogramSeries({ title: "MACD" });
        rt.macdLine = chart.addLineSeries({ color: "#5b9bd5", lineWidth: 1 });
        rt.macdSignal = chart.addLineSeries({ color: "#e8a838", lineWidth: 1 });
        applyChartEdgeAlignment(chart);
      });
    }

    if (showRsi && rsiRef.current && variant === "stock") {
      mountSubChart(rsiRef.current, subH, (chart) => {
        rt.rsi = chart.addLineSeries({
          color: "#9b7fd4",
          lineWidth: 1,
          title: "RSI",
        });
        applyChartEdgeAlignment(chart);
      });
    }

    const resizeAll = () => {
      rt.mounted.forEach(({ el, chart, h }) => {
        chart.resize(Math.max(paneWidth(el), 280), h);
      });
    };

    requestAnimationFrame(resizeAll);
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => resizeAll()) : null;
    if (ro && rootRef.current) ro.observe(rootRef.current);

    const snapshot = dataRef.current;
    if (snapshot?.bars.length && snapshot.symbol === symbol && rt.candles) {
      applyChart(snapshot, visibleRangeRef.current ? undefined : { initial: true });
    }

    return () => {
      ro?.disconnect();
      detachWheel?.();
      dispose();
    };
  }, [
    symbol,
    compact,
    variant,
    showMacd,
    showRsi,
    t,
    requestMoreHistory,
    applyChart,
    syncVisibleRange,
  ]);

  useEffect(() => {
    const rt = runtimeRef.current;
    const chart = rt.mainChart;
    if (!chart) return;

    for (const [period, series] of [...rt.maLines.entries()]) {
      if (!selectedMa.includes(period)) {
        chart.removeSeries(series);
        rt.maLines.delete(period);
      }
    }
    for (const period of selectedMa) {
      if (!rt.maLines.has(period)) {
        rt.maLines.set(
          period,
          chart.addLineSeries({
            color: MA_COLORS[period] ?? "#d4a017",
            lineWidth: 1,
            title: `MA${period}`,
          }),
        );
      }
    }

    const snapshot = dataRef.current;
    if (snapshot?.bars.length && snapshot.symbol === symbol && rt.candles) {
      applyChart(snapshot);
    }
  }, [selectedMa, symbol, applyChart]);

  useEffect(() => {
    const rt = runtimeRef.current;
    const chart = rt.mainChart;
    if (!chart) return;

    for (const series of rt.trendLines) chart.removeSeries(series);
    rt.trendLines = [];

    const snapshot = dataRef.current;
    if (!showTrend || variant !== "stock") return;
    if (!snapshot || snapshot.symbol !== symbol || snapshot.bars.length === 0) return;

    const { up, down } = readChartColors();
    for (const line of detectTrendLines(snapshot.bars)) {
      const support = line.kind === "support";
      const series = chart.addLineSeries({
        color: support ? up : down,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        title: support ? t("chart.trendSupport") : t("chart.trendResistance"),
        lastValueVisible: false,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      });
      series.setData([
        {
          time: barTime(snapshot.bars[line.startIndex].date),
          value: line.startPrice,
        },
        {
          time: barTime(snapshot.bars[line.endIndex].date),
          value: line.endPrice,
        },
      ]);
      rt.trendLines.push(series);
    }
    // showMacd/showRsi/compact/variant remount the chart, so re-apply lines then.
  }, [showTrend, data, symbol, variant, t, showMacd, showRsi, compact]);

  const [aiOverlays, setAiOverlays] = useState<ChartOverlaySet | null>(null);

  useEffect(() => subscribeChartOverlays(setAiOverlays), []);

  useEffect(() => {
    const rt = runtimeRef.current;
    const chart = rt.mainChart;
    if (!chart) return;
    for (const series of rt.aiOverlays) chart.removeSeries(series);
    rt.aiOverlays = [];
    if (!aiOverlays || aiOverlays.symbol !== symbol || variant !== "stock") return;
    const snapshot = dataRef.current;
    if (!snapshot || snapshot.symbol !== symbol || snapshot.bars.length === 0) return;
    const { up, down } = readChartColors();
    for (const overlay of aiOverlays.overlays) {
      if (overlay.kind === "level" && overlay.price != null) {
        // Horizontal reference level spanning the whole visible range.
        const support = overlay.side === "support";
        const series = chart.addLineSeries({
          color: support ? up : down,
          lineWidth: 2,
          lineStyle: LineStyle.Solid,
          title: `${t("overlays.level")} · AI`,
          lastValueVisible: false,
          priceLineVisible: false,
          crosshairMarkerVisible: false,
        });
        const first = barTime(snapshot.bars[0].date);
        const last = barTime(snapshot.bars[snapshot.bars.length - 1].date);
        series.setData([
          { time: first, value: overlay.price },
          { time: last, value: overlay.price },
        ]);
        rt.aiOverlays.push(series);
        continue;
      }
      if (overlay.kind !== "trend" || !overlay.a || !overlay.b) continue;
      const support = overlay.side === "support";
      const series = chart.addLineSeries({
        color: support ? up : down,
        lineWidth: 2,
        lineStyle: LineStyle.SparseDotted,
        title: `${support ? t("chart.trendSupport") : t("chart.trendResistance")} · AI`,
        lastValueVisible: false,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      });
      series.setData([
        { time: barTime(overlay.a.time), value: overlay.a.price },
        { time: barTime(overlay.b.time), value: overlay.b.price },
      ]);
      rt.aiOverlays.push(series);
    }
  }, [aiOverlays, symbol, variant, t, showMacd, showRsi, compact, data]);

  useEffect(() => {
    if (skipDataEffectRef.current) {
      skipDataEffectRef.current = false;
      return;
    }
    if (!data || data.bars.length === 0 || loading) return;
    if (data.symbol !== symbol) return;
    if (!runtimeRef.current.candles) return;
    applyChart(data, initialPaintRef.current ? { initial: true } : undefined);
  }, [data, loading, applyChart, symbol]);

  const maLabel =
    selectedMa.length > 0
      ? selectedMa
          .slice()
          .sort((a, b) => a - b)
          .map((p) => `MA${p}`)
          .join(", ")
      : t("chart.ma");

  function toggleMaPeriod(period: number) {
    setSelectedMa((prev) => {
      if (prev.includes(period)) {
        if (prev.length === 1) return prev;
        return prev.filter((p) => p !== period);
      }
      return [...prev, period].sort((a, b) => a - b);
    });
  }

  return (
    <div ref={rootRef} className={`market-chart${compact ? " market-chart-compact" : ""}`}>
      {variant === "stock" && (
        <div className="market-chart-toggles">
          <button
            type="button"
            className={`chart-toggle-btn${showMacd ? " active" : ""}`}
            onClick={() => setShowMacd((v) => !v)}
            disabled={loading || !!error}
          >
            {t("chart.macd")}
          </button>
          <button
            type="button"
            className={`chart-toggle-btn${showRsi ? " active" : ""}`}
            onClick={() => setShowRsi((v) => !v)}
            disabled={loading || !!error}
          >
            {t("chart.rsi")}
          </button>
          <button
            type="button"
            className={`chart-toggle-btn${showTrend ? " active" : ""}`}
            onClick={() => setShowTrend((v) => !v)}
            disabled={loading || !!error}
          >
            {t("chart.trend")}
          </button>
          {loadingMore && (
            <span className="muted market-chart-loading-more">{t("chart.loadingMore")}</span>
          )}
        </div>
      )}
      {loading && !data && <p className="muted market-chart-status">{t("chart.loading")}</p>}
      {!loading && error && !data && (
        <p className="muted market-chart-status">
          {t("chart.error")}: {error}
        </p>
      )}
      {!loading && !error && data?.bars.length === 0 && (
        <p className="muted market-chart-status">{t("chart.empty")}</p>
      )}
      {(data || !error) && (
        <>
          <div className="market-chart-stage">
            <div className="market-chart-axis-y" aria-hidden="true">
              {t("chart.priceUnit")}
            </div>
            <div className="market-chart-stage-main">
              <div className="market-chart-pane-head">
                <span className="market-chart-pane-label">{t("chart.price")}</span>
                <div className="chart-ma-select">
                  <button
                    type="button"
                    className="chart-ma-trigger"
                    onClick={() => setMaMenuOpen((v) => !v)}
                    disabled={loading || !!error}
                    aria-expanded={maMenuOpen}
                  >
                    {t("chart.ma")} · {maLabel} ▾
                  </button>
                  {maMenuOpen && (
                    <div className="chart-ma-menu" role="menu">
                      {MA_PERIODS.map((period) => (
                        <label key={period} className="chart-ma-option">
                          <input
                            type="checkbox"
                            checked={selectedMa.includes(period)}
                            onChange={() => toggleMaPeriod(period)}
                          />
                          <span style={{ color: MA_COLORS[period] }}>
                            {t("chart.maOption", { period: String(period) })}
                          </span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
                <span className="market-chart-pane-meta muted">{t("chart.volumeUnit")}</span>
              </div>
              <div ref={mainRef} className="market-chart-pane market-chart-main" />
              <div className="market-chart-axis-x" aria-hidden="true">
                {t("chart.dateAxis")}
              </div>
            </div>
          </div>
          {variant === "stock" && showMacd && (
            <div className="market-chart-stage market-chart-stage-sub">
              <div className="market-chart-axis-y muted" aria-hidden="true">
                {t("chart.macd")}
              </div>
              <div className="market-chart-stage-main">
                <div ref={macdRef} className="market-chart-pane" />
                <div className="market-chart-axis-x muted" aria-hidden="true">
                  {t("chart.dateAxis")}
                </div>
              </div>
            </div>
          )}
          {variant === "stock" && showRsi && (
            <div className="market-chart-stage market-chart-stage-sub">
              <div className="market-chart-axis-y muted" aria-hidden="true">
                {t("chart.rsi")}
              </div>
              <div className="market-chart-stage-main">
                <div ref={rsiRef} className="market-chart-pane" />
                <div className="market-chart-axis-x muted" aria-hidden="true">
                  {t("chart.dateAxis")}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/** @deprecated Use MarketChart — kept for existing imports. */
export function StockChart(props: Omit<MarketChartProps, "variant">) {
  return <MarketChart {...props} variant="stock" />;
}
