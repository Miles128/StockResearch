import type { QuotePriceConflict } from "./api";
import { useI18n } from "./i18n";

interface PriceConflictBannerProps {
  conflicts: QuotePriceConflict[];
}

export function PriceConflictBanner({ conflicts }: PriceConflictBannerProps) {
  const { t } = useI18n();
  if (conflicts.length === 0) return null;

  const preview = conflicts
    .slice(0, 2)
    .map((item) => `${item.name}(${item.diff_pct.toFixed(1)}%)`)
    .join(" · ");

  return (
    <div className="price-conflict-banner" role="status">
      <strong>{t("data.priceConflictTitle")}</strong>
      <span>
        {t("data.priceConflictBody", {
          count: String(conflicts.length),
          preview,
        })}
      </span>
    </div>
  );
}
