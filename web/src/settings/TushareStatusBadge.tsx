import { useEffect, useState } from "react";
import { api } from "../api";
import { useI18n } from "../i18n";

type TushareState = "checking" | "ok" | "no_token" | "invalid" | "quota" | "unavailable";

export function TushareStatusBadge() {
  const { t } = useI18n();
  const [state, setState] = useState<TushareState>("checking");

  useEffect(() => {
    let alive = true;
    api
      .dataSourceStatus()
      .then((status) => {
        if (!alive) return;
        const probe = status.tushare_status;
        if (probe === "ok" || probe === "no_token" || probe === "invalid" || probe === "quota" || probe === "unavailable") {
          setState(probe);
          return;
        }
        if (status.tushare_configured && status.tushare_available) setState("ok");
        else if (!status.tushare_configured) setState("no_token");
        else setState("unavailable");
      })
      .catch(() => {
        if (alive) setState("unavailable");
      });
    return () => {
      alive = false;
    };
  }, []);

  const text =
    state === "checking"
      ? t("settings.tushareStatusChecking")
      : state === "ok"
        ? t("settings.tushareStatusOk")
        : state === "no_token"
          ? t("settings.tushareStatusNoToken")
          : state === "invalid"
            ? t("settings.tushareStatusInvalid")
            : state === "quota"
              ? t("settings.tushareStatusQuota")
              : t("settings.tushareStatusUnavailable");

  return (
    <div className="tushare-status-block">
      <p className={`tushare-status tushare-status-${state}`}>{text}</p>
      <p className="settings-muted">{t("settings.tushareUsage")}</p>
    </div>
  );
}
