import { BUILTIN_MASTER_IDS, type ModeSettings } from "../modeSettings";
import { useI18n } from "../i18n";

interface AnalysisSettingsTabProps {
  modeSettings: ModeSettings;
  onToggleDebate: (enabled: boolean) => void;
  onToggleMasterCommentary: (enabled: boolean) => void;
  onToggleMasterSelection: (masterId: string, enabled: boolean) => void;
  onAddCustomMaster: () => void;
  onRemoveCustomMaster: (masterId: string) => void;
}

export function AnalysisSettingsTab({
  modeSettings,
  onToggleDebate,
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
