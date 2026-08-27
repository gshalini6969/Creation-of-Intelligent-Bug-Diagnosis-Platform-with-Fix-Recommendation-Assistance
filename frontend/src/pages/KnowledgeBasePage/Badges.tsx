function badgeClass(value: string): string {
  const level = value.toLowerCase();
  return ["low", "medium", "high", "critical"].includes(level) ? level : "default";
}

export function SeverityBadge({ value }: { value: string }) {
  if (!value) return null;
  return <span className={`kb-badge kb-badge--${badgeClass(value)}`}>{value}</span>;
}

export function StatusBadge({ value }: { value: string }) {
  if (!value) return null;
  const modifierMap: Record<string, string> = {
    Open: "status-open",
    "In Progress": "status-in-progress",
    Resolved: "status-resolved",
  };
  const modifier = modifierMap[value] || "default";
  return <span className={`kb-badge kb-badge--${modifier}`}>{value}</span>;
}
