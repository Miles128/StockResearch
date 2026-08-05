import { useEffect, useState } from "react";
import { api, type PriceAlertNotification, type PriceAlertSettings } from "./api";
import { useI18n } from "./i18n";
import { IconBell } from "./ui/Icons";

interface PriceAlertBellProps {
  onSelectSymbol: (symbol: string, name: string) => void;
  pollingEnabled?: boolean;
  pollingIntervalMs?: number;
}

export function PriceAlertBell({
  onSelectSymbol,
  pollingEnabled = false,
  pollingIntervalMs = 60_000,
}: PriceAlertBellProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<PriceAlertNotification[]>([]);
  const [settings, setSettings] = useState<PriceAlertSettings | null>(null);

  async function refresh() {
    try {
      const [notes, cfg] = await Promise.all([
        api.priceAlertNotifications(true),
        api.priceAlertSettings(),
      ]);
      setItems(notes);
      setSettings(cfg);
    } catch {
      setItems([]);
    }
  }

  useEffect(() => {
    // 挂载/轮询参数变化时发起加载：惯用加载模式
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
    if (!pollingEnabled) return;
    const id = window.setInterval(() => void refresh(), pollingIntervalMs);
    return () => window.clearInterval(id);
  }, [pollingEnabled, pollingIntervalMs]);

  const unread = items.length;

  async function markAllRead() {
    await api.markAllPriceAlertsRead();
    await refresh();
  }

  async function openItem(item: PriceAlertNotification) {
    await api.markPriceAlertRead(item.id);
    onSelectSymbol(item.symbol, item.name);
    setOpen(false);
    void refresh();
  }

  return (
    <div className="alert-bell-wrap">
      <button
        type="button"
        className={`icon-btn alert-bell-btn${unread ? " has-unread" : ""}`}
        onClick={() => setOpen((v) => !v)}
        title={t("alerts.title")}
        aria-label={t("alerts.title")}
      >
        <IconBell />
        {unread > 0 && <span className="alert-bell-badge">{unread}</span>}
      </button>
      {open && (
        <div className="alert-bell-panel">
          <div className="alert-bell-head">
            <strong>{t("alerts.title")}</strong>
            {settings && (
              <span className="muted">
                {t("alerts.threshold", { pct: String(settings.threshold_pct) })}
              </span>
            )}
            {unread > 0 && (
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => void markAllRead()}
              >
                {t("alerts.markAllRead")}
              </button>
            )}
          </div>
          {items.length === 0 && <p className="muted flat-empty">{t("alerts.empty")}</p>}
          <ul className="alert-bell-list">
            {items.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className="alert-bell-item"
                  onClick={() => void openItem(item)}
                >
                  <span className="alert-bell-item-title">
                    {item.name} · {item.symbol}
                  </span>
                  <span className="mono">
                    {item.change_pct > 0 ? "+" : ""}
                    {item.change_pct.toFixed(2)}%
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
