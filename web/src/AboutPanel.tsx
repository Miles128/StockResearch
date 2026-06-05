import { ABOUT_INFO } from "./aboutInfo";
import { useI18n } from "./i18n";

interface AboutPanelProps {
  open: boolean;
  onClose: () => void;
}

export function AboutPanel({ open, onClose }: AboutPanelProps) {
  const { t } = useI18n();
  if (!open) return null;

  return (
    <div className="settings-overlay" role="dialog" aria-modal="true" aria-labelledby="about-title">
      <div className="settings-backdrop" onClick={onClose} />
      <div className="settings-panel about-panel">
        <div className="settings-header">
          <h3 id="about-title">{t("about.title")}</h3>
          <button type="button" className="btn btn-ghost settings-close" onClick={onClose}>
            {t("settings.close")}
          </button>
        </div>

        <p className="about-product">{ABOUT_INFO.product}</p>
        <p className="settings-hint">{t("about.tagline")}</p>

        <dl className="about-dl">
          <dt>{t("about.author")}</dt>
          <dd>{ABOUT_INFO.author}</dd>

          <dt>GitHub</dt>
          <dd>
            <a href={ABOUT_INFO.repoUrl} target="_blank" rel="noopener noreferrer">
              {ABOUT_INFO.repoUrl}
            </a>
          </dd>

          <dt>{t("about.email")}</dt>
          <dd>
            <a href={`mailto:${ABOUT_INFO.email}`}>{ABOUT_INFO.email}</a>
          </dd>

          <dt>{t("about.xiaohongshu")}</dt>
          <dd>
            <a href={ABOUT_INFO.xiaohongshuUrl} target="_blank" rel="noopener noreferrer">
              {ABOUT_INFO.xiaohongshuId}
            </a>
          </dd>
        </dl>

        <h4 className="about-section-title">{t("about.refs")}</h4>
        <ul className="about-ref-list">
          {ABOUT_INFO.references.map((ref) => (
            <li key={ref.url}>
              <a href={ref.url} target="_blank" rel="noopener noreferrer">
                {ref.name}
              </a>
              {ref.note && <span className="about-ref-note"> — {ref.note}</span>}
            </li>
          ))}
        </ul>

        <p className="settings-hint about-disclaimer">{t("about.disclaimer")}</p>
      </div>
    </div>
  );
}
