/** Map backend index names / symbols to i18n keys under `indices.*`. */

const NAME_TO_SYMBOL: Record<string, string> = {
  上证指数: "000001",
  上证: "000001",
  沪指: "000001",
  深证成指: "399001",
  深指: "399001",
  深证: "399001",
  创业板指: "399006",
  创业板: "399006",
  沪深300: "000300",
};

export function indexSymbolKey(
  symbol?: string,
  fallbackName?: string,
): string | null {
  if (symbol && /^\d{6}$/.test(symbol)) return symbol;
  if (fallbackName && NAME_TO_SYMBOL[fallbackName])
    return NAME_TO_SYMBOL[fallbackName];
  return null;
}

export function localizeIndexName(
  symbol: string | undefined,
  fallbackName: string,
  t: (key: string) => string,
): string {
  const key = indexSymbolKey(symbol, fallbackName);
  if (!key) return fallbackName;
  const i18nKey = `indices.${key}`;
  const translated = t(i18nKey);
  return translated !== i18nKey ? translated : fallbackName;
}

/** Keywords for matching market news to an index focus tab. */
export function indexSearchTerms(symbol?: string, name?: string): string[] {
  const terms = new Set<string>();
  if (symbol) terms.add(symbol);
  if (name) terms.add(name);
  for (const [label, sym] of Object.entries(NAME_TO_SYMBOL)) {
    if (sym === symbol || label === name) terms.add(label);
  }
  terms.add("大盘");
  terms.add("A股");
  terms.add("市场");
  terms.add("指数");
  return [...terms].filter(Boolean);
}
