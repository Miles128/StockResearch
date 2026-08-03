import {
  ColorType,
  type DeepPartial,
  type ChartOptions,
} from "lightweight-charts";

function cssVar(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
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

export function baseChartOptions(
  width: number,
  height: number,
): DeepPartial<ChartOptions> {
  const { textColor, gridColor } = readChartTheme();
  return {
    width: Math.max(width, 1),
    height,
    layout: {
      background: { type: ColorType.Solid, color: "transparent" },
      textColor,
      attributionLogo: false,
    },
    grid: { vertLines: { color: gridColor }, horzLines: { color: gridColor } },
    rightPriceScale: {
      visible: true,
      borderVisible: true,
      borderColor: gridColor,
      minimumWidth: 52,
    },
    leftPriceScale: {
      visible: false,
    },
    timeScale: {
      visible: true,
      borderVisible: true,
      borderColor: gridColor,
      fixLeftEdge: false,
      fixRightEdge: true,
      rightOffset: 2,
      timeVisible: true,
      secondsVisible: false,
    },
    handleScroll: {
      mouseWheel: true,
      pressedMouseMove: true,
      horzTouchDrag: true,
      vertTouchDrag: false,
    },
    handleScale: {
      axisPressedMouseMove: { time: true, price: true },
      mouseWheel: true,
      pinch: true,
    },
  };
}

export function applyChartEdgeAlignment(chart: {
  timeScale: () => { applyOptions: (opts: object) => void };
}) {
  chart.timeScale().applyOptions({
    fixRightEdge: true,
    rightOffset: 2,
  });
}
