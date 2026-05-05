import { useEffect, useRef, useState } from "react";
import { useHealth } from "../hooks/useHealth";
import { useClusters } from "../hooks/useClusters";
import { useStats } from "../hooks/useAnalytics";
import { formatRelativeTime } from "../utils/format";

function StatPill({ value, label, valueClass = "text-slate-100" }) {
  if (value === undefined || value === null) {
    return (
      <span className="bg-surface-hover rounded-full px-3 py-1 text-xs flex items-center gap-1.5 animate-pulse">
        <span className="w-6 h-3 bg-surface-border rounded" />
      </span>
    );
  }
  return (
    <span className="bg-surface-hover rounded-full px-3 py-1 text-xs flex items-center gap-1.5">
      <span className={`font-mono font-semibold ${valueClass}`}>{value}</span>
      <span className="text-slate-400">{label}</span>
    </span>
  );
}

export default function TopBar({
  onUploadClick,
  onDemoClick,
  onSearchClick,
  showDemoButton,
}) {
  const health = useHealth();
  const clusters = useClusters();
  const stats = useStats();
  const [, setTick] = useState(0);
  const lastSuccessRef = useRef(null);

  useEffect(() => {
    if (clusters.isSuccess && clusters.dataUpdatedAt) {
      lastSuccessRef.current = new Date(clusters.dataUpdatedAt);
    }
  }, [clusters.isSuccess, clusters.dataUpdatedAt]);

  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 15_000);
    return () => clearInterval(id);
  }, []);

  const isHealthy = health.isSuccess && !health.isError;
  const dotColor = isHealthy ? "bg-positive" : "bg-critical";
  const statusText = isHealthy ? "Live" : "Disconnected";

  const s = stats.data || {};
  const emergingValue = stats.isLoading ? null : s.emerging_clusters ?? 0;

  return (
    <header
      className="h-14 bg-surface-card border-b border-surface-border px-6 flex items-center justify-between flex-shrink-0"
      data-demo-anchor="topbar"
    >
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-accent-dark flex items-center justify-center shadow-lg shadow-accent/20">
            <svg viewBox="0 0 24 24" className="w-5 h-5 text-white" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 12h3l3-9 6 18 3-9h3" />
            </svg>
          </div>
          <div className="leading-tight">
            <h1 className="font-bold text-white text-base tracking-tight">
              HVAC Intelligence
            </h1>
            <p className="text-slate-400 text-[11px]">
              Complaint Analysis System
            </p>
          </div>
        </div>

        <div className="hidden lg:flex items-center gap-1.5" data-demo-anchor="stats-pills">
          <StatPill
            value={stats.isLoading ? null : s.total_complaints ?? 0}
            label="complaints"
          />
          <StatPill
            value={stats.isLoading ? null : s.total_clusters ?? 0}
            label="clusters"
          />
          <StatPill
            value={emergingValue == null ? null : `${emergingValue} 🚨`}
            label="emerging"
            valueClass={emergingValue > 0 ? "text-critical" : "text-positive"}
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-xs">
          <span className="relative flex h-2 w-2">
            {isHealthy && (
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${dotColor} opacity-60`} />
            )}
            <span className={`relative inline-flex rounded-full h-2 w-2 ${dotColor}`} />
          </span>
          <span className={isHealthy ? "text-positive" : "text-critical"}>
            {statusText}
          </span>
        </div>

        <div className="text-xs text-slate-400 hidden md:block">
          Updated {formatRelativeTime(lastSuccessRef.current)}
        </div>

        <button
          onClick={onSearchClick}
          className="btn-ghost text-sm"
          title="Search complaints (press /)"
          aria-label="Search"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="7" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </button>

        {showDemoButton && (
          <button
            onClick={onDemoClick}
            className="btn-ghost text-sm"
            title="Run demo walkthrough (D)"
          >
            <span className="text-accent">▶</span> Demo Mode
          </button>
        )}

        <button
          onClick={onUploadClick}
          className="btn-primary text-sm"
          data-demo-anchor="upload-btn"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          Upload
        </button>
      </div>
    </header>
  );
}
