import { MarkdownContent } from "./MarkdownContent";
import { useI18n } from "./i18n";

interface AgentStep {
  agent_id: string;
  agent_name: string;
  role: string;
  content?: string;
  status: "running" | "done";
}

interface DebateRound {
  round: number;
  bull?: string;
  bear?: string;
  aggressive?: string;
  neutral?: string;
  neutral_view?: string;
  conservative?: string;
}

interface JudgeVerdict {
  risk_level?: string;
  position_action?: string;
  summary: string;
  reason?: string;
  divergence?: string;
  verdict?: string;
  content?: string;
  analysis_process?: string;
  holding_actions?: HoldingAction[];
}

export interface HoldingAction {
  symbol: string;
  name: string;
  action: string;
  reason: string;
  priority?: string;
}

interface StreamFeedProps {
  streamStatus: string;
  streamLog: string[];
  agentSteps: AgentStep[];
  debateRounds: DebateRound[];
  judgeVerdict: JudgeVerdict | null;
  voteTally: { bullish: number; bearish: number; neutral: number; leading?: string } | null;
  activeStreamIds?: string[];
}

const DEBATE_ROLES = new Set(["bull", "bear", "aggressive", "neutral", "conservative"]);
const SUMMARY_ROLES = new Set(["manager", "judge"]);

function earlyPipelineSteps(steps: AgentStep[]): AgentStep[] {
  return steps.filter((step) => !DEBATE_ROLES.has(step.role) && !SUMMARY_ROLES.has(step.role));
}

function managerStep(steps: AgentStep[]): AgentStep | undefined {
  return steps.find((step) => step.role === "manager" || step.agent_id === "research_manager");
}

function StreamMessage({
  title,
  body,
  running,
  streaming,
  className,
  typingLabel,
  analyzingLabel,
}: {
  title: string;
  body?: string;
  running?: boolean;
  streaming?: boolean;
  className?: string;
  typingLabel: string;
  analyzingLabel: string;
}) {
  const typing = streaming ?? (running === true && body !== undefined && body !== "");
  return (
    <div className={`message assistant stream-msg ${className ?? ""}`.trim()}>
      <div className="stream-msg-head">
        <strong>{title}</strong>
        {typing && <span className="muted">{typingLabel}</span>}
        {running && !body && <span className="muted">{analyzingLabel}</span>}
      </div>
      {body !== undefined && body !== "" && (
        <div className="stream-msg-body">
          <MarkdownContent text={body} />
          {typing && <span className="stream-cursor">▍</span>}
        </div>
      )}
      {running && !body && <p className="muted">…</p>}
    </div>
  );
}

