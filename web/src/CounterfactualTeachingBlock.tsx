import { useEffect, useMemo, useState } from "react";
import { api, type CounterfactualTeaching, type HoldingEnriched } from "./api";
import { CollapsibleSection } from "./CollapsibleSection";
import { useI18n } from "./i18n";
import { MarkdownContent } from "./MarkdownContent";

const MAX_SYMBOLS = 4;

/**
 * Phase 13b Counterfactual 教学块：用用户真实持仓金额绑定历史价格情景，
 * 零点击演示回撤/波动/估值三个概念（教机制，不给结论）。
 */
export function CounterfactualTeachingBlock({
  holdings,
  trigger,
}: {
  holdings: HoldingEnriched[];
  trigger: string;
}) {
  const { t } = useI18n();
  const [items, setItems] = useState<CounterfactualTeaching[] | null>(null);
  const [failed, setFailed] = useState(false);

  const symbols = useMemo(() => {
    const withValue = holdings
      .map((h) => ({ h, value: h.cost_price * h.quantity }))
      .sort((a, b) => b.value - a.value)
      .map((x) => x.h.symbol);
    return [...new Set(withValue)].slice(0, MAX_SYMBOLS);
  }, [holdings, trigger]);

  useEffect(() => {
    if (symbols.length === 0) {
      setItems([]);
      setFailed(false);
      return;
    }
    let alive = true;
    setItems(null);
    setFailed(false);
    api
      .portfolioCounterfactual(symbols)
      .then((res) => {
        if (alive) setItems(res.items);
      })
      .catch(() => {
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
    };
  }, [symbols.join(",")]);

  if (holdings.length === 0) return null;

  return (
    <CollapsibleSection
      title={t("portfolio.counterfactualTitle")}
      summary={items ? t("portfolio.counterfactualSummary") : t("portfolio.loading")}
      defaultCollapsed
    >
      {failed ? (
        <p className="muted flat-empty">{t("portfolio.counterfactualError")}</p>
      ) : items === null ? (
        <p className="muted flat-empty">{t("portfolio.loading")}</p>
      ) : items.length === 0 ? (
        <p className="muted flat-empty">{t("portfolio.counterfactualEmpty")}</p>
      ) : (
        items.map((item) => (
          <div key={item.symbol} className="counterfactual-item">
            <div className="counterfactual-head">
              <span className="counterfactual-symbol mono">{item.symbol}</span>
              <span className="counterfactual-name">{item.name}</span>
              {item.position_value != null && (
                <span className="counterfactual-amount">
                  {t("portfolio.counterfactualPosition")} ·{" "}
                  {t("portfolio.counterfactualWan", {
                    amount: (item.position_value / 10000).toFixed(1),
                  })}
                </span>
              )}
            </div>
            {item.segments.map((seg) => (
              <details key={seg.concept} className="counterfactual-segment">
                <summary>
                  <span className="counterfactual-concept">{seg.title}</span>
                  {seg.partial && (
                    <span className="counterfactual-partial">{t("portfolio.partial")}</span>
                  )}
                </summary>
                <div className="counterfactual-story">
                  <MarkdownContent text={seg.story} />
                  {seg.note && <p className="muted counterfactual-note">{seg.note}</p>}
                </div>
              </details>
            ))}
            <p className="muted counterfactual-disclaimer">{item.disclaimer}</p>
          </div>
        ))
      )}
    </CollapsibleSection>
  );
}
