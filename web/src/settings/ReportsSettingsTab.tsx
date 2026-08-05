import { useEffect, useState } from "react";
import {
  api,
  type CompareTable,
  type EventStudy,
  type EventStudyBatch,
  type HypothesisVerify,
  type MemorySearchResult,
  type ReportPostHoc,
  type ResearchReportListItem,
  type ResearchTimeline,
  type SignalBacktest,
} from "../api";
import { useI18n } from "../i18n";

interface ReportsSettingsTabProps {
  reports: ResearchReportListItem[];
  backtest: SignalBacktest | null;
  memoryQuery: string;
  memoryHits: MemorySearchResult | null;
  onMemoryQueryChange: (value: string) => void;
  onMemorySearch: (query: string) => void;
}

export function ReportsSettingsTab({
  reports,
  backtest,
  memoryQuery,
  memoryHits,
  onMemoryQueryChange,
  onMemorySearch,
}: ReportsSettingsTabProps) {
  const { t, locale } = useI18n();
  const [postHocById, setPostHocById] = useState<
    Record<number, ReportPostHoc | "loading" | "error">
  >({});
  const [toolSymbol, setToolSymbol] = useState("600519");
  const [timelineSymbol, setTimelineSymbol] = useState("600519");
  const [timeline, setTimeline] = useState<ResearchTimeline | "loading" | "error" | null>(null);
  const [compareSymbols, setCompareSymbols] = useState("600519,000858");
  const [compare, setCompare] = useState<CompareTable | "loading" | "error" | null>(null);
  const [eventStudy, setEventStudy] = useState<EventStudy | "loading" | "error" | null>(null);
  const [eventBatch, setEventBatch] = useState<EventStudyBatch | "loading" | "error" | null>(null);
  const [hypothesis, setHypothesis] = useState<HypothesisVerify | "loading" | "error" | null>(null);
  const [presets, setPresets] = useState<Record<string, string>>({});
  const [rule, setRule] = useState("momentum_positive");
  const [batchStatus, setBatchStatus] = useState<string | null>(null);

  useEffect(() => {
    void api
      .hypothesisPresets()
      .then(setPresets)
      .catch(() => {});
  }, []);

  async function loadPostHoc(id: number) {
    setPostHocById((prev) => ({ ...prev, [id]: "loading" }));
    try {
      const result = await api.reportPostHoc(id);
      setPostHocById((prev) => ({ ...prev, [id]: result }));
    } catch {
      setPostHocById((prev) => ({ ...prev, [id]: "error" }));
    }
  }

  async function loadTimeline() {
    if (!/^\d{6}$/.test(timelineSymbol)) return;
    setTimeline("loading");
    try {
      setTimeline(await api.researchTimeline(timelineSymbol, true));
    } catch {
      setTimeline("error");
    }
  }

  async function runCompare() {
    const symbols = compareSymbols
      .split(/[,，\s]+/)
      .map((s) => s.trim())
      .filter((s) => /^\d{6}$/.test(s));
    if (!symbols.length) return;
    setCompare("loading");
    try {
      setCompare(await api.compareSymbols(symbols));
    } catch {
      setCompare("error");
    }
  }

  async function runEventStudy() {
    if (!/^\d{6}$/.test(toolSymbol)) return;
    setEventStudy("loading");
    try {
      setEventStudy(await api.eventStudy(toolSymbol, "earnings"));
    } catch {
      setEventStudy("error");
    }
  }

  async function runEventStudyBatch() {
    const symbols = compareSymbols
      .split(/[,，\s]+/)
      .map((s) => s.trim())
      .filter((s) => /^\d{6}$/.test(s))
      .slice(0, 8);
    if (!symbols.length) return;
    setEventBatch("loading");
    try {
      setEventBatch(await api.eventStudyBatch(symbols, "earnings"));
    } catch {
      setEventBatch("error");
    }
  }

  async function runHypothesis() {
    if (!/^\d{6}$/.test(toolSymbol)) return;
    setHypothesis("loading");
    try {
      setHypothesis(await api.hypothesisVerify(toolSymbol, rule));
    } catch {
      setHypothesis("error");
    }
  }

  async function runBatch() {
    const symbols = compareSymbols
      .split(/[,，\s]+/)
      .map((s) => s.trim())
      .filter((s) => /^\d{6}$/.test(s))
      .slice(0, 4);
    if (!symbols.length) return;
    setBatchStatus(t("settings.batchRunning"));
    try {
      const result = await api.batchResearch(symbols);
      const ok = result.items.filter((i) => i.report).length;
      setBatchStatus(
        t("settings.batchDone", {
          ok: String(ok),
          n: String(result.items.length),
        }),
      );
    } catch (err) {
      setBatchStatus(err instanceof Error ? err.message : t("settings.batchFailed"));
    }
  }

  return (
    <>
      <h4 className="settings-section-title">{t("settings.reportHistory")}</h4>
      <p className="settings-hint">{t("settings.reportHistoryHint")}</p>
      {reports.length === 0 ? (
        <p className="settings-muted">{t("settings.reportEmpty")}</p>
      ) : (
        <ul className="report-history-list">
          {reports.map((r) => {
            const post = postHocById[r.id];
            return (
              <li key={r.id} className="report-history-item">
                <div className="report-history-main">
                  <strong>
                    {r.name} ({r.symbol})
                  </strong>
                  <span className="settings-muted">
                    {r.composite_score}/10 · {t("settings.reportResearchOnly")}
                  </span>
                  <span className="settings-muted report-history-time">
                    {new Date(r.created_at).toLocaleString(locale === "zh" ? "zh-CN" : "en-US")}
                  </span>
                  {post && post !== "loading" && post !== "error" ? (
                    <p className="settings-muted">
                      {t("card.postHoc")}：
                      {post.horizons.some((h) => h.return_pct != null)
                        ? post.horizons
                            .map((h) =>
                              t("card.postHocRow", {
                                days: String(h.days),
                                ret: h.return_pct != null ? String(h.return_pct) : "—",
                              }),
                            )
                            .join(" · ")
                        : t("card.postHocEmpty")}
                    </p>
                  ) : null}
                  {post === "error" ? (
                    <p className="settings-muted">{t("card.postHocEmpty")}</p>
                  ) : null}
                </div>
                <div className="report-history-actions">
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    disabled={post === "loading"}
                    onClick={() => void loadPostHoc(r.id)}
                  >
                    {post === "loading" ? "…" : t("card.postHocBtn")}
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => api.downloadReportMarkdown(r.id)}
                  >
                    {t("settings.reportExport")}
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => api.downloadReportPdf(r.id)}
                  >
                    {t("settings.reportExportPdf")}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <h4 className="settings-section-title">{t("settings.researchTimeline")}</h4>
      <p className="settings-hint">{t("settings.researchTimelineHint")}</p>
      <div className="settings-row" style={{ gap: 8, flexWrap: "wrap" }}>
        <input
          className="settings-input"
          value={timelineSymbol}
          onChange={(e) => setTimelineSymbol(e.target.value.trim())}
          placeholder={t("settings.verifySymbol")}
          maxLength={6}
        />
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          disabled={timeline === "loading"}
          onClick={() => void loadTimeline()}
        >
          {timeline === "loading" ? "…" : t("settings.researchTimelineBtn")}
        </button>
      </div>
      {timeline === "error" ? (
        <p className="settings-muted">{t("settings.researchTimelineFailed")}</p>
      ) : null}
      {timeline && timeline !== "loading" && timeline !== "error" ? (
        timeline.entries.length === 0 ? (
          <p className="settings-muted">{t("settings.researchTimelineEmpty")}</p>
        ) : (
          <ul className="report-history-list">
            {timeline.entries.map((e) => (
              <li key={e.report_id} className="report-history-item">
                <div className="report-history-main">
                  <strong>
                    {timeline.name} · {e.bias} · {e.composite_score}/10 · {e.analysis_depth}
                  </strong>
                  <span className="settings-muted report-history-time">
                    {new Date(e.created_at).toLocaleString(locale === "zh" ? "zh-CN" : "en-US")}
                  </span>
                  {e.bias_changed ? (
                    <span className="settings-muted">
                      {" "}
                      · {t("settings.researchTimelineBiasChanged")}
                    </span>
                  ) : null}
                  {e.score_delta != null ? (
                    <span className="settings-muted">
                      {" "}
                      ·{" "}
                      {t("settings.researchTimelineScoreDelta", {
                        delta: e.score_delta > 0 ? `+${e.score_delta}` : String(e.score_delta),
                      })}
                    </span>
                  ) : null}
                  {e.factor_alignment_note ? (
                    <p className="settings-muted">{e.factor_alignment_note}</p>
                  ) : null}
                  {e.factors.length > 0 ? (
                    <p className="settings-muted">
                      {e.factors
                        .map((f) => `${f.label}=${f.value ?? f.percentile ?? "—"}`)
                        .join(" · ")}
                    </p>
                  ) : null}
                  {e.post_hoc.some((h) => h.return_pct != null) ? (
                    <p className="settings-muted">
                      {e.post_hoc
                        .filter((h) => h.return_pct != null)
                        .map((h) =>
                          t("settings.researchTimelinePostHoc", {
                            days: String(h.days),
                            ret: String(h.return_pct),
                          }),
                        )
                        .join(" · ")}
                    </p>
                  ) : null}
                  {e.summary ? <p className="settings-muted">{e.summary}</p> : null}
                </div>
              </li>
            ))}
          </ul>
        )
      ) : null}

      <h4 className="settings-section-title">{t("settings.signalBacktest")}</h4>
      <p className="settings-hint">{t("settings.signalBacktestHint")}</p>
      {backtest?.sample_bias_note ? (
        <p className="settings-muted">{backtest.sample_bias_note}</p>
      ) : null}
      {backtest && (backtest.unique_symbols != null || backtest.bias_sample_count != null) ? (
        <p className="settings-muted">
          {t("settings.signalBacktestMeta", {
            symbols: String(backtest.unique_symbols ?? 0),
            bias: String(backtest.bias_sample_count ?? 0),
            tilt: String(backtest.factor_tilt_sample_count ?? 0),
          })}
        </p>
      ) : null}
      {backtest?.notes?.map((note) => (
        <p className="settings-muted" key={note}>
          {note}
        </p>
      ))}
      {backtest && backtest.horizons.some((h) => h.sample_count > 0) ? (
        <ul className="report-history-list">
          {backtest.horizons.map((h) => (
            <li key={h.days} className="settings-muted">
              {t("settings.signalBacktestRow", {
                days: String(h.days),
                n: String(h.sample_count),
                bull: h.bullish_avg_return_pct != null ? String(h.bullish_avg_return_pct) : "—",
                bullMed:
                  h.bullish_median_return_pct != null ? String(h.bullish_median_return_pct) : "—",
                bear: h.bearish_avg_return_pct != null ? String(h.bearish_avg_return_pct) : "—",
                bearMed:
                  h.bearish_median_return_pct != null ? String(h.bearish_median_return_pct) : "—",
                spread: h.spread_avg_return_pct != null ? String(h.spread_avg_return_pct) : "—",
                bullHit:
                  h.bullish_positive_rate_pct != null ? String(h.bullish_positive_rate_pct) : "—",
                bearHit:
                  h.bearish_negative_rate_pct != null ? String(h.bearish_negative_rate_pct) : "—",
              })}
              {(h.bias_bullish_avg_return_pct != null ||
                h.factor_tilt_bullish_avg_return_pct != null) && (
                <span>
                  {" "}
                  · bias {h.bias_bullish_avg_return_pct ?? "—"}/
                  {h.bias_bearish_avg_return_pct ?? "—"} · tilt{" "}
                  {h.factor_tilt_bullish_avg_return_pct ?? "—"}/
                  {h.factor_tilt_bearish_avg_return_pct ?? "—"}
                </span>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="settings-muted">{t("settings.signalBacktestEmpty")}</p>
      )}

      <h4 className="settings-section-title">{t("settings.memorySearch")}</h4>
      <p className="settings-hint">{t("settings.memorySearchHint")}</p>
      <div className="settings-memory-row">
        <input
          type="search"
          value={memoryQuery}
          placeholder={t("settings.memorySearchPh")}
          onChange={(e) => onMemoryQueryChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && memoryQuery.trim()) {
              onMemorySearch(memoryQuery.trim());
            }
          }}
        />
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          disabled={!memoryQuery.trim()}
          onClick={() => onMemorySearch(memoryQuery.trim())}
        >
          {t("settings.memorySearchBtn")}
        </button>
      </div>
      {memoryHits && (
        <ul className="report-history-list">
          {memoryHits.hits.length === 0 ? (
            <li className="settings-muted">{t("settings.memoryEmpty")}</li>
          ) : (
            memoryHits.hits.map((hit) => (
              <li key={hit.report_id} className="report-history-item">
                <strong>
                  {hit.name} ({hit.symbol})
                </strong>
                <span className="settings-muted">
                  {hit.composite_score}/10 · {hit.bias}
                </span>
                <p className="settings-muted">{hit.summary}</p>
              </li>
            ))
          )}
        </ul>
      )}

      <h4 className="settings-section-title">{t("settings.verifyTools")}</h4>
      <p className="settings-hint">{t("settings.verifyToolsHint")}</p>
      <label className="settings-field">
        <span>{t("settings.verifySymbol")}</span>
        <input
          value={toolSymbol}
          onChange={(e) => setToolSymbol(e.target.value.trim())}
          maxLength={6}
        />
      </label>
      <label className="settings-field">
        <span>{t("settings.compareSymbols")}</span>
        <input
          value={compareSymbols}
          onChange={(e) => setCompareSymbols(e.target.value)}
          placeholder="600519,000858"
        />
      </label>
      <div className="settings-memory-row">
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => void runCompare()}>
          {compare === "loading" ? "…" : t("settings.compareBtn")}
        </button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => void runBatch()}>
          {t("settings.batchBtn")}
        </button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => void runEventStudy()}>
          {eventStudy === "loading" ? "…" : t("settings.eventStudyBtn")}
        </button>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => void runEventStudyBatch()}
        >
          {eventBatch === "loading" ? "…" : t("settings.eventStudyBatchBtn")}
        </button>
      </div>
      {batchStatus ? <p className="settings-muted">{batchStatus}</p> : null}
      {compare && compare !== "loading" && compare !== "error" ? (
        <ul className="report-history-list">
          {compare.rows.map((row) => (
            <li key={row.symbol} className="report-history-item">
              <strong>
                {row.name} ({row.symbol})
              </strong>
              <span className="settings-muted">
                {row.bars_adjust}/{row.bars_source}
                {row.partial ? ` · ${t("batch.partial")}` : ""}
              </span>
              <p className="settings-muted">
                {row.factors
                  .slice(0, 6)
                  .map((f) => `${f.label}:${f.value ?? "—"}`)
                  .join(" · ") ||
                  row.note ||
                  "—"}
              </p>
            </li>
          ))}
        </ul>
      ) : null}
      {compare === "error" ? <p className="settings-muted">{t("settings.verifyFailed")}</p> : null}

      <label className="settings-field">
        <span>{t("settings.hypothesisRule")}</span>
        <select value={rule} onChange={(e) => setRule(e.target.value)}>
          {Object.entries(presets).map(([id, label]) => (
            <option key={id} value={id}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <button type="button" className="btn btn-ghost btn-sm" onClick={() => void runHypothesis()}>
        {hypothesis === "loading" ? "…" : t("settings.hypothesisBtn")}
      </button>
      {hypothesis && hypothesis !== "loading" && hypothesis !== "error" ? (
        <ul className="report-history-list">
          <li className="settings-muted">
            {hypothesis.rule_label} · n={hypothesis.sample_count}
            {hypothesis.point_in_time ? " · PIT" : ""}
          </li>
          {hypothesis.windows.map((w) => (
            <li key={w.days} className="settings-muted">
              {w.days}d · avg {w.avg_return_pct ?? "—"}% · hit {w.hit_rate_pct ?? "—"}% · n=
              {w.sample_count}
            </li>
          ))}
        </ul>
      ) : null}
      {hypothesis === "error" ? (
        <p className="settings-muted">{t("settings.verifyFailed")}</p>
      ) : null}

      {eventStudy && eventStudy !== "loading" && eventStudy !== "error" ? (
        <ul className="report-history-list">
          {eventStudy.kind_counts ? (
            <li className="settings-muted">
              {t("settings.eventStudyKinds", {
                earnings: String(eventStudy.kind_counts.earnings ?? 0),
                risk: String(eventStudy.kind_counts.risk ?? 0),
                other: String(eventStudy.kind_counts.other ?? 0),
              })}
            </li>
          ) : null}
          {eventStudy.windows.map((w) => (
            <li key={w.days} className="settings-muted">
              {t("settings.eventStudyRow", {
                days: String(w.days),
                n: String(w.sample_count),
                avg: w.avg_return_pct != null ? String(w.avg_return_pct) : "—",
                pos: w.positive_rate_pct != null ? String(w.positive_rate_pct) : "—",
              })}
            </li>
          ))}
          {eventStudy.events.slice(0, 5).map((ev) => (
            <li key={`${ev.event_date}-${ev.title}`} className="settings-muted">
              {ev.event_date} · [{ev.event_kind}] {ev.title.slice(0, 40)}
            </li>
          ))}
        </ul>
      ) : null}
      {eventStudy === "error" ? (
        <p className="settings-muted">{t("settings.verifyFailed")}</p>
      ) : null}
      {eventBatch && eventBatch !== "loading" && eventBatch !== "error" ? (
        <ul className="report-history-list">
          {eventBatch.items.map((item) => (
            <li key={item.symbol} className="report-history-item">
              <strong>
                {item.name} ({item.symbol})
              </strong>
              <p className="settings-muted">
                {item.windows
                  .map((w) => `${w.days}d n=${w.sample_count} avg=${w.avg_return_pct ?? "—"}%`)
                  .join(" · ")}
              </p>
            </li>
          ))}
        </ul>
      ) : null}
      {eventBatch === "error" ? (
        <p className="settings-muted">{t("settings.verifyFailed")}</p>
      ) : null}
    </>
  );
}
