export const CLUSTER_COLORS = [
  "#6366f1",
  "#e85d04",
  "#10b981",
  "#f59e0b",
  "#3b82f6",
  "#ec4899",
  "#14b8a6",
  "#a855f7",
  "#84cc16",
  "#f97316",
];

export const clusterColor = (id) => {
  if (id === null || id === undefined || id === -1) return "#334155";
  return CLUSTER_COLORS[((id % CLUSTER_COLORS.length) + CLUSTER_COLORS.length) % CLUSTER_COLORS.length];
};

export const sentimentBadge = (avg) => {
  if (avg === null || avg === undefined) return "badge-normal";
  if (avg < -0.8) return "badge-critical";
  if (avg < -0.5) return "badge-high";
  if (avg >= 0.2) return "badge-positive";
  return "badge-normal";
};

export const sentimentLabel = (avg) => {
  if (avg === null || avg === undefined) return "—";
  if (avg < -0.8) return "CRITICAL";
  if (avg < -0.5) return "HIGH";
  if (avg >= 0.2) return "POSITIVE";
  return "NORMAL";
};

export const formatRelativeTime = (date) => {
  if (!date) return "never";
  const d = date instanceof Date ? date : new Date(date);
  const seconds = Math.floor((Date.now() - d.getTime()) / 1000);
  if (seconds < 10) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
};

export const formatCurrencyINR = (value) => {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const n = Number(value);
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
};

export const formatPercent = (value, withSign = true) => {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const n = Number(value);
  const sign = withSign && n > 0 ? "+" : "";
  return `${sign}${n.toFixed(0)}%`;
};

export const truncate = (text, n = 100) => {
  if (!text) return "";
  return text.length > n ? `${text.slice(0, n - 1)}…` : text;
};

export const growthColorClass = (pct) => {
  if (pct === null || pct === undefined || Number.isNaN(pct)) return "text-ink-900";
  if (pct < 0) return "text-positive";
  if (pct > 100) return "text-critical";
  if (pct > 30) return "text-high";
  return "text-ink-900";
};

export const formatNumber = (n) => {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("en-US").format(Number(n));
};

export const formatCompact = (n) => {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const num = Number(n);
  if (num >= 1_000_000_000) return `$${(num / 1_000_000_000).toFixed(1)}B`;
  if (num >= 1_000_000) return `$${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `$${(num / 1_000).toFixed(1)}K`;
  return `$${num.toFixed(0)}`;
};

export const asArray = (v) => {
  if (Array.isArray(v)) return v;
  if (v && Array.isArray(v.items)) return v.items;
  if (v && Array.isArray(v.results)) return v.results;
  if (v && Array.isArray(v.data)) return v.data;
  if (v && Array.isArray(v.points)) return v.points;
  if (v && Array.isArray(v.alerts)) return v.alerts;
  if (v && Array.isArray(v.clusters)) return v.clusters;
  return [];
};
