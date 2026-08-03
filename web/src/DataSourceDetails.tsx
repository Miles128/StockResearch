import type { DataSourceDetail, DataSourceStatus } from "./api";
import { useI18n } from "./i18n";

interface DataSourceDetailsProps {
  status: DataSourceStatus | null;
  onClose: () => void;
}

function statusText(item: DataSourceDetail, locale: "zh" | "en"): string {
  if (locale === "en") {
    const map: Record<DataSourceDetail["status"], string> = {
      ok: "OK",
      degraded: "Degraded",
      missing: "Missing",
      mock: "Mock",
      configured: "Configured",
      not_configured: "Not configured",
    };
    return map[item.status];
  }
  const map: Record<DataSourceDetail["status"], string> = {
    ok: "正常",
    degraded: "降级",
    missing: "缺失",
    mock: "Mock",
    configured: "已配置",
    not_configured: "未配置",
  };
  return map[item.status];
}

function confidenceText(
  confidence: DataSourceDetail["confidence"],
  locale: "zh" | "en",
): string {
  if (locale === "en") {
    const map: Record<DataSourceDetail["confidence"], string> = {
      verified: "Verified",
      single_source: "Single source",
      delayed: "Delayed",
      cached: "Cached",
      conflict: "Conflict",
      missing: "Missing",
    };
    return map[confidence];
  }
  const map: Record<DataSourceDetail["confidence"], string> = {
    verified: "已验证",
    single_source: "单源",
    delayed: "延迟",
    cached: "缓存",
    conflict: "冲突",
    missing: "缺失",
  };
  return map[confidence];
}

function formatTime(value: string | null, locale: "zh" | "en"): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(locale === "zh" ? "zh-CN" : "en-US", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function DataSourceDetails({ status, onClose }: DataSourceDetailsProps) {
  const { locale } = useI18n();
  const details = status?.details ?? [];
  const degraded = details.some(
    (item) => item.status === "degraded" || item.status === "missing",
  );

  return (
    <div className="modal-overlay" role="presentation" onMouseDown={onClose}>
      <section
        className="modal data-source-modal"
        role="dialog"
        aria-modal="true"
        aria-label={locale === "zh" ? "数据源详情" : "Data source details"}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <div>
            <span className="canvas-kicker">
              {locale === "zh" ? "DATA SOURCES" : "DATA SOURCES"}
            </span>
            <h3>{locale === "zh" ? "数据源详情" : "Data source details"}</h3>
            <p className="muted">
              {locale === "zh"
                ? "查看当前行情、市场和增强数据的来源、缓存、Mock 与降级状态。"
                : "Inspect source, cache, mock and degradation status for current market data."}
            </p>
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={onClose}
          >
            {locale === "zh" ? "关闭" : "Close"}
          </button>
        </header>

        <div className={`data-source-summary${degraded ? " degraded" : ""}`}>
          <strong>
            {degraded
              ? locale === "zh"
                ? "存在降级或缺失"
                : "Degraded or missing"
              : locale === "zh"
                ? "数据状态正常"
                : "Data status OK"}
          </strong>
          <span>
            {locale === "zh"
              ? "当前使用真实外网数据或本地缓存"
              : "Using live external data or local cache"}
          </span>
        </div>

        <div className="data-source-list">
          {details.map((item) => (
            <article
              className="data-source-item"
              key={`${item.domain}-${item.label}`}
            >
              <div className="data-source-item-main">
                <div>
                  <span className="data-source-layer">{item.layer}</span>
                  <h4>{item.label}</h4>
                  <p>{item.source}</p>
                </div>
                <span className={`source-status-pill ${item.status}`}>
                  {statusText(item, locale)}
                </span>
              </div>
              <dl>
                <div>
                  <dt>{locale === "zh" ? "可信度" : "Confidence"}</dt>
                  <dd>{confidenceText(item.confidence, locale)}</dd>
                </div>
                <div>
                  <dt>{locale === "zh" ? "获取时间" : "Fetched"}</dt>
                  <dd>{formatTime(item.fetched_at, locale)}</dd>
                </div>
                <div>
                  <dt>{locale === "zh" ? "缓存 / Mock" : "Cache / Mock"}</dt>
                  <dd>
                    {item.is_cached
                      ? locale === "zh"
                        ? "缓存"
                        : "Cached"
                      : "Live"}
                    {item.is_mock ? " · Mock" : ""}
                  </dd>
                </div>
              </dl>
              {item.degraded_reason && (
                <p className="data-source-reason">{item.degraded_reason}</p>
              )}
            </article>
          ))}
          {details.length === 0 && (
            <p className="muted">
              {locale === "zh"
                ? "暂无数据源状态，刷新行情后再查看。"
                : "No data source status yet. Refresh market data first."}
            </p>
          )}
        </div>
      </section>
    </div>
  );
}
