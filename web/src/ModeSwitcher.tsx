/**
 * 顶栏模式切换器：个人 / 专家
 * 与中/EN 语言切换同级，常驻顶栏
 */

import { useI18n } from "./i18n";
import type { AppMode, ModeSettings } from "./modeSettings";
import { isPristinePreset } from "./modeSettings";

interface ModeSwitcherProps {
  settings: ModeSettings;
  onSwitch: (mode: AppMode) => void;
}

export function ModeSwitcher({ settings, onSwitch }: ModeSwitcherProps) {
  const { t } = useI18n();
  const pristine = isPristinePreset(settings);

  return (
    <div className="mode-switcher" role="tablist" aria-label={t("mode.switchTitle")}>
      <button
        type="button"
        role="tab"
        aria-selected={settings.mode === "advisor"}
        className={`mode-btn${settings.mode === "advisor" ? " active" : ""}`}
        onClick={() => onSwitch("advisor")}
        title={t("mode.advisorHint")}
      >
        {t("mode.advisor")}
        {settings.mode === "advisor" && !pristine && (
          <span className="mode-customized-badge" title={t("mode.customized")}>
            *
          </span>
        )}
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={settings.mode === "research"}
        className={`mode-btn${settings.mode === "research" ? " active" : ""}`}
        onClick={() => onSwitch("research")}
        title={t("mode.researchHint")}
      >
        {t("mode.research")}
        {settings.mode === "research" && !pristine && (
          <span className="mode-customized-badge" title={t("mode.customized")}>
            *
          </span>
        )}
      </button>
    </div>
  );
}
