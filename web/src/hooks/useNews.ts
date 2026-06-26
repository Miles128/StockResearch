import { useCallback, useEffect, useState } from "react";
import { api, type NewsItem, type SectorPreferences } from "../api";

export interface NewsState {
  news: NewsItem[];
  newsLoading: boolean;
  newsSectors: SectorPreferences | null;
  sectorSaving: boolean;
  loadNews: () => Promise<void>;
  toggleNewsSector: (sector: string) => Promise<void>;
}

export function useNews(active: boolean, onError?: (msg: string) => void): NewsState {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [newsSectors, setNewsSectors] = useState<SectorPreferences | null>(null);
  const [sectorSaving, setSectorSaving] = useState(false);

  const loadNews = useCallback(async () => {
    try {
      setNewsLoading(true);
      await api.ingestNews();
      setNews(await api.newsFeed());
    } catch (e) {
      onError?.(String(e));
    } finally {
      setNewsLoading(false);
    }
  }, [onError]);

  const toggleNewsSector = useCallback(
    async (sector: string) => {
      if (!newsSectors || sectorSaving) return;
      const selected = newsSectors.selected.includes(sector)
        ? newsSectors.selected.filter((s) => s !== sector)
        : [...newsSectors.selected, sector];
      try {
        setSectorSaving(true);
        const updated = await api.updateNewsSectors(selected);
        setNewsSectors(updated);
        await api.ingestNews();
        setNews(await api.newsFeed());
      } catch (e) {
        onError?.(String(e));
      } finally {
        setSectorSaving(false);
      }
    },
    [newsSectors, sectorSaving, onError],
  );

  useEffect(() => {
    if (!active) return;
    void api.newsSectors().then(setNewsSectors).catch(() => setNewsSectors(null));
    if (news.length === 0) void loadNews();
  }, [active, loadNews, news.length]);

  return {
    news,
    newsLoading,
    newsSectors,
    sectorSaving,
    loadNews,
    toggleNewsSector,
  };
}
