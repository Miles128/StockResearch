import { dataSourceRequestHeaders } from "../dataSourceSettings";
import {
  llmBodyField,
  llmFormToApiBody,
  llmRequestHeaders,
  type LlmSettingsMeta,
  type LlmTestResult,
  type LlmUserSettings,
} from "../llmSettings";

/** Build-time optional origin, e.g. https://api.example.com (no trailing slash). */
export const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";
export const API = API_ORIGIN ? `${API_ORIGIN}/api/v1` : "/api/v1";

export function apiUrl(path: string): string {
  return `${API}${path}`;
}

function formatApiDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === "object" && item && "msg" in item ? String(item.msg) : String(item)))
      .join("; ");
  }
  return "";
}

const DEFAULT_TIMEOUT_MS = 30_000;
const RETRY_COUNT = 2;
const RETRY_DELAY_MS = 1000;

async function fetchWithTimeout(url: string, options: RequestInit, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(id);
  }
}

async function fetchWithRetry(
  url: string,
  options: RequestInit,
  retries = RETRY_COUNT,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<Response> {
  let lastError: Error | null = null;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const resp = await fetchWithTimeout(url, options, timeoutMs);
      if (resp.status >= 500 && attempt < retries) {
        await new Promise((r) => setTimeout(r, RETRY_DELAY_MS * (attempt + 1)));
        continue;
      }
      return resp;
    } catch (err) {
      lastError = err as Error;
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, RETRY_DELAY_MS * (attempt + 1)));
      }
    }
  }
  throw lastError;
}

export async function requestPlain<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const resp = await fetchWithRetry(`${API}${path}`, { ...options, headers });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(formatApiDetail(err.detail) || "请求失败");
  }
  return resp.json();
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...dataSourceRequestHeaders(),
    ...(options.headers as Record<string, string>),
  };

  const resp = await fetchWithRetry(`${API}${path}`, { ...options, headers });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(formatApiDetail(err.detail) || "请求失败");
  }
  return resp.json();
}

export async function requestWithLlm<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs?: number,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...llmRequestHeaders(),
    ...dataSourceRequestHeaders(),
    ...(options.headers as Record<string, string>),
  };

  const resp = await fetchWithRetry(`${API}${path}`, { ...options, headers }, RETRY_COUNT, timeoutMs);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(formatApiDetail(err.detail) || "请求失败");
  }
  return resp.json();
}

export async function checkBackendHealth(): Promise<boolean> {
  const url = API_ORIGIN ? `${API_ORIGIN}/health` : "/health";
  try {
    const resp = await fetchWithTimeout(url, {}, 5000);
    if (!resp.ok) return false;
    const body = (await resp.json()) as { status?: string };
    return body.status === "ok";
  } catch {
    return false;
  }
}

export { llmFormToApiBody, llmRequestHeaders };
export type { LlmSettingsMeta, LlmTestResult, LlmUserSettings };
