const STORAGE_KEY = "stockresearch.llm.settings";
const LEGACY_STORAGE_KEYS = ["stockbuddy.llm.settings", "invesbao.llm.settings"];

export interface LlmUserSettings {
  apiKey: string;
  baseUrl: string;
  model: string;
  temperature: number;
  useMock: boolean;
}

export interface LlmSettingsMeta {
  default_base_url: string;
  default_model: string;
  default_api_key: string;
  default_temperature: number;
  server_use_mock: boolean;
  server_configured: boolean;
  server_has_api_key: boolean;
}

/** Map server metadata into the settings form. */
export function llmMetaToForm(meta: LlmSettingsMeta): LlmUserSettings {
  return {
    apiKey: meta.default_api_key,
    baseUrl: meta.default_base_url,
    model: meta.default_model,
    temperature: meta.default_temperature,
    useMock: meta.server_use_mock,
  };
}

export interface LlmTestResult {
  ok: boolean;
  message: string;
}

const DEFAULTS: LlmUserSettings = {
  apiKey: "",
  baseUrl: "",
  model: "",
  temperature: 0.3,
  useMock: false,
};

export function loadLlmSettings(): LlmUserSettings {
  try {
    let raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      for (const key of LEGACY_STORAGE_KEYS) {
        raw = localStorage.getItem(key);
        if (raw) break;
      }
    }
    if (!raw) return { ...DEFAULTS };
    const parsed = JSON.parse(raw) as Partial<LlmUserSettings>;
    return {
      apiKey: parsed.apiKey ?? "",
      baseUrl: parsed.baseUrl ?? "",
      model: parsed.model ?? "",
      temperature:
        typeof parsed.temperature === "number" ? parsed.temperature : DEFAULTS.temperature,
      useMock: Boolean(parsed.useMock),
    };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveLlmSettings(settings: LlmUserSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

/** Browser-local override configured (mock or full API fields). */
export function isLlmConfiguredLocally(): boolean {
  const s = loadLlmSettings();
  if (s.useMock) return true;
  return Boolean(s.apiKey.trim() && s.baseUrl.trim() && s.model.trim());
}

export function isServerLlmConfigured(meta: LlmSettingsMeta): boolean {
  return Boolean(meta.server_configured);
}

/** @deprecated use isLlmConfiguredLocally or server meta */
export function isLlmConfigured(): boolean {
  return isLlmConfiguredLocally();
}

export function llmFormToApiBody(form: LlmUserSettings): Record<string, unknown> {
  return {
    api_key: form.apiKey.trim() || null,
    base_url: form.baseUrl.trim() || null,
    model: form.model.trim() || null,
    temperature: form.temperature,
    use_mock: form.useMock,
  };
}

export function llmRequestHeaders(): Record<string, string> {
  const s = loadLlmSettings();
  const headers: Record<string, string> = {};
  if (s.apiKey.trim()) headers["X-LLM-Api-Key"] = s.apiKey.trim();
  if (s.baseUrl.trim()) headers["X-LLM-Base-Url"] = s.baseUrl.trim();
  if (s.model.trim()) headers["X-LLM-Model"] = s.model.trim();
  if (s.temperature !== 0.3) {
    headers["X-LLM-Temperature"] = String(s.temperature);
  }
  if (s.useMock) headers["X-LLM-Use-Mock"] = "true";
  return headers;
}

export function llmBodyField(): { llm: Record<string, unknown> } | Record<string, never> {
  const s = loadLlmSettings();
  const hasOverride =
    s.apiKey.trim() ||
    s.baseUrl.trim() ||
    s.model.trim() ||
    s.temperature !== 0.3 ||
    s.useMock;
  if (!hasOverride) return {};
  return { llm: llmFormToApiBody(s) };
}
