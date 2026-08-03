import type { LlmSettingsMeta } from "../api";
import type { LlmUserSettings } from "../llmSettings";
import { useI18n } from "../i18n";

interface LlmSettingsTabProps {
  required: boolean;
  variant: "inline" | "modal";
  form: LlmUserSettings;
  meta: LlmSettingsMeta | null;
  error: string;
  testOk: string;
  busy: boolean;
  testing: boolean;
  saving: boolean;
  onFormChange: (next: LlmUserSettings) => void;
  onClose: () => void;
  onTest: () => void;
  onSave: () => void;
}

export function LlmSettingsTab({
  required,
  variant,
  form,
  meta,
  error,
  testOk,
  busy,
  testing,
  saving,
  onFormChange,
  onClose,
  onTest,
  onSave,
}: LlmSettingsTabProps) {
  const { t } = useI18n();

  return (
    <>
      <h4 className="settings-section-title">{t("settings.llm")}</h4>
      <p className="settings-hint">{t("settings.llmHint")}</p>
      {error && <p className="settings-error">{error}</p>}
      {testOk && !error && <p className="settings-ok">{testOk}</p>}
      <label className="settings-field">
        <span>{t("settings.apiKey")}</span>
        <input
          type="password"
          autoComplete="off"
          value={form.apiKey}
          disabled={form.useMock}
          onChange={(e) => onFormChange({ ...form, apiKey: e.target.value })}
        />
      </label>
      <label className="settings-field">
        <span>{t("settings.baseUrl")}</span>
        <input
          type="text"
          autoComplete="off"
          spellCheck={false}
          value={form.baseUrl}
          disabled={form.useMock}
          onChange={(e) => onFormChange({ ...form, baseUrl: e.target.value })}
        />
      </label>
      <label className="settings-field">
        <span>{t("settings.model")}</span>
        <input
          type="text"
          value={form.model}
          disabled={form.useMock}
          onChange={(e) => onFormChange({ ...form, model: e.target.value })}
        />
      </label>
      <label className="settings-field">
        <span>
          {t("settings.temperature")}{" "}
          <strong>{form.temperature.toFixed(1)}</strong>
          <span className="settings-muted">{t("settings.tempHint")}</span>
        </span>
        <input
          type="range"
          min={0}
          max={2}
          step={0.1}
          value={form.temperature}
          onChange={(e) =>
            onFormChange({ ...form, temperature: parseFloat(e.target.value) })
          }
        />
      </label>
      <label className="settings-check">
        <input
          type="checkbox"
          checked={form.useMock}
          onChange={(e) => onFormChange({ ...form, useMock: e.target.checked })}
        />
        <span>{t("settings.useMock")}</span>
      </label>
      {meta?.server_use_mock && !required && (
        <p className="settings-warn">{t("settings.serverMock")}</p>
      )}
      <div className="settings-actions">
        {!required && variant === "modal" && (
          <button
            type="button"
            className="btn btn-ghost"
            onClick={onClose}
            disabled={busy}
          >
            {t("settings.cancel")}
          </button>
        )}
        <button
          type="button"
          className="btn btn-ghost"
          onClick={onTest}
          disabled={busy}
        >
          {testing ? t("settings.testing") : t("settings.test")}
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={onSave}
          disabled={busy}
        >
          {saving
            ? t("settings.saving")
            : required
              ? t("settings.saveEnter")
              : t("settings.save")}
        </button>
      </div>
    </>
  );
}
