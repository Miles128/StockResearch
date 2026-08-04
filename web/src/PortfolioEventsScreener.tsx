/**
 * Portfolio event calendar (earnings / lockup) + factor screener sections.
 *
 * Two independent exports:
 * - PortfolioEventsSection  → 组合事件日历（用于“今日关注”组合驾驶舱）
 * - FactorScreenerSection  → 全市场因子筛选（用于“市场”Tab）
 */

import { useEffect, useState } from "react";
import { api, type PortfolioEvents, type ScreenCondition, type ScreenResult } from "./api";
import { CollapsibleSection } from "./CollapsibleSection";
import { signedClass } from "./holdingDisplay";
import { useI18n } from "./i18n";

const EVENT_DAYS = 45;

type PresetKey = "lowVal" | "momentum" | "lowVol" | "combo";

const PRESET_ORDER: PresetKey[] = ["lowVal", "momentum", "lowVol", "combo"];

const PRESET_CONDITIONS: Record<PresetKey, ScreenCondition[]> = {
  lowVal: [{ key: "pe_percentile", op: "<=", value: 30 }],
  momentum: [{ key: "momentum_20d", op: ">", value: 0 }],
  lowVol: [{ key: "volatility_20d", op: "<=", value: 30 }],
  combo: [
    { key: "pe_percentile", op: "<=", value: 30 },
    { key: "momentum_20d", op: ">", value: 0 },
  ],
};

const PRESET_LABEL_KEYS: Record<PresetKey, string> = {
  lowVal: "portfolio.screenPresetLowVal",
  momentum: "portfolio.screenPresetMomentum",
  lowVol: "portfolio.screenPresetLowVol",
  combo: "portfolio.screenPresetCombo",
};

const FACTOR_LABEL_KEYS: Record<string, string> = {
  momentum_20d: "portfolio.screenFactorMom",
  volatility_20d: "portfolio.screenFactorVol",
  pe_percentile: "portfolio.screenFactorPe",
};

/** 组合事件日历：未来 N 天内持仓/自选的财报、解禁日程。 */
export function PortfolioEventsSection({ trigger = "" }: { trigger?: string }) {
  const { t } = useI18n();
  const [events, setEvents] = useState<PortfolioEvents | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .portfolioEvents(EVENT_DAYS)
      .then((data) => {
        if (alive) setEvents(data);
      })
      .catch(() => {
        if (alive) setEvents(null);
      });
    return () => {
      alive = false;
    };
  }, [trigger]);

  const eventSummary =
    events && events.events.length > 0 ? (
      <span className="mono ledger-events-count">{events.events.length}</span>
    ) : undefined;

  return (
    <CollapsibleSection title={t("portfolio.eventsTitle")} summary={eventSummary} defaultCollapsed>
      {events && events.events.length > 0 ? (
        <ul className="ledger-events">
          {events.events.map((ev) => (
            <li key={`${ev.kind}-${ev.symbol}-${ev.event_date}`} className="ledger-event-row">
              <span className="mono ledger-event-date">{ev.event_date.slice(5)}</span>
              <span className={`ledger-event-kind ${ev.kind}`}>
                {ev.kind === "earnings"
                  ? t("portfolio.eventsEarnings")
                  : t("portfolio.eventsLockup")}
              </span>
              <span className="ledger-event-name" title={ev.detail || ev.name}>
                {ev.name}
              </span>
              <span className="muted ledger-event-detail">{ev.detail || ""}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted flat-empty">
          {events ? events.message || t("portfolio.eventsEmpty") : t("portfolio.eventsEmpty")}
        </p>
      )}
      {events?.partial && events.message && events.events.length > 0 && (
        <p className="muted ledger-perf-basis">{events.message}</p>
      )}
    </CollapsibleSection>
  );
}

/** 因子筛选：预设条件扫描全市场（持仓/自选高亮），用于“市场”Tab。 */
export function FactorScreenerSection() {
  const { t } = useI18n();
  const [screen, setScreen] = useState<ScreenResult | null>(null);
  const [preset, setPreset] = useState<PresetKey | null>(null);
  const [screening, setScreening] = useState(false);

  const runPreset = (key: PresetKey) => {
    setPreset(key);
    setScreening(true);
    api
      .portfolioScreen({ universe: "all", conditions: PRESET_CONDITIONS[key] })
      .then((data) => setScreen(data))
      .catch(() => setScreen(null))
      .finally(() => setScreening(false));
  };

  return (
    <CollapsibleSection title={t("portfolio.screenTitle")} defaultCollapsed>
      <div className="ledger-screen-presets">
        {PRESET_ORDER.map((key) => (
          <button
            key={key}
            type="button"
            className={`ledger-screen-chip${preset === key ? " active" : ""}`}
            onClick={() => runPreset(key)}
            disabled={screening}
          >
            {t(PRESET_LABEL_KEYS[key])}
          </button>
        ))}
      </div>
      {screening && <p className="muted flat-empty">…</p>}
      {!screening && screen && (
        <>
          {screen.hits.length > 0 ? (
            <ul className="ledger-screen-hits">
              {screen.hits.map((hit) => (
                <li key={hit.symbol} className="ledger-screen-hit">
                  <span className="ledger-screen-hit-name" title={hit.sector || hit.name}>
                    {hit.name}
                    <i className={`ledger-screen-hit-scope ${hit.scope}`} aria-hidden="true" />
                  </span>
                  <span className="mono ledger-screen-hit-factors">
                    {Object.entries(hit.factors).map(([key, value]) => (
                      <span key={key} className="ledger-screen-hit-factor">
                        <span className="lists-metric-label">
                          {t(FACTOR_LABEL_KEYS[key] || key)}
                        </span>{" "}
                        <b className={key === "momentum_20d" ? signedClass(value) : ""}>
                          {value != null ? `${value.toFixed(1)}%` : "—"}
                        </b>
                      </span>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted flat-empty">{screen.message || t("portfolio.screenEmpty")}</p>
          )}
          <p className="muted ledger-perf-basis">
            {t("portfolio.screenScanned")} {screen.scanned}
            {screen.skipped > 0 ? ` · ${t("portfolio.screenSkipped")} ${screen.skipped}` : ""}
            {screen.message ? ` · ${screen.message}` : ""}
          </p>
        </>
      )}
      {!screening && !screen && <p className="muted flat-empty">{t("portfolio.screenIdle")}</p>}
    </CollapsibleSection>
  );
}