export function StreamFeed({
  streamStatus,
  streamLog,
  agentSteps,
  debateRounds,
  judgeVerdict,
  voteTally,
  activeStreamIds = [],
}: StreamFeedProps) {
  const { t } = useI18n();
  const pipeline = earlyPipelineSteps(agentSteps);
  const debateAgents = agentSteps.filter((step) => DEBATE_ROLES.has(step.role));
  const manager = managerStep(agentSteps);
  const sortedRounds = debateRounds.slice().sort((a, b) => a.round - b.round);
  const isTyping = (streamId: string) => activeStreamIds.includes(streamId);
  const hasBody =
    streamLog.length > 0 ||
    pipeline.length > 0 ||
    debateAgents.length > 0 ||
    sortedRounds.length > 0 ||
    voteTally != null ||
    manager != null ||
    judgeVerdict != null;

  const sideLabel: Record<string, string> = {
    bull: t("stream.long"),
    bear: t("stream.short"),
    aggressive: t("stream.aggressive"),
    neutral: t("stream.neutral"),
    conservative: t("stream.conservative"),
  };

  function debateSides(round: DebateRound): { key: string; label: string; text: string }[] {
    const sides: { key: string; label: string; text: string }[] = [];
    if (round.bull) sides.push({ key: "bull", label: sideLabel.bull, text: round.bull });
    if (round.bear) sides.push({ key: "bear", label: sideLabel.bear, text: round.bear });
    if (round.aggressive) sides.push({ key: "aggressive", label: sideLabel.aggressive, text: round.aggressive });
    const neutralText = round.neutral ?? round.neutral_view;
    if (neutralText) sides.push({ key: "neutral", label: sideLabel.neutral, text: neutralText });
    if (round.conservative) sides.push({ key: "conservative", label: sideLabel.conservative, text: round.conservative });
    return sides;
  }

  const msgProps = { typingLabel: t("stream.typing"), analyzingLabel: t("stream.analyzing") };

  return (
    <div className="stream-messages">
      {!hasBody && streamStatus && (
        <p className="stream-status stream-status-active">{streamStatus}</p>
      )}
      {!hasBody && !streamStatus && (
        <p className="stream-status muted">{t("stream.waiting")}</p>
      )}
      {streamLog.map((line, i) => (
        <p className="stream-status muted" key={`${i}-${line.slice(0, 12)}`}>
          {line}
        </p>
      ))}
      {streamStatus && streamLog[streamLog.length - 1] !== streamStatus && (
        <p className="stream-status stream-status-active">{streamStatus}</p>
      )}

      {pipeline.map((step) => (
        <StreamMessage
          key={step.agent_id}
          title={step.agent_name}
          body={step.content}
          running={step.status === "running"}
          streaming={
            isTyping(step.agent_id) ||
            activeStreamIds.some(
              (id) => id === `vote-${step.agent_id}` || id.endsWith(`-${step.agent_id}`),
            )
          }
          className={`stream-role-${step.role}`}
          {...msgProps}
        />
      ))}

      {debateAgents.map((step) => (
        <StreamMessage
          key={`debate-agent-${step.agent_id}`}
          title={step.agent_name}
          body={step.content}
          running={step.status === "running"}
          streaming={
            isTyping(step.agent_id) ||
            activeStreamIds.some((id) => id.match(new RegExp(`-${step.role}$`)))
          }
          className={`stream-role-${step.role}`}
          {...msgProps}
        />
      ))}

      {sortedRounds.map((round) =>
        debateSides(round).map((side) => (
          <StreamMessage
            key={`${round.round}-${side.key}`}
            title={`${t("stream.round", { n: round.round })} · ${side.label}`}
            body={side.text}
            streaming={isTyping(`r${round.round}-${side.key}`)}
            className={`stream-role-${side.key}`}
            {...msgProps}
          />
        )),
      )}

      {voteTally && (
        <StreamMessage
          title={t("stream.vote")}
          body={t("stream.voteBody", {
            bull: voteTally.bullish,
            bear: voteTally.bearish,
            neutral: voteTally.neutral,
            leading: voteTally.leading ? t("stream.leading", { value: voteTally.leading }) : "",
          })}
          {...msgProps}
        />
      )}

      {manager && (
        <StreamMessage
          key={manager.agent_id}
          title={manager.agent_name}
          body={manager.content}
          running={manager.status === "running"}
          streaming={isTyping(manager.agent_id)}
          className="stream-role-manager"
          {...msgProps}
        />
      )}

      {judgeVerdict && (
        <div className={`message assistant stream-msg stream-judge action-${judgeVerdict.position_action ?? "持有观望"}`}>
          <div className="stream-msg-head">
            <strong>{t("stream.judge")}</strong>
            {isTyping("judge") && <span className="muted">{t("stream.typing")}</span>}
          </div>
          {(judgeVerdict.risk_level || judgeVerdict.position_action) && (
            <p className="stream-msg-meta">
              {judgeVerdict.risk_level && (
                <span>{t("stream.overallRisk")}: {judgeVerdict.risk_level} </span>
              )}
              {judgeVerdict.position_action && (
                <span>{t("stream.portfolioBias")}: {judgeVerdict.position_action}</span>
              )}
            </p>
          )}

          {judgeVerdict.holding_actions && judgeVerdict.holding_actions.length > 0 ? (
            <>
              {judgeVerdict.analysis_process && (
                <>
                  <p className="stream-section-title">{t("stream.process")}</p>
                  <div className="stream-msg-body">
                    <MarkdownContent text={judgeVerdict.analysis_process} />
                  </div>
                </>
              )}
              <p className="stream-section-title">
                {t("stream.perStock", { n: judgeVerdict.holding_actions.length })}
              </p>
              <div className="holding-action-list">
                {judgeVerdict.holding_actions.map((item) => (
                  <div
                    key={item.symbol}
                    className={`holding-action action-${item.action}`}
                  >
                    <div className="holding-action-head">
                      <strong>
                        {item.name}（{item.symbol}）
                      </strong>
                      <span className="holding-action-badge">{item.action}</span>
                      {item.priority && (
                        <span className="muted holding-action-priority">
                          {t("stream.priority")} {item.priority}
                        </span>
                      )}
                    </div>
                    <div className="stream-msg-body">
                      <MarkdownContent text={item.reason} />
                    </div>
                  </div>
                ))}
              </div>
              <p className="stream-section-title">{t("stream.portfolioConclusion")}</p>
              <div className="stream-msg-body">
                <MarkdownContent text={judgeVerdict.summary} />
              </div>
              {judgeVerdict.reason && judgeVerdict.reason !== judgeVerdict.summary && (
                <div className="stream-msg-body muted">
                  <MarkdownContent text={judgeVerdict.reason} />
                </div>
              )}
              {judgeVerdict.divergence && (
                <div className="stream-msg-body muted">
                  <MarkdownContent text={`${t("stream.divergence")}: ${judgeVerdict.divergence}`} />
                </div>
              )}
            </>
          ) : (
            <>
              <div className="stream-msg-body">
                <MarkdownContent text={judgeVerdict.summary} />
                {isTyping("judge") && <span className="stream-cursor">▍</span>}
              </div>
              {judgeVerdict.reason && judgeVerdict.reason !== judgeVerdict.summary && (
                <div className="stream-msg-body muted">
                  <MarkdownContent text={judgeVerdict.reason} />
                </div>
              )}
              {judgeVerdict.divergence && (
                <div className="stream-msg-body muted">
                  <MarkdownContent text={`${t("stream.divergence")}: ${judgeVerdict.divergence}`} />
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export type { AgentStep, DebateRound, JudgeVerdict };
