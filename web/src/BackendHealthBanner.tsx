import { useEffect, useState } from "react";
import { useI18n } from "./i18n";

type HealthState = "ok" | "unreachable" | "wrong-service" | "checking";

/**
 * 检测后端 :8000 是否可访问且为 StockResearch API。
 *
 * - 网络错误 / 超时 → unreachable：提示启动 uvicorn
 * - 返回非 JSON 或字段缺失 → wrong-service：提示端口被其他服务占用
 * - status==="ok" → 隐藏
 *
 * 仅在 mount 时探测一次，结果可由用户关闭。
 */
export function BackendHealthBanner() {
  const { t } = useI18n();
  const [state, setState] = useState<HealthState>("checking");
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function probe() {
      try {
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), 4000);
        const resp = await fetch("/health", { signal: controller.signal });
        clearTimeout(id);
        if (cancelled) return;
        const ct = resp.headers.get("content-type") || "";
        if (!resp.ok || !ct.includes("application/json")) {
          setState("wrong-service");
          return;
        }
        const data = (await resp.json().catch(() => null)) as { status?: string } | null;
        if (data && data.status === "ok") {
          setState("ok");
        } else {
          setState("wrong-service");
        }
      } catch {
        if (!cancelled) setState("unreachable");
      }
    }
    void probe();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state === "ok" || state === "checking" || dismissed) return null;

  const title =
    state === "unreachable" ? t("health.unreachableTitle") : t("health.wrongServiceTitle");
  const hint =
    state === "unreachable" ? t("health.unreachableHint") : t("health.wrongServiceHint");

  return (
    <div className="backend-health-banner" role="alert">
      <div className="backend-health-banner-body">
        <strong>{title}</strong>
        <span className="muted">{hint}</span>
      </div>
      <button
        type="button"
        className="btn btn-ghost btn-sm"
        onClick={() => setDismissed(true)}
        aria-label="close"
      >
        ×
      </button>
    </div>
  );
}
