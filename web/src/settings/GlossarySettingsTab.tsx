import type { GlossaryTerm } from "../api";
import type { ModeSettings } from "../modeSettings";
import { useI18n } from "../i18n";

interface GlossarySettingsTabProps {
  modeSettings: ModeSettings;
  glossaryTerms: GlossaryTerm[];
  glossaryFilter: string;
  newGlossaryShort: string;
  newGlossaryDef: string;
  newGlossaryAnalogy: string;
  onGlossaryFilterChange: (value: string) => void;
  onNewGlossaryShortChange: (value: string) => void;
  onNewGlossaryDefChange: (value: string) => void;
  onNewGlossaryAnalogyChange: (value: string) => void;
  onPersistModeSettings: (next: ModeSettings) => void;
  onAddCustomGlossaryTerm: () => void;
  onRemoveCustomGlossaryTerm: (termId: string) => void;
}

export function GlossarySettingsTab({
  modeSettings,
  glossaryTerms,
  glossaryFilter,
  newGlossaryShort,
  newGlossaryDef,
  newGlossaryAnalogy,
  onGlossaryFilterChange,
  onNewGlossaryShortChange,
  onNewGlossaryDefChange,
  onNewGlossaryAnalogyChange,
  onPersistModeSettings,
  onAddCustomGlossaryTerm,
  onRemoveCustomGlossaryTerm,
}: GlossarySettingsTabProps) {
  const { t } = useI18n();

  return (
    <>
      <h4 className="settings-section-title">{t("settings.glossary")}</h4>
      <p className="settings-hint">{t("settings.glossaryHint")}</p>
      <label className="settings-check">
        <input
          type="checkbox"
          checked={modeSettings.enableGlossary}
          disabled={modeSettings.mode === "research"}
          onChange={(e) =>
            onPersistModeSettings({
              ...modeSettings,
              enableGlossary: e.target.checked,
            })
          }
        />
        <span>{t("settings.enableGlossary")}</span>
      </label>
      <p className="settings-muted settings-analysis-note">
        {modeSettings.mode === "research"
          ? t("settings.glossaryResearchNote")
          : modeSettings.enableGlossary
            ? t("settings.glossaryOnNote")
            : t("settings.glossaryOffNote")}
      </p>

      <div className="glossary-settings-panel">
        <div className="glossary-settings-toolbar">
          <input
            type="search"
            className="settings-input"
            placeholder={t("settings.glossarySearch")}
            value={glossaryFilter}
            onChange={(e) => onGlossaryFilterChange(e.target.value)}
          />
          <span className="settings-muted">
            {t("settings.glossaryCount", { n: glossaryTerms.length })}
          </span>
        </div>
        <ul className="glossary-term-list">
          {glossaryTerms
            .filter((term) => {
              const q = glossaryFilter.trim().toLowerCase();
              if (!q) return true;
              return (
                term.short.toLowerCase().includes(q) ||
                term.id.toLowerCase().includes(q) ||
                term.def.toLowerCase().includes(q)
              );
            })
            .map((term) => (
              <li key={term.id} className="glossary-term-row">
                <div className="glossary-term-head">
                  <strong>{term.short}</strong>
                  {term.custom ? (
                    <span className="glossary-term-badge custom">
                      {t("settings.glossaryCustom")}
                    </span>
                  ) : (
                    <span className="glossary-term-badge">{t("settings.glossaryBuiltin")}</span>
                  )}
                  {term.custom && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => onRemoveCustomGlossaryTerm(term.id)}
                    >
                      {t("settings.glossaryRemove")}
                    </button>
                  )}
                </div>
                <p className="glossary-term-def">{term.def}</p>
                {term.analogy ? <p className="glossary-term-analogy">{term.analogy}</p> : null}
              </li>
            ))}
        </ul>

        <h5 className="settings-subsection-title">{t("settings.glossaryAddTitle")}</h5>
        <p className="settings-hint">{t("settings.glossaryAddHint")}</p>
        <label className="settings-field">
          <span>{t("settings.glossaryTermShort")}</span>
          <input
            className="settings-input"
            value={newGlossaryShort}
            onChange={(e) => onNewGlossaryShortChange(e.target.value)}
            placeholder={t("settings.glossaryTermShortPh")}
          />
        </label>
        <label className="settings-field">
          <span>{t("settings.glossaryTermDef")}</span>
          <textarea
            className="settings-input"
            rows={2}
            value={newGlossaryDef}
            onChange={(e) => onNewGlossaryDefChange(e.target.value)}
            placeholder={t("settings.glossaryTermDefPh")}
          />
        </label>
        <label className="settings-field">
          <span>{t("settings.glossaryTermAnalogy")}</span>
          <input
            className="settings-input"
            value={newGlossaryAnalogy}
            onChange={(e) => onNewGlossaryAnalogyChange(e.target.value)}
            placeholder={t("settings.glossaryTermAnalogyPh")}
          />
        </label>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={onAddCustomGlossaryTerm}
          disabled={!newGlossaryShort.trim() || newGlossaryDef.trim().length < 2}
        >
          {t("settings.glossaryAddBtn")}
        </button>
      </div>
    </>
  );
}
