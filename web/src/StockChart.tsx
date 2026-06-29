import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createChart, type IChartApi, type LogicalRange } from "lightweight-charts";
import { api, type KlineChart } from "./api";
import { useI18n } from "./i18n";
import { baseChartOptions, readChartColors } from "./ui/chartTheme";

export type MarketChartVariant = "stock" | "index";

const INITIAL_DAYS = 90;
const LOAD_CHUNK = 90;
const MAX_DAYS = 500;

interface MarketChartProps {
  symbol: string;
  compact?: boolean;
  variant?: MarketChartVariant;
}

/** Unified K-line chart with volume, optional MACD/RSI, and scroll-back loading. */
export function MarketChart({ symbol, compact = false, variant = "stock" }: MarketChartProps) {
  const { t } = useI18n();
  const priceRef = useRef<HTMLDivElement>(null);
  const volumeRef = useRef<HTMLDivElement>(null);
  const macdRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);
  const chartsRef = useRef<IChartApi[]>([]);
  const barCountRef = useRef(0);
  const visibleRangeRef = useRef<LogicalRange | null>(null);
  const fetchDaysRef = useRef(INITIAL_DAYS);
  const loadingMoreRef = useRef(false);
  const exhaustedRef = useRef(false);

  const [data, setData] = useState<KlineChart | null>(null);
  const [fetchDays, setFetchDays] = useState(INITIAL_DAYS);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [showMacd, setShowMacd] = useState(false);
  const [showRsi, setShowRsi] = useState(false);

  useEffect(() => {
    fetchDaysRef.current = INITIAL_DAYS;
    exhaustedRef.current = false;
    barCountRef.current = 0;
    setFetchDays(INITIAL_DAYS);
  }, [symbol]);

  useEffect(() => {
    let cancelled = false;
    const isInitial = fetchDays === INITIAL_DAYS;
    if (isInitial) {
      setLoading(true);
      setError("");
      setData(null);
    } else {
      setLoadingMore(true);
      loadingMoreRef.current = true;
    }

    api
      .klineChart(symbol, fetchDays)
      .then((d) => {
        if (cancelled) return;
        const prevCount = barCountRef.current;
        const added = d.bars.length - prevCount;
        barCountRef.current = d.bars.length;
        if (!isInitial && added <= 0) {
          exhaustedRef.current = true;
        }
        if (fetchDays >= MAX_DAYS) {
          exhaustedRef.current = true;
        }
        setData(d);
        if (!isInitial && added > 0) {
          const range = visibleRangeRef.current;
          if (range) {
            requestAnimationFrame(() => {
              const chart = chartsRef.current[0];
              if (!chart) return;
              chart.timeScale().setVisibleLogicalRange({
                from: range.from + added,
                to: range.to + added,
              });
            });
          }
        }
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      })
      .finally(() => {
        if (cancelled) return;
        if (isInitial) setLoading(false);
        else {
          setLoadingMore(false);
          loadingMoreRef.current = false;
        }
      });

    return () => {
      cancelled = true;
    };
  }, [symbol, fetchDays]);

  function requestMoreHistory() {
    if (loadingMoreRef.current || exhaustedRef.current || fetchDaysRef.current >= MAX_DAYS) return;
    fetchDaysRef.current = Math.min(fetchDaysRef.current + LOAD_CHUNK, MAX_DAYS);
    setFetchDays(fetchDaysRef.current);
  }

  useLayoutEffect(() => {
    if (!data) return;

    const dispose = () => {
      chartsRef.current.forEach((c) => c.remove());
      chartsRef.current = [];
    };

    dispose();

    const { up: chartUp, down: chartDown } = readChartColors();
    const priceH = compact ? 180 : 240;
    const subH = compact ? 72 : 88;

    if (priceRef.current) {
      priceRef.current.style.height = `${priceH}px`;
      const chart = createChart(priceRef.current, baseChartOptions(priceH));
      chartsRef.current.push(chart);
      const candles = chart.addCandlestickSeries({
        upColor: chartUp,
        downColor: chartDown,
        borderVisible: false,
        wickUpColor: chartUp,
        wickDownColor: chartDown,
      });
      candles.setData(
        data.bars.map((b) => ({
          time: b.date,
          open: b.open,
          high: b.high,
          low: b.low,
          close: b.close,
        })),
      );
      const ma = chart.addLineSeries({ color: "#d4a017", lineWidth: 1, title: "MA20" });
      ma.setData(
        data.bars
          .map((b, i) => ({ time: b.date, value: data.indicators.ma20[i] }))
          .filter((p): p is { time: string; value: number } => p.value != null),
      );
      chart.timeScale().fitContent();
      chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (!range) return;
        visibleRangeRef.current = range;
        if (range.from < 12) requestMoreHistory();
      });
    }

    if (volumeRef.current) {
      volumeRef.current.style.height = `${subH}px`;
      const chart = createChart(volumeRef.current, baseChartOptions(subH));
      chartsRef.current.push(chart);
      const volume = chart.addHistogramSeries({ title: t("chart.volume") });
      volume.setData(
        data.bars.map((b) => ({
          time: b.date,
          value: b.volume,
          color: b.close >= b.open ? `${chartUp}88` : `${chartDown}88`,
        })),
      );
      chart.timeScale().fitContent();
    }

    if (showMacd && macdRef.current && variant === "stock") {
      macdRef.current.style.height = `${subH}px`;
      const chart = createChart(macdRef.current, baseChartOptions(subH));
      chartsRef.current.push(chart);
      const hist = chart.addHistogramSeries({ title: "MACD" });
      hist.setData(
        data.bars
          .map((b, i) => ({
            time: b.date,
            value: data.indicators.macd_histogram[i] ?? 0,
            color: (data.indicators.macd_histogram[i] ?? 0) >= 0 ? `${chartUp}88` : `${chartDown}88`,
          }))
          .filter((_, i) => data.indicators.macd_histogram[i] != null),
      );
      const macdLine = chart.addLineSeries({ color: "#5b9bd5", lineWidth: 1 });
      macdLine.setData(
        data.bars
          .map((b, i) => ({ time: b.date, value: data.indicators.macd[i] }))
          .filter((p): p is { time: string; value: number } => p.value != null),
      );
      const signal = chart.addLineSeries({ color: "#e8a838", lineWidth: 1 });
      signal.setData(
        data.bars
          .map((b, i) => ({ time: b.date, value: data.indicators.macd_signal[i] }))
          .filter((p): p is { time: string; value: number } => p.value != null),
      );
      chart.timeScale().fitContent();
    }

    if (showRsi && rsiRef.current && variant === "stock") {
      rsiRef.current.style.height = `${subH}px`;
      const chart = createChart(rsiRef.current, baseChartOptions(subH));
      chartsRef.current.push(chart);
      const rsi = chart.addLineSeries({ color: "#9b7fd4", lineWidth: 1, title: "RSI" });
      rsi.setData(
        data.bars
          .map((b, i) => ({ time: b.date, value: data.indicators.rsi[i] }))
          .filter((p): p is { time: string; value: number } => p.value != null),
      );
      chart.timeScale().fitContent();
    }

    return dispose;
  }, [data, compact, variant, t, showMacd, showRsi]);

  if (loading) return <p className="muted market-chart-status">{t("chart.loading")}</p>;
  if (error) return <p className="muted market-chart-status">{t("chart.error")}: {error}</p>;

  return (
    <div className={`market-chart${compact ? " market-chart-compact" : ""}`}>
      {variant === "stock" && (
        <div className="market-chart-toggles">
          <button
            type="button"
            className={`chart-toggle-btn${showMacd ? " active" : ""}`}
            onClick={() => setShowMacd((v) => !v)}
          >
            {t("chart.macd")}
          </button>
          <button
            type="button"
            className={`chart-toggle-btn${showRsi ? " active" : ""}`}
            onClick={() => setShowRsi((v) => !v)}
          >
            {t("chart.rsi")}
          </button>
          {loadingMore && <span className="muted market-chart-loading-more">{t("chart.loadingMore")}</span>}
        </div>
      )}
      <div className="market-chart-pane-label">{t("chart.price")}</div>
      <div ref={priceRef} className="market-chart-pane" />
      <div className="market-chart-pane-label">{t("chart.volume")}</div>
      <div ref={volumeRef} className="market-chart-pane" />
      {variant === "stock" && showMacd && (
        <>
          <div className="market-chart-pane-label">{t("chart.macd")}</div>
          <div ref={macdRef} className="market-chart-pane" />
        </>
      )}
      {variant === "stock" && showRsi && (
        <>
          <div className="market-chart-pane-label">{t("chart.rsi")}</div>
          <div ref={rsiRef} className="market-chart-pane" />
        </>
      )}
    </div>
  );
}

/** @deprecated Use MarketChart — kept for existing imports. */
export function StockChart(props: Omit<MarketChartProps, "variant">) {
  return <MarketChart {...props} variant="stock" />;
}
