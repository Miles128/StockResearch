export type CenterTab = "focus" | "market" | "risk" | "news";

export type ListsLayoutMode = "sidebar" | "hidden" | "center";

export type FocusContext =
  | {
      kind: "stock";
      symbol: string;
      name: string;
      price?: number | null;
      change_pct?: number | null;
    }
  | {
      kind: "index";
      symbol: string;
      name: string;
    }
  | { kind: "sector"; name: string };
