import { useAlerts } from "../api/alerts.js";

const SEVERITY_STYLES = {
  CRITICAL: "bg-red-900 border-red-700 text-red-100",
  HIGH: "bg-orange-900 border-orange-700 text-orange-100",
  MEDIUM: "bg-yellow-900 border-yellow-700 text-yellow-100",
  LOW: "bg-blue-900 border-blue-700 text-blue-100",
};

export default function AlertBanner() {
  const { data } = useAlerts({ limit: 3 });
  const alerts = data?.alerts ?? [];

  if (alerts.length === 0) return null;

  return (
    <div className="space-y-1 px-4 pt-3">
      {alerts.map((alert) => (
        <div
          key={alert.alert_id}
          className={`flex items-center gap-3 px-3 py-2 rounded-lg border text-sm ${
            SEVERITY_STYLES[alert.severity] ?? SEVERITY_STYLES.MEDIUM
          }`}
        >
          <span className="font-semibold uppercase text-xs tracking-wider opacity-75">
            {alert.severity}
          </span>
          <span className="flex-1 truncate">{alert.message}</span>
          <span className="text-xs opacity-60 shrink-0">
            {alert.complaint_count} complaints
          </span>
        </div>
      ))}
    </div>
  );
}
