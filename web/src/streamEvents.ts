import type { AgentStreamEvent } from "./api";
import {
  detectDimensionSet,
  dimensionDefsForKind,
  isDimensionAgent,
  seedDimensionSteps,
} from "./dimensionStream";
import { isRiskWorkflowAgent, seedRiskWorkflowSteps } from "./riskWorkflow";
import {
  detectDimensionKind,
  localizeAgentName,
  shouldSeedDimensions,
  shouldSkipStatusLog,
} from "./streamI18n";
import { localizePositionAction, localizeVoteLabel } from "./uiLabels";
import type { TParams } from "./i18n";
import { stripDisclaimer } from "./disclaimerText";
import type { AgentStep, HoldingAction, JudgeVerdict } from "./types/streamTypes";

/** Per-skill nested process (dimensions, judge, etc.). */
export interface SkillStreamSlice {
  streamStatus: string;
  streamLog: string[];
  agentSteps: AgentStep[];
  judgeVerdict: JudgeVerdict | null;
  activeStreamIds: string[];
}

export interface SkillStep {
  skillRunId: string;
  skillId: string;
  label: string;
  status: "running" | "done";
  summary?: string;
  nested: SkillStreamSlice;
}

export interface StreamState {
  streamStatus: string;
  streamLog: string[];
  agentSteps: AgentStep[];
  judgeVerdict: JudgeVerdict | null;
  activeStreamIds: string[];
  skillSteps: SkillStep[];
  activeSkillRunId?: string;
}

function activateStream(active: string[], streamId: string): string[] {
  if (active.includes(streamId)) {
    return active;
  }
  return [...active, streamId];
}

function deactivateAgentStream(active: string[], agentId: string): string[] {
  return active.filter((id) => id !== agentId);
}

function upsertAgentContent(
  steps: AgentStep[],
  streamId: string,
  delta: string,
  meta?: { agent_id?: string; agent_name?: string; role?: string },
): AgentStep[] {
  const agentId = meta?.agent_id ?? streamId;
  const existing = steps.find((s) => s.agent_id === agentId);
  if (existing) {
    return steps.map((s) =>
      s.agent_id === agentId
        ? { ...s, content: `${s.content ?? ""}${delta}`, status: "running" }
        : s,
    );
  }
  return [
    ...steps,
    {
      agent_id: agentId,
      agent_name: meta?.agent_name ?? streamId,
      role: meta?.role ?? "analyst",
      content: delta,
      status: "running",
    },
  ];
}

function applyTextDeltaToSlice(
  slice: SkillStreamSlice,
  streamId: string,
  delta: string,
  meta?: { agent_id?: string; agent_name?: string; role?: string },
): Pick<SkillStreamSlice, "agentSteps" | "judgeVerdict"> {
  if (streamId === "judge") {
    const summary = `${slice.judgeVerdict?.summary ?? ""}${delta}`;
    return {
      agentSteps: slice.agentSteps,
      judgeVerdict: {
        ...(slice.judgeVerdict ?? { summary: "", reason: "" }),
        summary,
        reason: summary,
      },
    };
  }

  return {
    agentSteps: upsertAgentContent(slice.agentSteps, streamId, delta, meta),
    judgeVerdict: slice.judgeVerdict,
  };
}

export function emptySkillStreamSlice(): SkillStreamSlice {
  return {
    streamStatus: "",
    streamLog: [],
    agentSteps: [],
    judgeVerdict: null,
    activeStreamIds: [],
  };
}

export function emptyStreamState(): StreamState {
  return {
    streamStatus: "",
    streamLog: [],
    agentSteps: [],
    judgeVerdict: null,
    activeStreamIds: [],
    skillSteps: [],
  };
}

function sliceHasSubstance(slice: SkillStreamSlice): boolean {
  return slice.agentSteps.length > 0 || slice.judgeVerdict != null;
}

/** Completed turns: only show process panel when there is real agent output. */
export function hasProcessContent(process?: StreamState): boolean {
  if (!process) return false;
  if (sliceHasSubstance(process)) return true;
  return process.skillSteps.some((skill) => sliceHasSubstance(skill.nested));
}

/** In-progress stream panel — include transient status lines. */
export function hasLiveProcessContent(process?: StreamState): boolean {
  if (!process) return false;
  return (
    hasProcessContent(process) ||
    process.streamLog.length > 0 ||
    Boolean(process.streamStatus.trim())
  );
}

