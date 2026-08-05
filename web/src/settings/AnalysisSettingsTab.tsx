import { type AnalysisDepth, type ModeSettings } from "../modeSettings";
import { useI18n } from "../i18n";

interface AnalysisSettingsTabProps {
  modeSettings: ModeSettings;
  onToggleDebate: (enabled: boolean) => void;
  onSelectAnalysisDepth: (depth: AnalysisDepth) => void;
}

const DEPTH_OPTIONS: {
  id: AnalysisDepth;
  labelKey: string;
  hintKey: string;
}[] = [
  {
    id: "standard",
    labelKey: "settings.analysisDepthStandard",
    hintKey: "settings.analysisDepthStandardHint",
  },
  {
    id: "comprehensive",
    labelKey: "settings.analysisDepthComprehensive",
    hintKey: "settings.analysisDepthComprehensiveHint",
  },
  {
    id: "deep",
    labelKey: "settings.analysisDepthDeep",
    hintKey: "settings.analysisDepthDeepHint",
  },
];

export function AnalysisSettingsTab({
  modeSettings,
  onToggleDebate,
  onSelectAnalysisDepth,
}: AnalysisSettingsTabProps) {
  const { t } = useI18n();

  return (
    <>
      <h4 className="settings-section-title">{t("settings.analysis")}</h4>
      <p className="settings-hint">{t("settings.analysisHint")}</p>

      <h4 className="settings-section-title">{t("settings.analysisDepth")}</h4>
      <p className="settings-hint">{t("settings.analysisDepthHint")}</p>
      <div className="settings-radio-group">
        {DEPTH_OPTIONS.map((opt) => (
          <label key={opt.id} className="settings-check">
            <input
              type="radio"
              name="analysis-depth"
              checked={modeSettings.analysisDepth === opt.id}
              onChange={() => onSelectAnalysisDepth(opt.id)}
            />
            <span>
              {t(opt.labelKey)}
              <span className="settings-muted"> — {t(opt.hintKey)}</span>
            </span>
          </label>
        ))}
      </div>

      <label className="settings-check">
        <input
          type="checkbox"
          checked={modeSettings.enableDebate}
          onChange={(e) => onToggleDebate(e.target.checked)}
        />
        <span>{t("settings.enableDebate")}</span>
      </label>
      <p className="settings-muted settings-analysis-note">
        {modeSettings.enableDebate ? t("settings.debateOnNote") : t("settings.debateOffNote")}
      </p>
    </>
  );
}
