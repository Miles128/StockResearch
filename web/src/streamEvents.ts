import type { AgentStreamEvent } from "./api";
import {
  detectDimensionKind,
  localizeAgentName,
  shouldSeedDimensions,
  shouldSkipStatusLog,
} from "./streamI18n";
import { localizePositionAction, localizeVoteLabel } from "./uiLabels";
import type { TParams } from "./i18n";
import { stripDisclaimer } from "./disclaimerText";
import {
  detectDimensionSet,
  dimensionDefsForKind,
  isDimensionAgent,
  seedDimensionSteps,
} from "./dimensionStream";
import type { AgentStep, DebateRound, JudgeVerdict, HoldingAction } from "./StreamFeed";

export interface VoteTally {
  bullish: number;
  bearish: number;
  neutral: number;
  leading?: string;
}

export interface StreamState {
  streamStatus: string;
  streamLog: string[];
  agentSteps: AgentStep[];
  debateRounds: DebateRound[];
  judgeVerdict: JudgeVerdict | null;
  voteTally: VoteTally | null;
  activeStreamIds: string[];
}

const DEBATE_AGENT_SIDES: Record<string, string> = {
  bull: "bull",
  bear: "bear",
  aggressive: "aggressive",
  neutral: "neutral",
  conservative: "conservative",
};

function activateStream(active: string[], streamId: string): string[] {
  if (active.includes(streamId)) {
    return active;
  }
  return [...active, streamId];
}

function deactivateAgentStream(active: string[], agentId: string, role?: string): string[] {
  if (role === "vote") {
    return active.filter((id) => id !== `vote-${agentId}` && id !== agentId);
  }
  const side = role ? DEBATE_AGENT_SIDES[role] : undefined;
  if (side) {
    return active.filter((id) => !id.endsWith(`-${side}`));
  }
  return active.filter((id) => id !== agentId);
}

const DEBATE_SIDE_KEYS: Record<string, keyof DebateRound> = {
  bull: "bull",
  bear: "bear",
  aggressive: "aggressive",
  neutral: "neutral",
  conservative: "conservative",
};

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

function upsertDebateDelta(
  rounds: DebateRound[],
  roundNum: number,
  side: keyof DebateRound,
  delta: string,
): DebateRound[] {
  const existing = rounds.find((r) => r.round === roundNum);
  const prev = typeof existing?.[side] === "string" ? (existing[side] as string) : "";
  const nextRound: DebateRound = {
    round: roundNum,
    ...existing,
    [side]: `${prev}${delta}`,
  };
  return [...rounds.filter((r) => r.round !== roundNum), nextRound];
}

function applyTextDelta(
  prev: StreamState,
  streamId: string,
  delta: string,
  meta?: { agent_id?: string; agent_name?: string; role?: string },
): Pick<StreamState, "agentSteps" | "debateRounds" | "judgeVerdict"> {
  const roundMatch = streamId.match(/^r(\d+)-(\w+)$/);
  if (roundMatch) {
    const roundNum = Number(roundMatch[1]);
    const sideKey = DEBATE_SIDE_KEYS[roundMatch[2]];
    if (sideKey) {
      return {
        agentSteps: prev.agentSteps,
        debateRounds: upsertDebateDelta(prev.debateRounds, roundNum, sideKey, delta),
        judgeVerdict: prev.judgeVerdict,
      };
    }
  }

  if (streamId === "judge") {
    const summary = `${prev.judgeVerdict?.summary ?? ""}${delta}`;
    return {
      agentSteps: prev.agentSteps,
      debateRounds: prev.debateRounds,
      judgeVerdict: {
        ...(prev.judgeVerdict ?? { summary: "", reason: "" }),
        summary,
        reason: summary,
      },
    };
  }

  return {
    agentSteps: upsertAgentContent(prev.agentSteps, streamId, delta, meta),
    debateRounds: prev.debateRounds,
    judgeVerdict: prev.judgeVerdict,
  };
}

export function emptyStreamState(): StreamState {
  return {
    streamStatus: "",
    streamLog: [],
    agentSteps: [],
    debateRounds: [],
    judgeVerdict: null,
    voteTally: null,
    activeStreamIds: [],
  };
}

type TFn = (key: string, params?: TParams) => string;

