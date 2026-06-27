import { ColorType, type DeepPartial, type ChartOptions } from "lightweight-charts";

function cssVar(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

export function readChartColors() {
  return {
    up: cssVar("--chart-up", "#34d399"),
    down: cssVar("--chart-down", "#f87171"),
    text: cssVar("--bbg-text", "#e8e8e8"),
    grid: cssVar("--bbg-border", "#333"),
  };
}

export function readChartTheme() {
  const { text, grid } = readChartColors();
  return { textColor: text, gridColor: grid };
}

export function baseChartOptions(height: number): DeepPartial<ChartOptions> {
  const { textColor, gridColor } = readChartTheme();
  return {
    height,
    layout: {
      background: { type: ColorType.Solid, color: "transparent" },
      textColor,
    },
    grid: { vertLines: { color: gridColor }, horzLines: { color: gridColor } },
    rightPriceScale: { borderColor: gridColor },
    timeScale: { borderColor: gridColor },
    autoSize: true,
  };
}
