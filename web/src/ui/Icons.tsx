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

export function IconMessages({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M2.5 3.5h11a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H6l-3.5 2.5V4.5a1 1 0 0 1 1-1Z"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconPlus({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M8 3.5v9M3.5 8h9" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  );
}

export function IconEdit({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M10.5 2.5l3 3L6 13H3v-3L10.5 2.5Z"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconClose({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M4.5 4.5l7 7M11.5 4.5l-7 7" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  );
}

export function IconSettings({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.25" />
      <path
        d="M8 1.5v1.2M8 13.3v1.2M1.5 8h1.2M13.3 8h1.2M3.4 3.4l.85.85M11.75 11.75l.85.85M3.4 12.6l.85-.85M11.75 4.25l.85-.85"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconGlobe({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.25" />
      <path d="M2.5 8h11M8 2.5c1.8 1.6 2.8 3.7 2.8 5.5S9.8 11.9 8 13.5M8 2.5C6.2 4.1 5.2 6.2 5.2 8s1 3.9 2.8 5.5" stroke="currentColor" strokeWidth="1.25" />
    </svg>
  );
}

export function IconLayoutSidebar({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="2" y="2.5" width="12" height="11" rx="1.25" stroke="currentColor" strokeWidth="1.25" />
      <path d="M6 2.5v11" stroke="currentColor" strokeWidth="1.25" />
    </svg>
  );
}

export function IconLayoutTop({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="2" y="2.5" width="12" height="11" rx="1.25" stroke="currentColor" strokeWidth="1.25" />
      <path d="M2 6.5h12" stroke="currentColor" strokeWidth="1.25" />
    </svg>
  );
}

export function IconSignal({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="2.5" fill="currentColor" />
    </svg>
  );
}

export function IconUser({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="5.5" r="2.5" stroke="currentColor" strokeWidth="1.25" />
      <path d="M3.5 13c.8-2 2.4-3 4.5-3s3.7 1 4.5 3" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  );
}

export function IconLab({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M6 2.5h4l3 6.5a3 3 0 0 1-2.6 4.5H5.6A3 3 0 0 1 3 9l3-6.5Z" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round" />
      <path d="M6.5 6h3" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  );
}

export function IconBell({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M8 2.5a3.5 3.5 0 0 0-3.5 3.5v2.5L3 10v1h10v-1l-1.5-1.5V6A3.5 3.5 0 0 0 8 2.5Z" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round" />
      <path d="M6.5 13a1.5 1.5 0 0 0 3 0" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  );
}

export function IconRefresh({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M13 3.5v3h-3M3 12.5v-3h3"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M4.2 6.5A4.5 4.5 0 0 1 12 5.5M11.8 9.5A4.5 4.5 0 0 1 4 10.5"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconExternalLink({ className = "ui-icon", size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M6.5 3.5H12v5.5M12 3.5 6.5 9" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 5.5v7h7" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function SignalIcon({ type, severity }: { type: string; severity: string }) {
  if (type === "risk" && severity === "critical") return <IconAlert />;
  if (type === "risk" && severity === "warning") return <IconBolt />;
  if (type === "news") return <IconNews />;
  if (type === "price") return <IconChart />;
  if (type === "market") return <IconGlobe />;
  return <IconList />;
}
