/** Client-side OHLCV indicators — mirrors backend technical_indicators.py */

export interface KlineBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface KlineIndicators {
  ma20: (number | null)[];
  rsi: (number | null)[];
  macd: (number | null)[];
  macd_signal: (number | null)[];
  macd_histogram: (number | null)[];
}

function emaSeries(values: number[], period: number): (number | null)[] {
  if (!values.length) return [];
  const k = 2 / (period + 1);
  const out: (number | null)[] = [values[0]];
  let ema = values[0];
  for (let i = 1; i < values.length; i += 1) {
    ema = values[i] * k + ema * (1 - k);
    out.push(Math.round(ema * 10000) / 10000);
  }
  return out;
}

export function maSeries(closes: number[], window: number): (number | null)[] {
  const out: (number | null)[] = new Array(closes.length).fill(null);
  for (let i = window - 1; i < closes.length; i += 1) {
    let sum = 0;
    for (let j = i - window + 1; j <= i; j += 1) sum += closes[j];
    out[i] = Math.round((sum / window) * 10000) / 10000;
  }
  return out;
}

export function rsiSeries(closes: number[], period = 14): (number | null)[] {
  const out: (number | null)[] = new Array(closes.length).fill(null);
  if (closes.length < period + 1) return out;

  const gains: number[] = [];
  const losses: number[] = [];
  for (let i = 1; i < closes.length; i += 1) {
    const delta = closes[i] - closes[i - 1];
    gains.push(Math.max(delta, 0));
    losses.push(Math.max(-delta, 0));
  }

  let avgGain = gains.slice(0, period).reduce((a, b) => a + b, 0) / period;
  let avgLoss = losses.slice(0, period).reduce((a, b) => a + b, 0) / period;
  const idx = period;
  let rs = avgLoss ? avgGain / avgLoss : 100;
  out[idx] = Math.round((100 - 100 / (1 + rs)) * 100) / 100;

  for (let i = period + 1; i < closes.length; i += 1) {
    avgGain = (avgGain * (period - 1) + gains[i - 1]) / period;
    avgLoss = (avgLoss * (period - 1) + losses[i - 1]) / period;
    rs = avgLoss ? avgGain / avgLoss : 100;
    out[i] = Math.round((100 - 100 / (1 + rs)) * 100) / 100;
  }
  return out;
}

export function macdSeries(closes: number[]): {
  macd: (number | null)[];
  signal: (number | null)[];
  histogram: (number | null)[];
} {
  const n = closes.length;
  const empty: (number | null)[] = new Array(n).fill(null);
  if (n < 2) return { macd: empty, signal: empty, histogram: empty };

  const ema12 = emaSeries(closes, 12);
  const ema26 = emaSeries(closes, 26);
  const macdLine: (number | null)[] = new Array(n).fill(null);
  const macdValues: number[] = [];
  const macdIndices: number[] = [];

  for (let i = 0; i < n; i += 1) {
    const fast = ema12[i];
    const slow = ema26[i];
    if (fast == null || slow == null) continue;
    const val = Math.round((fast - slow) * 10000) / 10000;
    macdLine[i] = val;
    macdValues.push(val);
    macdIndices.push(i);
  }

  const signalLine: (number | null)[] = new Array(n).fill(null);
  if (macdValues.length) {
    const signalEma = emaSeries(macdValues, 9);
    macdIndices.forEach((barIdx, j) => {
      signalLine[barIdx] = signalEma[j] ?? null;
    });
  }

  const histogram: (number | null)[] = new Array(n).fill(null);
  for (let i = 0; i < n; i += 1) {
    const m = macdLine[i];
    const s = signalLine[i];
    if (m == null || s == null) continue;
    histogram[i] = Math.round((m - s) * 10000) / 10000;
  }

  return { macd: macdLine, signal: signalLine, histogram };
}

export function buildIndicators(closes: number[]): KlineIndicators {
  const macd = macdSeries(closes);
  return {
    ma20: maSeries(closes, 20),
    rsi: rsiSeries(closes),
    macd: macd.macd,
    macd_signal: macd.signal,
    macd_histogram: macd.histogram,
  };
}

export function mergeKlineBars(older: KlineBar[], existing: KlineBar[]): KlineBar[] {
  if (!older.length) return existing;
  if (!existing.length) return older;
  const seen = new Set(existing.map((b) => b.date));
  const prepend = older.filter((b) => !seen.has(b.date));
  if (!prepend.length) return existing;
  return [...prepend, ...existing].sort((a, b) => a.date.localeCompare(b.date));
}
