import { useCallback, useEffect, useState } from "react";
import { api, type StockLookupOut } from "../api";
import { useI18n } from "../i18n";

export interface StockLookupState {
  holdingInput: string;
  holdingCost: string;
  holdingLots: string;
  holdingDate: string;
  lookupResult: StockLookupOut | null;
  lookupPrice: number | null;
  lookupLoading: boolean;
  setHoldingInput: (value: string) => void;
  setHoldingCost: (value: string) => void;
  setHoldingLots: (value: string) => void;
  setHoldingDate: (value: string) => void;
  setLookupResult: (value: StockLookupOut | null) => void;
  lookupAndAdd: (onSuccess?: () => void | Promise<void>) => Promise<void>;
  confirmCandidate: (symbol: string, name: string, onSuccess?: () => void | Promise<void>) => Promise<void>;
}

export function useStockLookup(onError?: (msg: string) => void): StockLookupState {
  const { t } = useI18n();
  const [holdingInput, setHoldingInput] = useState("");
  const [holdingCost, setHoldingCost] = useState("");
  const [holdingLots, setHoldingLots] = useState("");
  const [holdingDate, setHoldingDate] = useState("");
  const [lookupResult, setLookupResult] = useState<StockLookupOut | null>(null);
  const [lookupPrice, setLookupPrice] = useState<number | null>(null);
  const [lookupLoading, setLookupLoading] = useState(false);

  useEffect(() => {
    if (lookupResult?.status !== "confirmed" || !lookupResult.symbol) {
      setLookupPrice(null);
      return;
    }
    void api
      .stockQuotes(lookupResult.symbol)
      .then((quotes) => setLookupPrice(quotes[0]?.price ?? null))
      .catch(() => setLookupPrice(null));
  }, [lookupResult]);

  const resetForm = useCallback(() => {
    setHoldingInput("");
    setHoldingCost("");
    setHoldingLots("");
    setHoldingDate("");
    setLookupResult(null);
  }, []);

  const addHolding = useCallback(
    async (symbol: string, name: string, onSuccess?: () => void | Promise<void>) => {
      const cost = holdingCost ? parseFloat(holdingCost) : 0;
      const lots = holdingLots ? parseInt(holdingLots) : 1;
      if (cost <= 0) {
        onError?.(t("portfolio.invalidCost"));
        return;
      }
      await api.addHolding({
        symbol,
        name,
        cost_price: cost,
        lots,
        buy_date: holdingDate || undefined,
      });
      await onSuccess?.();
      resetForm();
    },
    [holdingCost, holdingLots, holdingDate, resetForm, onError],
  );

  const lookupAndAdd = useCallback(
    async (onSuccess?: () => void | Promise<void>) => {
      if (!holdingInput.trim()) return;
      setLookupLoading(true);
      setLookupResult(null);
      try {
        const result = await api.lookupStock(holdingInput.trim());
        setLookupResult(result);
        if (result.status === "confirmed" && result.symbol && result.name) {
          await addHolding(result.symbol, result.name, onSuccess);
        }
      } catch (e) {
        onError?.(String(e));
      } finally {
        setLookupLoading(false);
      }
    },
    [holdingInput, addHolding, onError],
  );

  const confirmCandidate = useCallback(
    async (symbol: string, name: string, onSuccess?: () => void | Promise<void>) => {
      try {
        await addHolding(symbol, name, onSuccess);
      } catch (e) {
        onError?.(String(e));
      }
    },
    [addHolding, onError],
  );

  return {
    holdingInput,
    holdingCost,
    holdingLots,
    holdingDate,
    lookupResult,
    lookupPrice,
    lookupLoading,
    setHoldingInput,
    setHoldingCost,
    setHoldingLots,
    setHoldingDate,
    setLookupResult,
    lookupAndAdd,
    confirmCandidate,
  };
}
