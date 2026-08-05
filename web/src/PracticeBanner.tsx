/**
 * 新手带练横幅：首次进入投顾模式时引导用户用 demo 标的走一遍完整流程。
 * PRD §11.4 S4 — 新用户 5 分钟出第一份看得懂的研报。
 */
import { useI18n } from "./i18n";

export function PracticeBanner({
  onStart,
  onDismiss,
}: {
  onStart: () => void;
  onDismiss: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="practice-banner">
      <div className="practice-banner-text">
        <strong>{t("practice.title")}</strong>
        <p>{t("practice.hint")}</p>
      </div>
      <div className="practice-banner-actions">
        <button type="button" className="practice-start-btn" onClick={onStart}>
          {t("practice.start")}
        </button>
        <button type="button" className="practice-later-btn" onClick={onDismiss}>
          {t("practice.later")}
        </button>
      </div>
    </div>
  );
}
