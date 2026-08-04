import { useEffect, useState } from "react";
import { api, type SentimentData } from "./api";
import { useI18n } from "./i18n";

interface SentimentGaugeProps {
  /** market | sector | stock */
  variant: "market" | "sector" | "stock";
  /** sector name (for variant=sector) */
  sectorName?: string;
  /** stock symbol (for variant=stock) */
  symbol?: string;
  /** stock name (for variant=stock) */
  name?: string;
  /** compact mode for inline display */
  compact?: boolean;
  /** PRD §七: UI 轮询默认关。开启时按间隔轮询。 */
  pollingEnabled?: boolean;
  pollingIntervalMs?: number;
}

export function SentimentGauge({
  variant,
  sectorName,
  symbol,
  name,
  compact,
  pollingEnabled = false,
  pollingIntervalMs = 5 * 60 * 1000,
}: SentimentGaugeProps) {
  const { t } = useI18n();
  const [data, setData] = useState<SentimentData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const fetchSentiment = async () => {
      setLoading(true);
      try {
        let result: SentimentData | null = null;
        if (variant === "market") {
          result = await api.marketSentiment();
        } else if (variant === "sector" && sectorName) {
          result = await api.sectorSentiment(sectorName);
        } else if (variant === "stock" && symbol) {
          result = await api.stockSentiment(symbol, name);
        }
        if (!cancelled && result) {
          setData(result);
        }
      } catch {
        // silent fail — sentiment is supplementary
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void fetchSentiment();
    if (!pollingEnabled) return;
    const timer = window.setInterval(() => void fetchSentiment(), pollingIntervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [variant, sectorName, symbol, name, pollingEnabled, pollingIntervalMs]);

  if (loading && !data) {
    return compact ? (
      <span className="muted sentiment-compact">{t("sentiment.loading")}</span>
    ) : (
      <p className="muted">{t("sentiment.loading")}</p>
    );
  }

  if (!data) {
    return compact ? (
      <span className="muted sentiment-compact">—</span>
    ) : (
      <p className="muted">{t("sentiment.unavailable")}</p>
    );
  }

  const scoreClass =
    data.score <= 20
      ? "fear"
      : data.score <= 40
        ? "caution"
        : data.score <= 60
          ? "neutral"
          : data.score <= 80
            ? "optimism"
            : "greed";

  if (compact) {
    return (
      <span className={`sentiment-compact sentiment-${scoreClass}`} title={data.label}>
        {data.label} {data.score}
      </span>
    );
  }

  return (
    <div className="sentiment-gauge">
      <div className="sentiment-gauge-bar">
        <div className="sentiment-gauge-track">
          <div
            className={`sentiment-gauge-fill sentiment-${scoreClass}`}
            style={{ width: `${data.score}%` }}
          />
        </div>
        <span className={`sentiment-gauge-score mono sentiment-${scoreClass}`}>{data.score}</span>
      </div>
      <span className="sentiment-gauge-label">{data.label}</span>
      {data.drivers.length > 0 && (
        <ul className="sentiment-drivers">
          {data.drivers.map((d, i) => (
            <li key={i} className={`sentiment-driver sentiment-driver-${d.impact}`}>
              <span className="sentiment-driver-label">{d.label}</span>
              <span className="sentiment-driver-value">{d.value}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
