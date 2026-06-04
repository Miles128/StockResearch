import { useEffect, useState } from "react";
import { api, type LlmSettingsMeta } from "./api";
import {
  loadLlmSettings,
  saveLlmSettings,
  type LlmUserSettings,
} from "./llmSettings";
import {
  applyTheme,
  loadTheme,
  saveTheme,
  THEME_OPTIONS,
  type AppTheme,
} from "./themeSettings";

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
  /** 首次使用：必须完成大模型配置才能进入应用 */
  required?: boolean;
  onConfigured?: () => void;
}

function formatApiError(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

export function SettingsPanel({
  open,
  onClose,
  required = false,
  onConfigured,
}: SettingsPanelProps) {
  const [meta, setMeta] = useState<LlmSettingsMeta | null>(null);
  const [form, setForm] = useState<LlmUserSettings>(loadLlmSettings);
  const [theme, setTheme] = useState<AppTheme>(loadTheme);
  const [error, setError] = useState("");
  const [testOk, setTestOk] = useState("");
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(loadLlmSettings());
    setTheme(loadTheme());
    setError("");
    setTestOk("");
    api.llmSettings().then(setMeta).catch(() => setMeta(null));
  }, [open]);

  if (!open) return null;

  function selectTheme(next: AppTheme) {
    setTheme(next);
    saveTheme(next);
    applyTheme(next);
  }

  async function testConnection(): Promise<boolean> {
    setError("");
    setTestOk("");
    try {
      const result = await api.testLlmConnection(form);
      setTestOk(result.message);
      return true;
    } catch (e) {
      setError(formatApiError(e));
      return false;
    }
  }

  async function handleTest() {
    setTesting(true);
    try {
      await testConnection();
    } finally {
      setTesting(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    try {
      if (!(await testConnection())) return;
      saveLlmSettings(form);
      onConfigured?.();
      if (!required) onClose();
    } finally {
      setSaving(false);
    }
  }

  const busy = testing || saving;

  return (
    <div
      className={`settings-overlay${required ? " settings-overlay-required" : ""}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
    >
      {!required && <div className="settings-backdrop" onClick={onClose} />}
      {required && <div className="settings-backdrop settings-backdrop-lock" />}
      <div className="settings-panel">
        <div className="settings-header">
          <h3 id="settings-title">{required ? "欢迎使用 StockResearch" : "设置"}</h3>
          {!required && (
            <button type="button" className="btn btn-ghost settings-close" onClick={onClose}>
              关闭
            </button>
          )}
        </div>

        {required && (
          <p className="settings-required-banner">
            请先配置大模型。API Key 仅保存在您本机浏览器，不会上传到 Cloudflare 或服务器仓库。
          </p>
        )}

        {!required && (
          <>
            <h4 className="settings-section-title">外观风格</h4>
            <p className="settings-hint">切换后立即生效，保存在本机浏览器。</p>
            <div className="theme-picker">
              {THEME_OPTIONS.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  className={`theme-option${theme === opt.id ? " active" : ""}`}
                  data-theme-preview={opt.id}
                  onClick={() => selectTheme(opt.id)}
                >
                  <span className="theme-option-label">{opt.label}</span>
                  <span className="theme-option-hint">{opt.hint}</span>
                </button>
              ))}
            </div>
          </>
        )}

        <h4 className="settings-section-title">大模型</h4>
        <p className="settings-hint">
          API Key 保存在本机浏览器，每次请求会带给服务端用于调用大模型，不会写入数据库。
          保存前会先测试连接，不通则无法保存。
        </p>

        {error && <p className="settings-error">{error}</p>}
        {testOk && !error && <p className="settings-ok">{testOk}</p>}

        <label className="settings-field">
          <span>API Key</span>
          <input
            type="password"
            autoComplete="off"
            placeholder="sk-..."
            value={form.apiKey}
            disabled={form.useMock}
            onChange={(e) => setForm((f) => ({ ...f, apiKey: e.target.value }))}
          />
        </label>

        <label className="settings-field">
          <span>API Base URL</span>
          <input
            type="url"
            placeholder={meta?.default_base_url ?? "https://api.example.com/v1"}
            value={form.baseUrl}
            disabled={form.useMock}
            onChange={(e) => setForm((f) => ({ ...f, baseUrl: e.target.value }))}
          />
        </label>

        <label className="settings-field">
          <span>模型 ID</span>
          <input
            type="text"
            placeholder={meta?.default_model ?? "model-name"}
            value={form.model}
            disabled={form.useMock}
            onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))}
          />
        </label>

        <label className="settings-field">
          <span>
            温度 <strong>{form.temperature.toFixed(1)}</strong>
            <span className="settings-muted">（0 更稳定，2 更发散）</span>
          </span>
          <input
            type="range"
            min={0}
            max={2}
            step={0.1}
            value={form.temperature}
            onChange={(e) =>
              setForm((f) => ({ ...f, temperature: parseFloat(e.target.value) }))
            }
          />
        </label>

        <label className="settings-check">
          <input
            type="checkbox"
            checked={form.useMock}
            onChange={(e) => setForm((f) => ({ ...f, useMock: e.target.checked }))}
          />
          <span>使用 Mock 回复（无需 API Key，用于演示）</span>
        </label>

        {meta?.server_use_mock && !required && (
          <p className="settings-warn">服务端当前启用了 USE_MOCK_LLM；勾选 Mock 可本地演示。</p>
        )}

        <div className="settings-actions">
          {!required && (
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={busy}>
              取消
            </button>
          )}
          <button
            type="button"
            className="btn btn-ghost"
            onClick={handleTest}
            disabled={busy}
          >
            {testing ? "测试中…" : "测试连接"}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSave}
            disabled={busy}
          >
            {saving ? "保存中…" : required ? "保存并进入" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
