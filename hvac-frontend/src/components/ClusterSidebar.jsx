import { useMemo, useState } from "react";
import { useClusters } from "../hooks/useClusters";
import {
  asArray,
  clusterColor,
  formatCurrencyINR,
  sentimentBadge,
  sentimentLabel,
} from "../utils/format";
import SkeletonCard from "./ui/SkeletonCard";
import ErrorBanner from "./ui/ErrorBanner";
import Sparkline from "./Sparkline";

export default function ClusterSidebar({ selectedId, onSelect }) {
  const [region, setRegion] = useState("");
  const [emergingOnly, setEmergingOnly] = useState(false);

  const filters = useMemo(() => {
    const f = { limit: 100 };
    if (region) f.region = region;
    if (emergingOnly) f.emerging_only = true;
    return f;
  }, [region, emergingOnly]);

  const { data, isLoading, isError, error, refetch, isFetching } =
    useClusters(filters);
  const allClusters = asArray(data);

  const regions = useMemo(() => {
    const set = new Set();
    allClusters.forEach((c) => {
      const arr = c.regions || (c.region ? [c.region] : []);
      arr.forEach((r) => r && set.add(r));
    });
    return Array.from(set).sort();
  }, [allClusters]);

  const sorted = useMemo(() => {
    return [...allClusters].sort((a, b) => {
      const pa = a.priority_score ?? a.priority ?? 0;
      const pb = b.priority_score ?? b.priority ?? 0;
      if (pb !== pa) return pb - pa;
      return (b.member_count ?? 0) - (a.member_count ?? 0);
    });
  }, [allClusters]);

  return (
    <aside
      className="w-[280px] flex-shrink-0 bg-surface-card/40 border-r border-surface-border flex flex-col overflow-hidden"
      data-demo-anchor="sidebar"
    >
      <div className="sticky top-0 z-10 bg-surface-card/95 backdrop-blur border-b border-surface-border">
        <div className="px-4 pt-4 pb-3">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white tracking-wide uppercase">
              Clusters
            </h2>
            <span className="text-xs px-2 py-0.5 rounded-full bg-surface-border text-slate-300 font-mono">
              {sorted.length} found
            </span>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="flex-1 bg-surface text-slate-200 text-xs border border-surface-border rounded-md px-2 py-1.5 focus:outline-none focus:border-accent"
            >
              <option value="">All regions</option>
              {regions.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
            <button
              onClick={() => setEmergingOnly((v) => !v)}
              className={`text-xs px-2.5 py-1.5 rounded-md font-medium transition-colors border ${
                emergingOnly
                  ? "bg-accent text-white border-accent"
                  : "bg-surface text-slate-300 border-surface-border hover:border-accent/50"
              }`}
              title="Show only emerging clusters"
            >
              🚨 Emerging
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3">
        {isLoading && (
          <div>
            {[...Array(5)].map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        )}

        {isError && (
          <ErrorBanner
            message={error?.message || "Failed to load clusters"}
            onRetry={refetch}
          />
        )}

        {!isLoading && !isError && sorted.length === 0 && (
          <div className="text-center text-slate-500 text-sm py-8">
            No clusters yet.
          </div>
        )}

        {!isLoading &&
          !isError &&
          sorted.map((c) => {
            const id = c.id ?? c.cluster_id;
            const color = clusterColor(id);
            const isSelected = id === selectedId;
            const trend =
              c.trend_7d ||
              c.sparkline ||
              c.daily_counts ||
              null;
            const trendValues = Array.isArray(trend)
              ? trend.map((t) => (typeof t === "number" ? t : t.count ?? 0))
              : null;
            const exposureRaw =
              c.cost_exposure_estimate ??
              c.exposure_inr ??
              c.cost_exposure ??
              c.exposure ??
              null;
            const exposure = exposureRaw != null ? Number(exposureRaw) : null;
            const memberCount = c.member_count ?? c.complaint_count ?? 0;
            const avg = c.avg_sentiment;
            const isEmerging = !!c.is_emerging;
            return (
              <button
                key={id}
                onClick={() => onSelect?.(id)}
                data-cluster-id={id}
                data-cluster-emerging={isEmerging ? "1" : "0"}
                data-priority-score={c.priority_score ?? 0}
                className={`w-full text-left mb-2 rounded-lg p-3 transition-colors ${
                  isSelected
                    ? "bg-surface-hover border-l-4 border-accent"
                    : "bg-surface-card hover:bg-surface-hover border-l-4 border-transparent"
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ backgroundColor: color }}
                    />
                    <span className="text-sm font-medium text-slate-100 truncate">
                      {c.label || `Cluster #${id}`}
                    </span>
                  </div>
                  {isEmerging && <span className="badge-emerging">EMERGING</span>}
                </div>
                <div className="flex items-center gap-2 text-[11px] text-slate-400 mb-2 ml-4">
                  <span>{memberCount} complaints</span>
                  {avg != null && (
                    <>
                      <span className="text-slate-600">·</span>
                      <span className="font-mono">avg {Number(avg).toFixed(2)}</span>
                    </>
                  )}
                </div>
                <div className="ml-4 mb-1.5">
                  <Sparkline
                    values={trendValues}
                    color={isEmerging ? "#dc2626" : "#64748b"}
                    width={140}
                    height={20}
                  />
                </div>
                <div className="flex items-center justify-between ml-4">
                  {exposure != null ? (
                    <span className="text-[11px] text-slate-300 font-mono">
                      {formatCurrencyINR(exposure)} exposure
                    </span>
                  ) : (
                    <span />
                  )}
                  <span className={sentimentBadge(avg)}>
                    {sentimentLabel(avg)}
                  </span>
                </div>
              </button>
            );
          })}
      </div>

      <div className="border-t border-surface-border px-4 py-2 flex items-center justify-between text-[11px] text-slate-500 flex-shrink-0">
        <span>Refreshes every 60s</span>
        <button
          onClick={refetch}
          disabled={isFetching}
          className="text-slate-400 hover:text-accent disabled:opacity-50 transition-colors"
          title="Refresh now"
          aria-label="Refresh"
        >
          <svg
            className={`w-4 h-4 ${isFetching ? "animate-spin" : ""}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="23 4 23 10 17 10" />
            <polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
        </button>
      </div>
    </aside>
  );
}
