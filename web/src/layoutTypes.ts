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
  | { kind: "sector"; name: string };

export interface SelectedStock {
  symbol: string;
  name: string;
  price?: number | null;
  change_pct?: number | null;
  quantity?: number;
  profit_amount?: number | null;
}
