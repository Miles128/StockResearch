import type { AgentStreamEvent } from "./api";
import type { AgentStep, DebateRound, JudgeVerdict } from "./StreamFeed";

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

function upsertAgentContent(steps: AgentStep[], streamId: string, delta: string): AgentStep[] {
  const existing = steps.find((s) => s.agent_id === streamId);
  if (existing) {
    return steps.map((s) =>
      s.agent_id === streamId
        ? { ...s, content: `${s.content ?? ""}${delta}`, status: "running" }
        : s,
    );
  }
  return [
    ...steps,
    {
      agent_id: streamId,
      agent_name: streamId,
      role: "analyst",
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
    agentSteps: upsertAgentContent(prev.agentSteps, streamId, delta),
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

export function applyStreamEvent(prev: StreamState, event: AgentStreamEvent): StreamState {
  let {
    streamStatus,
    streamLog,
    agentSteps,
    debateRounds,
    judgeVerdict,
    voteTally,
    activeStreamIds,
  } = prev;

  if (event.type === "status" && event.message) {
    streamStatus = event.message;
    if (streamLog[streamLog.length - 1] !== event.message) {
      streamLog = [...streamLog, event.message];
    }
  }

  if (event.type === "text_delta" && event.stream_id && event.delta) {
    const updated = applyTextDelta(prev, event.stream_id, event.delta);
    agentSteps = updated.agentSteps;
    debateRounds = updated.debateRounds;
    judgeVerdict = updated.judgeVerdict;
    activeStreamIds = activateStream(activeStreamIds, event.stream_id);
  }

  if (event.type === "agent_start" && event.agent_id && event.agent_name && event.role) {
    agentSteps = [
      ...agentSteps.filter((s) => s.agent_id !== event.agent_id),
      {
        agent_id: event.agent_id,
        agent_name: event.agent_name,
        role: event.role,
        status: "running",
        content: "",
      },
    ];
  }

  if (event.type === "agent_done" && event.agent_id) {
    agentSteps = agentSteps.map((s) =>
      s.agent_id === event.agent_id
        ? { ...s, status: "done", content: event.content ?? s.content ?? "" }
        : s,
    );
    activeStreamIds = deactivateAgentStream(activeStreamIds, event.agent_id, event.role);
  }

  if (event.type === "debate_round" && event.round != null) {
    debateRounds = [
      ...debateRounds.filter((r) => r.round !== event.round),
      {
        round: event.round,
        bull: event.bull,
        bear: event.bear,
        aggressive: event.aggressive,
        neutral: event.neutral_view,
        conservative: event.conservative,
      },
    ];
  }

  if (event.type === "vote" && event.agent_name && event.vote) {
    streamLog = [...streamLog, `${event.agent_name} 投票：${event.vote}`];
  }

  if (event.type === "vote_tally") {
    voteTally = {
      bullish: event.bullish ?? 0,
      bearish: event.bearish ?? 0,
      neutral: event.neutral ?? 0,
      leading: event.leading,
    };
    if (event.message) {
      streamStatus = event.message;
      if (streamLog[streamLog.length - 1] !== event.message) {
        streamLog = [...streamLog, event.message];
      }
    }
  }

  if (event.type === "judge") {
    activeStreamIds = activeStreamIds.filter((id) => id !== "judge");
    const biasLabel =
      event.verdict === "bullish"
        ? "偏多"
        : event.verdict === "bearish"
          ? "偏空"
          : event.verdict === "neutral"
            ? "中性"
            : undefined;
    judgeVerdict = {
      risk_level: event.risk_level ?? biasLabel,
      position_action: event.position_action,
      summary: event.summary ?? event.content ?? judgeVerdict?.summary ?? "",
      reason: event.reason ?? event.summary ?? judgeVerdict?.reason ?? "",
      divergence: event.divergence,
      verdict: event.verdict,
      content: event.content,
      analysis_process: event.analysis_process,
      holding_actions: event.holding_actions,
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
