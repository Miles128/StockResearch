import { useI18n } from "./i18n";

interface DemoBannerProps {
  onLoad: () => void;
  onClear: () => void;
  onGoPortfolio?: () => void;
  isDemo: boolean;
  loading: boolean;
}

export function DemoBanner({ onLoad, onClear, onGoPortfolio, isDemo, loading }: DemoBannerProps) {
  const { t } = useI18n();

  if (isDemo) {
    return (
      <div className="demo-banner demo-banner-active">
        <span className="demo-banner-text">{t("demo.active")}</span>
        {onGoPortfolio && (
          <button type="button" className="btn btn-sm btn-ghost" onClick={onGoPortfolio}>
            {t("demo.replace")}
          </button>
        )}
        <button type="button" className="btn btn-sm btn-ghost" onClick={onClear} disabled={loading}>
          {t("demo.clear")}
        </button>
      </div>
    );
  }

  return (
    <div className="demo-banner">
      <span className="demo-banner-text">{t("demo.hint")}</span>
      <button type="button" className="btn btn-sm btn-primary" onClick={onLoad} disabled={loading}>
        {t("demo.load")}
      </button>
    </div>
  );
}
