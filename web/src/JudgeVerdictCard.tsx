import { MarkdownContent } from "./MarkdownContent";
import { useI18n } from "./i18n";
import type { HoldingAction, JudgeVerdict } from "./StreamFeed";
import { localizePositionAction, positionActionCssClass } from "./uiLabels";

interface JudgeVerdictCardProps {
  verdict: JudgeVerdict;
  isTyping: boolean;
}

export function JudgeVerdictCard({ verdict, isTyping }: JudgeVerdictCardProps) {
  const { t } = useI18n();
  const actionKey = positionActionCssClass(verdict.position_action ?? "仓位适中");

  return (
    <div className={`message assistant stream-msg stream-judge action-${actionKey}`}>
      <div className="stream-msg-head">
        <strong>{t("stream.judge")}</strong>
        {isTyping && <span className="muted">{t("stream.typing")}</span>}
      </div>
      {(verdict.risk_level || verdict.position_action) && (
        <p className="stream-msg-meta">
          {verdict.risk_level && (
            <span>
              {t("stream.overallRisk")}: {verdict.risk_level}{" "}
            </span>
          )}
          {verdict.position_action && (
            <span>
              {t("stream.portfolioBias")}:{" "}
              {localizePositionAction(verdict.position_action ?? "", t)}
            </span>
          )}
        </p>
      )}

      {verdict.holding_actions && verdict.holding_actions.length > 0 ? (
        <>
          {verdict.analysis_process && (
            <>
              <p className="stream-section-title">{t("stream.process")}</p>
              <div className="stream-msg-body">
                <MarkdownContent text={verdict.analysis_process} />
              </div>
            </>
          )}
          <p className="stream-section-title">
            {t("stream.perStock", { n: verdict.holding_actions.length })}
          </p>
          <div className="holding-action-list">
            {verdict.holding_actions.map((item: HoldingAction) => (
              <div
                key={item.symbol}
                className={`holding-action action-${positionActionCssClass(item.action)}`}
              >
                <div className="holding-action-head">
                  <strong>
                    {item.name}（{item.symbol}）
                  </strong>
                  <span className="holding-action-badge">
                    {localizePositionAction(item.action, t)}
                  </span>
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
            <MarkdownContent text={verdict.summary} />
          </div>
          {verdict.reason && verdict.reason !== verdict.summary && (
            <div className="stream-msg-body muted">
              <MarkdownContent text={verdict.reason} />
            </div>
          )}
          {verdict.divergence && (
            <div className="stream-msg-body muted">
              <MarkdownContent text={`${t("stream.divergence")}: ${verdict.divergence}`} />
            </div>
          )}
        </>
      ) : (
        <>
          <div className="stream-msg-body">
            <MarkdownContent text={verdict.summary} />
            {isTyping && <span className="stream-cursor">▍</span>}
          </div>
          {verdict.reason && verdict.reason !== verdict.summary && (
            <div className="stream-msg-body muted">
              <MarkdownContent text={verdict.reason} />
            </div>
          )}
          {verdict.divergence && (
            <div className="stream-msg-body muted">
              <MarkdownContent text={`${t("stream.divergence")}: ${verdict.divergence}`} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