function finalizeSlice(slice: SkillStreamSlice, doneLabel: string): SkillStreamSlice {
  return {
    ...slice,
    streamStatus: doneLabel,
    streamLog: [],
    activeStreamIds: [],
    agentSteps: slice.agentSteps.map((step) =>
      step.status === "running" ? { ...step, status: "done" as const } : step,
    ),
  };
}

/** Freeze stream UI after completion — drop stale react status lines. */
export function finalizeStreamState(state: StreamState, doneLabel: string): StreamState {
  return {
    ...state,
    streamStatus: doneLabel,
    streamLog: [],
    activeStreamIds: [],
    agentSteps: state.agentSteps.map((step) =>
      step.status === "running" ? { ...step, status: "done" as const } : step,
    ),
    skillSteps: state.skillSteps.map((skill) => ({
      ...skill,
      status: "done" as const,
      nested: finalizeSlice(skill.nested, doneLabel),
    })),
  };
}

type TFn = (key: string, params?: TParams) => string;

function applyCoreStreamEvent(
  slice: SkillStreamSlice,
  event: AgentStreamEvent,
  t?: TFn,
): SkillStreamSlice {
  let { streamStatus, streamLog, agentSteps, judgeVerdict, activeStreamIds } = slice;

  if (event.type === "status" && (event.message || event.message_key)) {
    const msg = event.message ?? "";
    streamStatus = msg;
    if (shouldSeedDimensions(event)) {
      const kind = detectDimensionKind(event, msg);
      const defs = t ? dimensionDefsForKind(kind, t) : detectDimensionSet(agentSteps, msg, kind);
      agentSteps = seedDimensionSteps(agentSteps, defs);
    }
    if (!shouldSkipStatusLog(event) && streamLog[streamLog.length - 1] !== msg) {
      streamLog = [...streamLog, msg];
    }
  }

  if (event.type === "text_delta" && event.stream_id && event.delta) {
    const meta = event.agent_id
      ? {
          agent_id: event.agent_id,
          agent_name: event.agent_name,
          role: event.role,
        }
      : undefined;
    const updated = applyTextDeltaToSlice(slice, event.stream_id, event.delta, meta);
    agentSteps = updated.agentSteps;
    judgeVerdict = updated.judgeVerdict;
    activeStreamIds = activateStream(activeStreamIds, event.stream_id);
  }

  if (event.type === "agent_start" && event.agent_id && event.agent_name && event.role) {
    const agentName =
      t != null ? localizeAgentName(event.agent_id, event.agent_name, t) : event.agent_name;
    const dimensionAgent = isDimensionAgent(event.agent_id);
    const riskAgent = isRiskWorkflowAgent(event.agent_id);
    if (!dimensionAgent && !riskAgent) {
      const startLine = t ? t("stream.agentStarted", { name: agentName }) : `▶ ${agentName} 开始`;
      if (streamLog[streamLog.length - 1] !== startLine) {
        streamLog = [...streamLog, startLine];
      }
    } else if (dimensionAgent) {
      const kind = detectDimensionKind({ type: "status", message: streamStatus }, streamStatus);
      const defs = t
        ? dimensionDefsForKind(kind, t)
        : detectDimensionSet(agentSteps, streamStatus, kind);
      agentSteps = seedDimensionSteps(agentSteps, defs);
    } else if (riskAgent && t != null) {
      agentSteps = seedRiskWorkflowSteps(agentSteps, t);
    }
    const existing = agentSteps.find((s) => s.agent_id === event.agent_id);
    agentSteps = [
      ...agentSteps.filter((s) => s.agent_id !== event.agent_id),
      {
        agent_id: event.agent_id,
        agent_name: agentName,
        role: event.role,
        status: "running",
        content: existing?.content ?? "",
      },
    ];
  }

  if (event.type === "dimension_ready" && event.agent_id && event.agent_name) {
    const defs = detectDimensionSet(agentSteps, streamStatus);
    agentSteps = seedDimensionSteps(agentSteps, defs);
    const content = stripDisclaimer(String(event.content ?? ""));
    const existing = agentSteps.find((s) => s.agent_id === event.agent_id);
    agentSteps = [
      ...agentSteps.filter((s) => s.agent_id !== event.agent_id),
      {
        agent_id: event.agent_id,
        agent_name: event.agent_name,
        role: event.role ?? "analyst",
        status: "done",
        content: content || existing?.content || "",
      },
    ];
  }

  if (event.type === "agent_done" && event.agent_id) {
    const dimensionAgent = isDimensionAgent(event.agent_id);
    if (!dimensionAgent && !isRiskWorkflowAgent(event.agent_id)) {
      const doneName =
        agentSteps.find((s) => s.agent_id === event.agent_id)?.agent_name ?? event.agent_id;
      const doneLine = t ? t("stream.agentDone", { name: doneName }) : `✓ ${doneName} 完成`;
      if (streamLog[streamLog.length - 1] !== doneLine) {
        streamLog = [...streamLog, doneLine];
      }
    }
    agentSteps = agentSteps.map((s) =>
      s.agent_id === event.agent_id
        ? {
            ...s,
            status: "done",
            content: stripDisclaimer(String(event.content ?? s.content ?? "")),
          }
        : s,
    );
    activeStreamIds = deactivateAgentStream(activeStreamIds, event.agent_id);
  }

  if (event.type === "judge") {
    activeStreamIds = activeStreamIds.filter((id) => id !== "judge");
    const biasLabel =
      t && event.verdict
        ? localizeVoteLabel(event.verdict, t)
        : event.verdict === "bullish"
          ? "偏多"
          : event.verdict === "bearish"
            ? "偏空"
            : event.verdict === "neutral"
              ? "中性"
              : undefined;
    judgeVerdict = {
      risk_level: event.risk_level ?? biasLabel,
      position_action: event.position_action
        ? t
          ? localizePositionAction(String(event.position_action), t)
          : event.position_action
        : event.position_action,
      summary: stripDisclaimer(
        String(event.summary ?? event.content ?? judgeVerdict?.summary ?? ""),
      ),
      reason: stripDisclaimer(String(event.reason ?? event.summary ?? judgeVerdict?.reason ?? "")),
      divergence: event.divergence,
      verdict: event.verdict,
      content: event.content,
      analysis_process: event.analysis_process,
      holding_actions: event.holding_actions as HoldingAction[] | undefined,
    };
  }

  return {
    streamStatus,
    streamLog,
    agentSteps,
    judgeVerdict,
    activeStreamIds,
  };
}

