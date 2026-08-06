import { useState } from "react";
import { api } from "../api";
import { useI18n } from "../i18n";

/** 设置页「数据备份」块：一键下载全量用户数据 JSON（换机/迁移用）。 */
export function BackupBlock() {
  const { t } = useI18n();
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setDownloading(true);
    setError(null);
    try {
      const data = await api.exportUserData();
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `stockresearch-backup-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError(t("settings.backupFailed"));
    } finally {
      setDownloading(false);
    }
  }

  return (
    <section className="settings-section">
      <h4 className="settings-section-title">{t("settings.backupTitle")}</h4>
      <p className="settings-hint">{t("settings.backupHint")}</p>
      <button
        type="button"
        className="settings-ghost-btn"
        disabled={downloading}
        onClick={() => void download()}
      >
        {downloading ? "…" : t("settings.backupDownload")}
      </button>
      {error && <p className="error settings-analysis-note">{error}</p>}
    </section>
  );
}
