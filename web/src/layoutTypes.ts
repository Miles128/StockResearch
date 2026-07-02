export interface SelectedMarketIndex {
  symbol: string;
  name: string;
}

export type CenterTab = "focus" | "risk" | "news";

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

export interface SelectedStock {
  symbol: string;
  name: string;
  price?: number | null;
  change_pct?: number | null;
  quantity?: number;
  profit_amount?: number | null;
}
