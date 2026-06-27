import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ColorType, createChart, type IChartApi } from "lightweight-charts";
import { api, type KlineChart } from "./api";
import { useI18n } from "./i18n";

interface StockChartProps {
  symbol: string;
  days?: number;
  compact?: boolean;
}

export function StockChart({ symbol, days = 60, compact = false }: StockChartProps) {
  const { t } = useI18n();
  const priceRef = useRef<HTMLDivElement>(null);
  const macdRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);
  const chartsRef = useRef<IChartApi[]>([]);
  const [data, setData] = useState<KlineChart | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Fetch K-line data
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

  // Render charts once data is available and DOM refs are attached
  useLayoutEffect(() => {
    if (!data) return;

    const dispose = () => {
      chartsRef.current.forEach((c) => c.remove());
      chartsRef.current = [];
    };

    dispose();

    const textColor =
      getComputedStyle(document.documentElement).getPropertyValue("--bbg-text").trim() || "#e8e8e8";
    const gridColor =
      getComputedStyle(document.documentElement).getPropertyValue("--bbg-border").trim() || "#333";
    const common = {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor,
      },
      grid: { vertLines: { color: gridColor }, horzLines: { color: gridColor } },
      rightPriceScale: { borderColor: gridColor },
      timeScale: { borderColor: gridColor },
      autoSize: true,
    };

    if (priceRef.current) {
      const h = compact ? 180 : 240;
      priceRef.current.style.height = `${h}px`;
      const chart = createChart(priceRef.current, { ...common, height: h });
      chartsRef.current.push(chart);
      const candles = chart.addCandlestickSeries({
        upColor: "#3d9a5d",
        downColor: "#c45c5c",
        borderVisible: false,
        wickUpColor: "#3d9a5d",
        wickDownColor: "#c45c5c",
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

    if (macdRef.current) {
      const h = compact ? 72 : 96;
      macdRef.current.style.height = `${h}px`;
      const chart = createChart(macdRef.current, { ...common, height: h });
      chartsRef.current.push(chart);
      const hist = chart.addHistogramSeries({ title: "MACD" });
      hist.setData(
        data.bars
          .map((b, i) => ({
            time: b.date,
            value: data.indicators.macd_histogram[i] ?? 0,
            color: (data.indicators.macd_histogram[i] ?? 0) >= 0 ? "#3d9a5d88" : "#c45c5c88",
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

    if (rsiRef.current) {
      const h = compact ? 72 : 96;
      rsiRef.current.style.height = `${h}px`;
      const chart = createChart(rsiRef.current, { ...common, height: h });
      chartsRef.current.push(chart);
      const rsi = chart.addLineSeries({ color: "#9b7fd4", lineWidth: 1, title: "RSI" });
      rsi.setData(
        data.bars
          .map((b, i) => ({ time: b.date, value: data.indicators.rsi[i] }))
          .filter((p): p is { time: string; value: number } => p.value != null),
      );
      chart.timeScale().fitContent();
    }

    return () => {
      dispose();
    };
  }, [data, compact]);

  if (loading) return <p className="muted stock-chart-status">{t("chart.loading")}</p>;
  if (error) return <p className="muted stock-chart-status">{t("chart.error")}: {error}</p>;

  return (
    <div className={`stock-chart${compact ? " stock-chart-compact" : ""}`}>
      <div className="stock-chart-pane-label">{t("chart.price")}</div>
      <div ref={priceRef} className="stock-chart-pane" />
      <div className="stock-chart-pane-label">{t("chart.macd")}</div>
      <div ref={macdRef} className="stock-chart-pane" />
      <div className="stock-chart-pane-label">{t("chart.rsi")}</div>
      <div ref={rsiRef} className="stock-chart-pane" />
    </div>
  );
}
