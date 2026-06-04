import { ABOUT_INFO } from "./aboutInfo";

interface AboutPanelProps {
  open: boolean;
  onClose: () => void;
}

export function AboutPanel({ open, onClose }: AboutPanelProps) {
  if (!open) return null;

  return (
    <div className="settings-overlay" role="dialog" aria-modal="true" aria-labelledby="about-title">
      <div className="settings-backdrop" onClick={onClose} />
      <div className="settings-panel about-panel">
        <div className="settings-header">
          <h3 id="about-title">关于</h3>
          <button type="button" className="btn btn-ghost settings-close" onClick={onClose}>
            关闭
          </button>
        </div>

        <p className="about-product">{ABOUT_INFO.product}</p>
        <p className="settings-hint">{ABOUT_INFO.tagline}</p>

        <dl className="about-dl">
          <dt>作者</dt>
          <dd>{ABOUT_INFO.author}</dd>

          <dt>GitHub</dt>
          <dd>
            <a href={ABOUT_INFO.repoUrl} target="_blank" rel="noopener noreferrer">
              {ABOUT_INFO.repoUrl}
            </a>
          </dd>

          <dt>邮箱</dt>
          <dd>
            <a href={`mailto:${ABOUT_INFO.email}`}>{ABOUT_INFO.email}</a>
          </dd>

          <dt>小红书</dt>
          <dd>
            <a href={ABOUT_INFO.xiaohongshuUrl} target="_blank" rel="noopener noreferrer">
              {ABOUT_INFO.xiaohongshuId}
            </a>
          </dd>
        </dl>

        <h4 className="about-section-title">参考开源项目</h4>
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

        <p className="settings-hint about-disclaimer">
          本产品所有 AI 输出仅供学习参考，不构成投资建议。
        </p>
      </div>
    </div>
  );
}
