import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createChart, type IChartApi } from "lightweight-charts";
import { api, type KlineChart } from "./api";
import { useI18n } from "./i18n";
import { baseChartOptions, readChartColors } from "./ui/chartTheme";

export type MarketChartVariant = "stock" | "index";

interface MarketChartProps {
  symbol: string;
  days?: number;
  compact?: boolean;
  variant?: MarketChartVariant;
}

/** Unified K-line chart: stock (candles + MACD + RSI) or index (candles + volume). */
export function MarketChart({ symbol, days = 60, compact = false, variant = "stock" }: MarketChartProps) {
  const { t } = useI18n();
  const priceRef = useRef<HTMLDivElement>(null);
  const secondaryRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);
  const chartsRef = useRef<IChartApi[]>([]);
  const [data, setData] = useState<KlineChart | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setData(null);

    api
      .klineChart(symbol, days)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [symbol, days]);

  useLayoutEffect(() => {
    if (!data) return;

    const dispose = () => {
      chartsRef.current.forEach((c) => c.remove());
      chartsRef.current = [];
    };

    dispose();

    const { up: chartUp, down: chartDown } = readChartColors();
    const priceH = compact ? 180 : 240;
    const subH = compact ? 72 : 96;

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
    }

    if (secondaryRef.current) {
      secondaryRef.current.style.height = `${subH}px`;
      const chart = createChart(secondaryRef.current, baseChartOptions(subH));
      chartsRef.current.push(chart);

      if (variant === "index") {
        const volume = chart.addHistogramSeries({ title: t("chart.volume") });
        volume.setData(
          data.bars.map((b) => ({
            time: b.date,
            value: b.volume,
            color: b.close >= b.open ? `${chartUp}88` : `${chartDown}88`,
          })),
        );
      } else {
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
      }
      chart.timeScale().fitContent();
    }

    if (variant === "stock" && rsiRef.current) {
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
  }, [data, compact, variant, t]);

  if (loading) return <p className="muted market-chart-status">{t("chart.loading")}</p>;
  if (error) return <p className="muted market-chart-status">{t("chart.error")}: {error}</p>;

  return (
    <div className={`market-chart${compact ? " market-chart-compact" : ""}`}>
      <div className="market-chart-pane-label">{t("chart.price")}</div>
      <div ref={priceRef} className="market-chart-pane" />
      <div className="market-chart-pane-label">
        {variant === "index" ? t("chart.volume") : t("chart.macd")}
      </div>
      <div ref={secondaryRef} className="market-chart-pane" />
      {variant === "stock" && (
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
