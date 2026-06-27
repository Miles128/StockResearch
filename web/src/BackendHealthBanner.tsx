import { useEffect, useState } from "react";
import { api } from "./api";
import { useI18n } from "./i18n";

export function BackendHealthBanner() {
  const { t } = useI18n();
  const [healthy, setHealthy] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const check = () => {
      void api.health().then((ok) => {
        if (!cancelled) setHealthy(ok);
      });
    };
    check();
    const id = window.setInterval(check, 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  if (healthy) return null;

  return (
    <div className="backend-health-banner" role="alert">
      {t("header.backendDown")}
    </div>
  );
}
