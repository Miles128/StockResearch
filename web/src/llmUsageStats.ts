import type { LlmUsage } from "./api";

/** 本机 LLM 用量累计（localStorage）——BYOK 用户的用量可见性。 */

export interface UsageAggregate {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_cny: number;
  calls: number;
  /** 最近一次用量记录的日期（YYYY-MM-DD），用于"今日"聚合。 */
  last_day: string;
  today_tokens: number;
}

const STORAGE_KEY = "stockresearch.llm.usage";

const EMPTY: UsageAggregate = {
  prompt_tokens: 0,
  completion_tokens: 0,
  total_tokens: 0,
  cost_cny: 0,
  calls: 0,
  last_day: "",
  today_tokens: 0,
};

function todayKey(): string {
  return new Date().toISOString().slice(0, 10);
}

function loadRaw(): UsageAggregate {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...EMPTY };
    const parsed = JSON.parse(raw) as Partial<UsageAggregate>;
    return { ...EMPTY, ...parsed };
  } catch {
    return { ...EMPTY };
  }
}

export function loadUsageStats(): UsageAggregate {
  const agg = loadRaw();
  if (agg.last_day !== todayKey()) {
    agg.today_tokens = 0;
  }
  return agg;
}

export function recordLlmUsage(usage: LlmUsage | null | undefined): void {
  if (!usage || !usage.total_tokens) return;
  const agg = loadRaw();
  const today = todayKey();
  if (agg.last_day !== today) {
    agg.last_day = today;
    agg.today_tokens = 0;
  }
  agg.prompt_tokens += usage.prompt_tokens || 0;
  agg.completion_tokens += usage.completion_tokens || 0;
  agg.total_tokens += usage.total_tokens || 0;
  agg.cost_cny += usage.estimated_cost_cny ?? 0;
  agg.calls += 1;
  agg.today_tokens += usage.total_tokens || 0;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(agg));
  } catch {
    /* storage full/disabled — stats are best-effort */
  }
}
