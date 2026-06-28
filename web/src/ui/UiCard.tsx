import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

type UiCardBaseProps = {
  title?: ReactNode;
  meta?: ReactNode;
  children?: ReactNode;
  active?: boolean;
  className?: string;
};

type UiCardDivProps = UiCardBaseProps &
  HTMLAttributes<HTMLDivElement> & {
    as?: "div";
  };

type UiCardButtonProps = UiCardBaseProps &
  ButtonHTMLAttributes<HTMLButtonElement> & {
    as: "button";
  };

export type UiCardProps = UiCardDivProps | UiCardButtonProps;

/** Shared surface for market tiles, portfolio blocks, and data panels. */
export function UiCard(props: UiCardProps) {
  const { title, meta, children, active, className = "", as = "div", ...rest } = props;
  const classes = `ui-card${active ? " ui-card-active" : ""}${className ? ` ${className}` : ""}`;

  const body = (
    <>
      {(title || meta) && (
        <div className="ui-card-head">
          {title ? <span className="ui-card-title">{title}</span> : null}
          {meta ? <span className="ui-card-meta">{meta}</span> : null}
        </div>
      )}
      {children ? <div className="ui-card-body">{children}</div> : null}
    </>
  );

  if (as === "button") {
    const { type = "button", ...buttonRest } = rest as ButtonHTMLAttributes<HTMLButtonElement>;
    return (
      <button type={type} className={classes} {...buttonRest}>
        {body}
      </button>
    );
  }

  return (
    <div className={classes} {...(rest as HTMLAttributes<HTMLDivElement>)}>
      {body}
    </div>
  );
}
