interface IconProps {
  className?: string;
  size?: number;
}

export function IconAlert({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M8 1.5 14.5 13H1.5L8 1.5Z"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinejoin="round"
      />
      <path d="M8 6v3.5M8 11.5v.5" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  );
}

export function IconBolt({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M9 1 4 9h3.5L7 15l6-8H9.5L9 1Z"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconNews({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="2" y="2.5" width="12" height="11" rx="1.25" stroke="currentColor" strokeWidth="1.25" />
      <path d="M4.5 5.5h4M4.5 8h7M4.5 10.5h5.5" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  );
}

export function IconChart({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M2.5 13.5V4.5M6 13.5V8M9.5 13.5V6M13 13.5V2.5" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  );
}

export function IconList({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M3 4.5h10M3 8h10M3 11.5h10" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  );
}

export function IconPanelBottom({ className = "ui-icon", size = 14 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="2" y="2.5" width="12" height="11" rx="1.25" stroke="currentColor" strokeWidth="1.25" />
      <path d="M2 10.5h12" stroke="currentColor" strokeWidth="1.25" />
    </svg>
  );
}

export function IconPanelSide({ className = "ui-icon", size = 14 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="2" y="2.5" width="12" height="11" rx="1.25" stroke="currentColor" strokeWidth="1.25" />
      <path d="M10 2.5v11" stroke="currentColor" strokeWidth="1.25" />
    </svg>
  );
}

export function SignalIcon({ type, severity }: { type: string; severity: string }) {
  if (type === "risk" && severity === "critical") return <IconAlert />;
  if (type === "risk" && severity === "warning") return <IconBolt />;
  if (type === "news") return <IconNews />;
  if (type === "price") return <IconChart />;
  return <IconList />;
}
