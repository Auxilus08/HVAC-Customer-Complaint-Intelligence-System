import { useAlerts } from "../hooks/useAlerts";
import { asArray, formatPercent } from "../utils/format";

const severityClasses = (severity) => {
  const s = (severity || "").toLowerCase();
  if (s === "critical") return "bg-status-critical/8 border-l-4 border-status-critical hover:bg-status-critical/12";
  if (s === "warning" || s === "high") return "bg-status-high/8 border-l-4 border-status-high hover:bg-status-high/12";
  return "bg-carrier-light border-l-4 border-carrier hover:bg-carrier-light/80";
};

const severityLabel = (severity) => {
  const s = (severity || "").toUpperCase();
  if (s === "WARNING" || s === "HIGH") return "WARNING";
  return "CRITICAL";
};

const severityBadge = (severity) =>
  severityLabel(severity) === "CRITICAL" ? "badge-critical" : "badge-high";

export default function AlertBanner({ onClusterSelect }) {
  const { data, isLoading } = useAlerts();
  const alerts = asArray(data);
  if (isLoading || alerts.length === 0) return null;

  const visible = alerts.slice(0, 5);
  const overflow = alerts.length - visible.length;

  return (
    <div
      className="bg-surface-card border-b border-surface-border px-6 py-3 animate-fade-in flex-shrink-0"
      data-demo-anchor="alert-banner"
    >
      <div className="flex items-center gap-3 overflow-x-auto">
        <div className="text-[11px] uppercase tracking-wider text-ink-500 font-semibold shrink-0">
          Active Alerts
        </div>
        {visible.map((a) => {
          const id = a.cluster_id ?? a.id;
          const label = a.label || a.cluster_label || "Unlabeled cluster";
          const region = a.region || (Array.isArray(a.regions) ? a.regions[0] : null);
          const wow = a.growth_pct_wow ?? a.wow_growth_pct ?? a.growth_pct ?? a.wow ?? null;
          const count = a.complaint_count ?? a.member_count ?? a.count ?? 0;
          return (
            <button
              key={`${id}-${label}`}
              type="button"
              onClick={() => id != null && onClusterSelect?.(id)}
              className={`shrink-0 min-w-[260px] max-w-[340px] rounded-lg px-3 py-2 text-left transition-colors cursor-pointer ${severityClasses(a.severity)}`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="text-sm font-semibold text-ink-900 truncate">
                    {label}
                    {region ? <span className="text-ink-500 font-normal"> — {region}</span> : null}
                  </span>
                </div>
                {wow != null && (
                  <span className="text-xs font-mono text-carrier font-semibold shrink-0">
                    {formatPercent(wow)} WoW
                  </span>
                )}
              </div>
              <div className="flex items-center justify-between mt-1 text-xs text-ink-500">
                <span>{count} complaints</span>
                <span className={severityBadge(a.severity)}>
                  {severityLabel(a.severity)}
                </span>
              </div>
            </button>
          );
        })}
        {overflow > 0 && (
          <span className="chip text-xs shrink-0">+ {overflow} more</span>
        )}
      </div>
    </div>
  );
}
