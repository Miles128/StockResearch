/** Signed number display with A-share colors (up=green, down=red). */

export function signedClass(value: number | null | undefined): string {
  if (value == null || value === 0) return "";
  return value > 0 ? "up" : "down";
}

export function formatSignedPct(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function formatSignedMoney(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}¥${Math.abs(value).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatMoney(value: number | null | undefined, locale = "zh-CN"): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `¥${value.toLocaleString(locale, { maximumFractionDigits: 0 })}`;
}

export function formatPrice(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(2);
}

export function computeDailyPnlAmount(
  price: number | null | undefined,
  quantity: number,
  changePct: number | null | undefined,
): number | null {
  if (price == null || changePct == null || Number.isNaN(changePct)) return null;
  return Math.round(price * quantity * (changePct / 100) * 100) / 100;
}

export function formatHoldingDuration(buyDate: string | null | undefined): string {
  if (!buyDate) return "—";
  const start = new Date(buyDate);
  if (Number.isNaN(start.getTime())) return "—";
  const days = Math.max(1, Math.floor((Date.now() - start.getTime()) / 86_400_000));
  if (days < 30) return `${days}天`;
  if (days < 365) return `${Math.floor(days / 30)}月`;
  const years = days / 365;
  return years >= 2 ? `${years.toFixed(1)}年` : `${Math.floor(days / 30)}月`;
}

/** Prefer human-readable name; fall back to quote name when DB name is missing or equals symbol. */
export function displayStockName(
  symbol: string,
  storedName?: string | null,
  quoteName?: string | null,
): string {
  const stored = storedName?.trim();
  if (stored && stored !== symbol) return stored;
  const quoted = quoteName?.trim();
  if (quoted && quoted !== symbol) return quoted;
  return stored || quoted || symbol;
}
