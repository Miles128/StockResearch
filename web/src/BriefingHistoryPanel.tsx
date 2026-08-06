import { useCallback, useEffect, useState } from "react";
import { api, type Briefing } from "./api";
import { CollapsibleSection } from "./CollapsibleSection";
import { useI18n } from "./i18n";
import { MarkdownContent } from "./MarkdownContent";
import { recordEvent, EVENT_KEYS } from "./usageTracking";

const BRIEFING_KINDS: Array<{ kind: Briefing["kind"]; labelKey: string }> = [
  { kind: "premarket", labelKey: "lists.briefingKindPremarket" },
  { kind: "intraday", labelKey: "lists.briefingKindIntraday" },
  { kind: "postmarket", labelKey: "lists.briefingKindPostmarket" },
];

function dateKey(iso: string): string {
  return iso.slice(0, 10);
}

/** 左侧栏简报折叠块：历史列表 + 盘前/盘后对照。自包含，不依赖外部 props。 */
export function BriefingHistoryPanel() {
  const { t } = useI18n();
  const [briefings, setBriefings] = useState<Briefing[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);
  const [generating, setGenerating] = useState<Briefing["kind"] | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const list = await api.briefingHistory("all", 12);
      setBriefings(list);
    } catch {
      setError(t("lists.briefingLoadFailed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const generate = useCallback(
    async (kind: Briefing["kind"]) => {
      if (generating) return;
      setGenerating(kind);
      setError("");
      try {
        await api.generateBriefing(kind);
        recordEvent(EVENT_KEYS.briefingGenerate);
        setGeneratedAt(new Date().toLocaleTimeString());
        await load();
      } catch {
        setError(t("lists.briefingGenerateFailed"));
      } finally {
        setGenerating(null);
      }
    },
    [generating, load, t],
  );

  const selected = briefings.find((b) => b.id === openId) ?? null;
  const morningMatch =
    selected?.kind === "postmarket"
      ? briefings.find(
          (b) =>
            b.kind === "premarket" && dateKey(b.generated_at) === dateKey(selected.generated_at),
        )
      : null;

  return (
    <CollapsibleSection title={t("lists.briefingTitle")} defaultCollapsed>
      <div className="briefing-panel">
        <div className="briefing-generate-row">
          {BRIEFING_KINDS.map(({ kind, labelKey }) => (
            <button
              key={kind}
              type="button"
              className="icon-btn briefing-generate-btn"
              disabled={generating !== null}
              onClick={() => void generate(kind)}
              title={t("lists.briefingGenerate")}
            >
              {generating === kind ? "…" : t(labelKey)}
            </button>
          ))}
        </div>
        {generatedAt && (
          <div className="briefing-note">
            {t("lists.briefingGeneratedAt")} {generatedAt}
          </div>
        )}
        {error && <div className="briefing-note briefing-error">{error}</div>}
        {loading && <div className="briefing-note">{t("lists.briefingLoading")}</div>}
        {!loading && briefings.length === 0 && (
          <div className="briefing-note">{t("lists.briefingEmpty")}</div>
        )}
        <ul className="briefing-list">
          {briefings.map((b) => (
            <li key={b.id}>
              <button
                type="button"
                className={`briefing-item${b.id === openId ? " open" : ""}`}
                onClick={() => {
                  if (b.id !== openId) recordEvent(EVENT_KEYS.briefingView);
                  setOpenId(b.id === openId ? null : b.id);
                }}
              >
                <span className={`briefing-kind briefing-kind-${b.kind}`}>
                  {t(
                    `lists.briefingKind${b.kind === "premarket" ? "Premarket" : b.kind === "intraday" ? "Intraday" : "Postmarket"}`,
                  )}
                </span>
                <span className="briefing-item-title">
                  <MarkdownContent text={b.title || b.summary} className="briefing-item-title-md" />
                </span>
                <span className="briefing-item-date">{dateKey(b.generated_at)}</span>
              </button>
            </li>
          ))}
        </ul>
        {selected && (
          <div className="briefing-detail">
            <h4>
              <MarkdownContent text={selected.title} className="briefing-title-md" />
            </h4>
            {selected.summary && (
              <MarkdownContent text={selected.summary} className="briefing-summary-md" />
            )}
            {selected.sections.map((s, i) => (
              <div key={i} className="briefing-section">
                <strong>
                  <MarkdownContent text={s.title} className="briefing-section-title-md" />
                </strong>
                <MarkdownContent text={s.content} />
              </div>
            ))}
            {morningMatch && (
              <details className="briefing-contrast">
                <summary>{t("lists.briefingContrast")}</summary>
                <div className="briefing-section">
                  <strong>
                    <MarkdownContent
                      text={morningMatch.title}
                      className="briefing-section-title-md"
                    />
                  </strong>
                  <MarkdownContent text={morningMatch.summary} />
                </div>
              </details>
            )}
          </div>
        )}
      </div>
    </CollapsibleSection>
  );
}
