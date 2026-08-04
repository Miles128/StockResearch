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
  boll_mid: (number | null)[];
  boll_upper: (number | null)[];
  boll_lower: (number | null)[];
  atr: (number | null)[];
  kdj_k: (number | null)[];
  kdj_d: (number | null)[];
  kdj_j: (number | null)[];
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

export function bollSeries(
  closes: number[],
  window = 20,
  numStd = 2,
): {
  mid: (number | null)[];
  upper: (number | null)[];
  lower: (number | null)[];
} {
  const n = closes.length;
  const mid: (number | null)[] = new Array(n).fill(null);
  const upper: (number | null)[] = new Array(n).fill(null);
  const lower: (number | null)[] = new Array(n).fill(null);
  if (window < 2 || n < window) return { mid, upper, lower };
  for (let i = window - 1; i < n; i += 1) {
    let sum = 0;
    for (let j = i - window + 1; j <= i; j += 1) sum += closes[j];
    const mean = sum / window;
    let varSum = 0;
    for (let j = i - window + 1; j <= i; j += 1) varSum += (closes[j] - mean) ** 2;
    const std = Math.sqrt(varSum / window);
    mid[i] = Math.round(mean * 10000) / 10000;
    upper[i] = Math.round((mean + numStd * std) * 10000) / 10000;
    lower[i] = Math.round((mean - numStd * std) * 10000) / 10000;
  }
  return { mid, upper, lower };
}

export function atrSeries(
  highs: number[],
  lows: number[],
  closes: number[],
  period = 14,
): (number | null)[] {
  const n = closes.length;
  const out: (number | null)[] = new Array(n).fill(null);
  if (n < 2 || highs.length !== n || lows.length !== n || period < 1) return out;
  const trs: number[] = new Array(n).fill(0);
  trs[0] = highs[0] - lows[0];
  for (let i = 1; i < n; i += 1) {
    trs[i] = Math.max(
      highs[i] - lows[i],
      Math.abs(highs[i] - closes[i - 1]),
      Math.abs(lows[i] - closes[i - 1]),
    );
  }
  if (n <= period) return out;
  let atr = trs.slice(1, period + 1).reduce((a, b) => a + b, 0) / period;
  out[period] = Math.round(atr * 10000) / 10000;
  for (let i = period + 1; i < n; i += 1) {
    atr = (atr * (period - 1) + trs[i]) / period;
    out[i] = Math.round(atr * 10000) / 10000;
  }
  return out;
}

export function kdjSeries(
  highs: number[],
  lows: number[],
  closes: number[],
  n = 9,
  m1 = 3,
  m2 = 3,
): { k: (number | null)[]; d: (number | null)[]; j: (number | null)[] } {
  const length = closes.length;
  const empty: (number | null)[] = new Array(length).fill(null);
  if (length < n || highs.length !== length || lows.length !== length) {
    return { k: empty.slice(), d: empty.slice(), j: empty.slice() };
  }
  const kLine: (number | null)[] = new Array(length).fill(null);
  const dLine: (number | null)[] = new Array(length).fill(null);
  const jLine: (number | null)[] = new Array(length).fill(null);
  let kPrev = 50;
  let dPrev = 50;
  for (let i = n - 1; i < length; i += 1) {
    let hi = highs[i];
    let lo = lows[i];
    for (let j = i - n + 1; j <= i; j += 1) {
      hi = Math.max(hi, highs[j]);
      lo = Math.min(lo, lows[j]);
    }
    const denom = hi - lo;
    const rsv = denom <= 0 ? 50 : ((closes[i] - lo) / denom) * 100;
    kPrev = (rsv + (m1 - 1) * kPrev) / m1;
    dPrev = (kPrev + (m2 - 1) * dPrev) / m2;
    kLine[i] = Math.round(kPrev * 100) / 100;
    dLine[i] = Math.round(dPrev * 100) / 100;
    jLine[i] = Math.round((3 * kPrev - 2 * dPrev) * 100) / 100;
  }
  return { k: kLine, d: dLine, j: jLine };
}

export function buildIndicators(
  closes: number[],
  highs?: number[],
  lows?: number[],
): KlineIndicators {
  const macd = macdSeries(closes);
  const boll = bollSeries(closes);
  const hi = highs ?? closes;
  const lo = lows ?? closes;
  const kdj = kdjSeries(hi, lo, closes);
  return {
    ma20: maSeries(closes, 20),
    rsi: rsiSeries(closes),
    macd: macd.macd,
    macd_signal: macd.signal,
    macd_histogram: macd.histogram,
    boll_mid: boll.mid,
    boll_upper: boll.upper,
    boll_lower: boll.lower,
    atr: atrSeries(hi, lo, closes),
    kdj_k: kdj.k,
    kdj_d: kdj.d,
    kdj_j: kdj.j,
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
