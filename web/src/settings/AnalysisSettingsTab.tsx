import {
  BUILTIN_MASTER_IDS,
  type AnalysisDepth,
  type ModeSettings,
} from "../modeSettings";
import { useI18n } from "../i18n";

interface AnalysisSettingsTabProps {
  modeSettings: ModeSettings;
  onToggleDebate: (enabled: boolean) => void;
  onSelectAnalysisDepth: (depth: AnalysisDepth) => void;
  onToggleMasterCommentary: (enabled: boolean) => void;
  onToggleMasterSelection: (masterId: string, enabled: boolean) => void;
  onAddCustomMaster: () => void;
  onRemoveCustomMaster: (masterId: string) => void;
}

const DEPTH_OPTIONS: { id: AnalysisDepth; labelKey: string; hintKey: string }[] = [
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
  onToggleMasterCommentary,
  onToggleMasterSelection,
  onAddCustomMaster,
  onRemoveCustomMaster,
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

      <label className="settings-check">
        <input
          type="checkbox"
          checked={modeSettings.enableMasterCommentary}
          onChange={(e) => onToggleMasterCommentary(e.target.checked)}
        />
        <span>{t("settings.enableMasterCommentary")}</span>
      </label>
      <p className="settings-muted settings-analysis-note">
        {modeSettings.enableMasterCommentary
          ? t("settings.masterCommentaryOnNote")
          : t("settings.masterCommentaryOffNote")}
      </p>

      <h4 className="settings-section-title">{t("settings.masterSelection")}</h4>
      <p className="settings-hint">{t("settings.masterSelectionHint")}</p>
      <div className="settings-master-list">
        {BUILTIN_MASTER_IDS.map((id) => (
          <label key={id} className="settings-check">
            <input
              type="checkbox"
              checked={modeSettings.selectedMasters.includes(id)}
              onChange={(e) => onToggleMasterSelection(id, e.target.checked)}
              disabled={!modeSettings.enableMasterCommentary}
            />
            <span>{t(`settings.masters.${id}`)}</span>
          </label>
        ))}
        {modeSettings.customMasters.map((master) => (
          <label key={master.id} className="settings-check settings-custom-master-row">
            <input
              type="checkbox"
              checked={modeSettings.selectedMasters.includes(master.id)}
              onChange={(e) => onToggleMasterSelection(master.id, e.target.checked)}
              disabled={!modeSettings.enableMasterCommentary}
            />
            <span>{master.name}</span>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => onRemoveCustomMaster(master.id)}
            >
              {t("settings.removeCustomMaster")}
            </button>
          </label>
        ))}
      </div>
      <button
        type="button"
        className="btn btn-ghost btn-sm"
        onClick={onAddCustomMaster}
        disabled={!modeSettings.enableMasterCommentary}
      >
        {t("settings.addCustomMaster")}
      </button>
    </>
  );
}
