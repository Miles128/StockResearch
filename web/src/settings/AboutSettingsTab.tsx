import { ABOUT_INFO } from "../aboutInfo";
import { useI18n } from "../i18n";

export function AboutSettingsTab() {
  const { t } = useI18n();

  return (
    <div className="about-panel about-panel-inline">
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
    </div>
  );
}
