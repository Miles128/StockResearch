import { useEffect, useState } from "react";

export function useClock(locale: "zh" | "en"): string {
  const [clock, setClock] = useState("");

  useEffect(() => {
    const localeTag = locale === "zh" ? "zh-CN" : "en-US";
    const tick = () => {
      const now = new Date();
      const dateStr = now.toLocaleDateString(localeTag, {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      });
      const timeStr = now.toLocaleTimeString(localeTag, { hour12: false });
      setClock(`${dateStr} ${timeStr}`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [locale]);

  return clock;
}
