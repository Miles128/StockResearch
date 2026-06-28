import type { ReactNode } from "react";
import { formatPrice, formatSignedPct, signedClass } from "../holdingDisplay";

interface DataValueProps {
  label: string;
  value: ReactNode;
  className?: string;
  mono?: boolean;
}

/** Unified label + value row for cards and tickers. */
export function DataValue({ label, value, className = "", mono = false }: DataValueProps) {
  return (
    <div className={`ui-data-value${className ? ` ${className}` : ""}`}>
      <span className="ui-data-label">{label}</span>
      <span className={`ui-data-amount${mono ? " mono" : ""}`}>{value}</span>
    </div>
  );
}

interface QuoteValuesProps {
  price: number;
  changePct: number;
  priceClassName?: string;
  inline?: boolean;
}

export function QuoteValues({
  price,
  changePct,
  priceClassName = "ui-quote-price",
  inline = false,
}: QuoteValuesProps) {
  return (
    <div className={`ui-quote-stack${inline ? " ui-quote-stack-inline" : ""}`}>
      <span className={`${priceClassName} mono`}>{formatPrice(price)}</span>
      <span className={`ui-quote-change mono ${signedClass(changePct)}`}>{formatSignedPct(changePct)}</span>
    </div>
  );
}
