/** Factory for JSON SSE streams consumed by the API client. */

import { dataSourceRequestHeaders } from "./dataSourceSettings";

export interface SseEvent {
  type: string;
  [key: string]: unknown;
}

export interface SseStreamOptions<T, E extends SseEvent = SseEvent> {
  url: string;
  method?: "GET" | "POST";
  headers?: Record<string, string>;
  body?: Record<string, unknown>;
  signal?: AbortSignal;
  /** Per-read timeout while waiting for the next SSE chunk. */
  timeoutMs?: number;
  onEvent?: (event: E) => void;
  /** Pull the final payload from a terminal event (usually type === "done"). */
  extractResult: (event: E) => T | undefined;
}

const SSE_READ_TIMEOUT_MS = 60_000;
const SSE_OPEN_TIMEOUT_MS = 30_000;

async function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  const externalAbort = options.signal;
  const onExternalAbort = () => controller.abort();
  externalAbort?.addEventListener("abort", onExternalAbort, { once: true });
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(id);
    externalAbort?.removeEventListener("abort", onExternalAbort);
  }
}

async function consumeSse<E extends SseEvent>(
  resp: Response,
  onEvent?: (event: E) => void,
  signal?: AbortSignal,
  timeoutMs = SSE_READ_TIMEOUT_MS,
): Promise<void> {
  if (!resp.body) {
    throw new Error("流式请求失败");
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let timedOut = false;

  const onAbort = () => {
    timedOut = true;
    reader.cancel().catch(() => {});
  };
  signal?.addEventListener("abort", onAbort, { once: true });

  try {
    while (true) {
      if (timedOut) break;
      const readPromise = reader.read();
      let timerId: ReturnType<typeof setTimeout> | undefined;
      const timeoutPromise = new Promise<never>((_, reject) => {
        timerId = setTimeout(() => {
          reject(new Error("SSE connection timed out — no data received for 60s"));
        }, timeoutMs);
      });

      try {
        const { done, value } = await Promise.race([readPromise, timeoutPromise]);
        if (timerId !== undefined) clearTimeout(timerId);
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6).trim();
          if (!jsonStr || jsonStr === "[DONE]") continue;
          try {
            const event = JSON.parse(jsonStr) as E;
            onEvent?.(event);
          } catch {
            // skip malformed JSON
          }
        }
      } catch (err) {
        if (timerId !== undefined) clearTimeout(timerId);
        reader.cancel().catch(() => {});
        if (err instanceof Error && err.message.includes("timed out")) break;
        throw err;
      }
    }
  } finally {
    signal?.removeEventListener("abort", onAbort);
    try {
      reader.releaseLock();
    } catch {
      /* already released */
    }
  }
}

export async function createJsonSseStream<T, E extends SseEvent = SseEvent>(
  options: SseStreamOptions<T, E>,
): Promise<T | null> {
  const {
    url,
    method = "GET",
    headers = {},
    body,
    signal,
    timeoutMs = SSE_READ_TIMEOUT_MS,
    onEvent,
    extractResult,
  } = options;

  const init: RequestInit = {
    method,
    headers: {
      "Content-Type": "application/json",
      ...dataSourceRequestHeaders(),
      ...headers,
    },
    signal,
  };
  if (body && method !== "GET") {
    init.body = JSON.stringify(body);
  }

  const resp = await fetchWithTimeout(url, init, SSE_OPEN_TIMEOUT_MS);
  if (!resp.ok) {
    throw new Error("流式请求失败");
  }

  let result: T | null = null;
  await consumeSse<E>(
    resp,
    (event) => {
      onEvent?.(event);
      const r = extractResult(event);
      if (r !== undefined) {
        result = r;
      }
    },
    signal,
    timeoutMs,
  );
  return result;
}