export function applyStreamEvent(prev: StreamState, event: AgentStreamEvent, t?: TFn): StreamState {
  let {
    streamStatus,
    streamLog,
    agentSteps,
    judgeVerdict,
    activeStreamIds,
    skillSteps,
    activeSkillRunId,
  } = prev;

  const skillRunId =
    event.skill_run_id && event.type !== "skill_start" && event.type !== "skill_done"
      ? String(event.skill_run_id)
      : undefined;

  if (event.type === "skill_start" && event.skill_run_id && event.skill_id) {
    const runId = String(event.skill_run_id);
    const label = String(event.label ?? event.skill_id);
    skillSteps = [
      ...skillSteps,
      {
        skillRunId: runId,
        skillId: String(event.skill_id),
        label,
        status: "running",
        nested: emptySkillStreamSlice(),
      },
    ];
    activeSkillRunId = runId;
    const line = `▶ ${label}`;
    if (streamLog[streamLog.length - 1] !== line) {
      streamLog = [...streamLog, line];
    }
  }

  if (event.type === "skill_done" && event.skill_run_id) {
    const runId = String(event.skill_run_id);
    skillSteps = skillSteps.map((s) =>
      s.skillRunId === runId
        ? {
            ...s,
            status: "done" as const,
            summary: event.summary ? String(event.summary) : s.summary,
          }
        : s,
    );
    if (activeSkillRunId === runId) {
      activeSkillRunId = undefined;
    }
  }

  if (skillRunId) {
    activeSkillRunId = skillRunId;
    skillSteps = skillSteps.map((s) =>
      s.skillRunId === skillRunId ? { ...s, nested: applyCoreStreamEvent(s.nested, event, t) } : s,
    );
  } else if (event.type !== "skill_start" && event.type !== "skill_done") {
    const topSlice: SkillStreamSlice = {
      streamStatus,
      streamLog,
      agentSteps,
      judgeVerdict,
      activeStreamIds,
    };
    const next = applyCoreStreamEvent(topSlice, event, t);
    streamStatus = next.streamStatus;
    streamLog = next.streamLog;
    agentSteps = next.agentSteps;
    judgeVerdict = next.judgeVerdict;
    activeStreamIds = next.activeStreamIds;
  }

  return {
    streamStatus,
    streamLog,
    agentSteps,
    judgeVerdict,
    activeStreamIds,
    skillSteps,
    activeSkillRunId,
  };
}