export function applyStreamEvent(
  prev: StreamState,
  event: AgentStreamEvent,
  t?: TFn,
): StreamState {
  let {
    streamStatus,
    streamLog,
    agentSteps,
    debateRounds,
    judgeVerdict,
    voteTally,
    activeStreamIds,
  } = prev;

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
    const updated = applyTextDelta(prev, event.stream_id, event.delta, meta);
    agentSteps = updated.agentSteps;
    debateRounds = updated.debateRounds;
    judgeVerdict = updated.judgeVerdict;
    activeStreamIds = activateStream(activeStreamIds, event.stream_id);
  }

  if (event.type === "manager" && event.content) {
    agentSteps = agentSteps.map((s) =>
      s.agent_id === "research_manager"
        ? { ...s, content: event.content, status: "done" as const }
        : s,
    );
  }

  if (event.type === "agent_start" && event.agent_id && event.agent_name && event.role) {
    const agentName =
      t != null
        ? localizeAgentName(event.agent_id, event.agent_name, t)
        : event.agent_name;
    const dimensionAgent = isDimensionAgent(event.agent_id);
    if (!dimensionAgent) {
      const startLine = t
        ? t("stream.agentStarted", { name: agentName })
        : `▶ ${agentName} 开始`;
      if (streamLog[streamLog.length - 1] !== startLine) {
        streamLog = [...streamLog, startLine];
      }
    } else {
      const kind = detectDimensionKind(
        { type: "status", message: streamStatus },
        streamStatus,
      );
      const defs = t
        ? dimensionDefsForKind(kind, t)
        : detectDimensionSet(agentSteps, streamStatus, kind);
      agentSteps = seedDimensionSteps(agentSteps, defs);
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
    if (!dimensionAgent) {
      const doneName =
        agentSteps.find((s) => s.agent_id === event.agent_id)?.agent_name ?? event.agent_id;
      const doneLine = t
        ? t("stream.agentDone", { name: doneName })
        : `✓ ${doneName} 完成`;
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
    activeStreamIds = deactivateAgentStream(activeStreamIds, event.agent_id, event.role);
  }

  if (event.type === "debate_round" && event.round != null) {
    const roundLine = t
      ? t("stream.debateRoundDone", { n: event.round ?? 0 })
      : `◆ 第 ${event.round} 轮多空交锋完成`;
    if (streamLog[streamLog.length - 1] !== roundLine) {
      streamLog = [...streamLog, roundLine];
    }
    debateRounds = [
      ...debateRounds.filter((r) => r.round !== event.round),
      {
        round: event.round,
        bull: event.bull ? stripDisclaimer(String(event.bull)) : event.bull,
        bear: event.bear ? stripDisclaimer(String(event.bear)) : event.bear,
        aggressive: event.aggressive
          ? stripDisclaimer(String(event.aggressive))
          : event.aggressive,
        neutral: event.neutral_view
          ? stripDisclaimer(String(event.neutral_view))
          : event.neutral_view,
        conservative: event.conservative
          ? stripDisclaimer(String(event.conservative))
          : event.conservative,
      },
    ];
  }

  if (event.type === "vote" && event.agent_name && event.vote) {
    const voteLine = t
      ? t("stream.voteLine", {
          name: event.agent_name,
          vote: localizeVoteLabel(String(event.vote), t),
        })
      : `${event.agent_name} 投票：${event.vote}`;
    streamLog = [...streamLog, voteLine];
  }

  if (event.type === "vote_tally") {
    voteTally = {
      bullish: event.bullish ?? 0,
      bearish: event.bearish ?? 0,
      neutral: event.neutral ?? 0,
      leading: event.leading,
    };
    const voteMsg = t
      ? t("stream.voteBody", {
          bull: event.bullish ?? 0,
          bear: event.bearish ?? 0,
          neutral: event.neutral ?? 0,
          leading: event.leading
            ? t("stream.leading", {
                value: localizeVoteLabel(String(event.leading), t),
              })
            : "",
        })
      : event.message;
    if (voteMsg) {
      streamStatus = voteMsg;
      if (streamLog[streamLog.length - 1] !== voteMsg) {
        streamLog = [...streamLog, voteMsg];
      }
    }
  }

  if (event.type === "judge") {
    activeStreamIds = activeStreamIds.filter((id) => id !== "judge");
    const biasLabel = t
      ? event.verdict === "bullish"
        ? t("card.bullish")
        : event.verdict === "bearish"
          ? t("card.bearish")
          : event.verdict === "neutral"
            ? t("card.neutral")
            : undefined
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
      reason: stripDisclaimer(
        String(event.reason ?? event.summary ?? judgeVerdict?.reason ?? ""),
      ),
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
    debateRounds,
    judgeVerdict,
    voteTally,
    activeStreamIds,
  };
}
