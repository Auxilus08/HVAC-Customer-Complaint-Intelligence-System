import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  useClusterDetail,
  useAdvisory,
  useClusterTrend,
} from "../hooks/useClusters";
import {
  asArray,
  clusterColor,
  formatCurrencyINR,
  formatPercent,
  formatRelativeTime,
  growthColorClass,
  sentimentBadge,
  sentimentLabel,
} from "../utils/format";
import Spinner from "./ui/Spinner";
import ErrorBanner from "./ui/ErrorBanner";
import { exportClusterCSV, exportAdvisoryText } from "../hooks/useExport";

const parseAdvisorySections = (text) => {
  if (!text) return [];
  const lines = text.split(/\r?\n/);
  const sections = [];
  let current = null;
  const headingRe = /^\s{0,3}(#{1,4}|\*\*)\s*(.+?)\s*(\*\*)?\s*$/;
  const bulletHeading = /^\s*[-•]\s*\*\*(.+?)\*\*\s*[:：]?\s*(.*)$/;

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      if (current) current.body += "\n";
      continue;
    }
    const bm = line.match(bulletHeading);
    if (bm) {
      if (current) sections.push(current);
      current = { title: bm[1].trim(), body: bm[2] ? `${bm[2]}\n` : "" };
      continue;
    }
    const m = line.match(headingRe);
    if (m && (m[1].startsWith("#") || (m[1] === "**" && line.endsWith("**")))) {
      if (current) sections.push(current);
      current = { title: m[2].replace(/\*\*/g, "").trim(), body: "" };
      continue;
    }
    if (!current) current = { title: "Advisory", body: "" };
    current.body += `${line}\n`;
  }
  if (current) sections.push(current);
  return sections.filter((s) => s.body.trim() || s.title);
};

function MetricCard({ value, label, valueClass = "text-ink-900" }) {
  return (
    <div className="bg-surface-card rounded-xl p-4 border border-surface-border">
      <div className={`text-2xl font-bold ${valueClass}`}>{value}</div>
      <div className="text-xs text-ink-500 mt-1">{label}</div>
    </div>
  );
}

function AdvisorySection({ id, cluster }) {
  const queryClient = useQueryClient();
  const [enabled, setEnabled] = useState(false);
  const [copied, setCopied] = useState(false);
  const advisory = useAdvisory(id, enabled);

  useEffect(() => {
    setEnabled(false);
  }, [id]);

  const text =
    advisory.data?.advisory_text ||
    advisory.data?.text ||
    advisory.data?.advisory ||
    (typeof advisory.data === "string" ? advisory.data : "");
  const sections = useMemo(() => parseAdvisorySections(text), [text]);

  const handleCopy = async () => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  const handleRegenerate = () => {
    queryClient.removeQueries({ queryKey: ["advisory", id] });
    setEnabled(false);
    setTimeout(() => setEnabled(true), 50);
  };

  return (
    <section
      className="card mt-4"
      data-demo-anchor="advisory"
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold text-ink-900 tracking-tight">
          AI-Generated Service Advisory
        </h3>
        {advisory.isSuccess && (
          <div className="flex items-center gap-2">
            <button onClick={handleCopy} className="btn-ghost text-xs">
              {copied ? "Copied!" : "Copy Advisory"}
            </button>
            <button
              onClick={() => exportAdvisoryText(text, cluster || { id, label: "Cluster" })}
              className="btn-ghost text-xs"
              title="Download as text"
            >
              Download
            </button>
            <button onClick={handleRegenerate} className="btn-ghost text-xs">
              Regenerate
            </button>
          </div>
        )}
      </div>

      {!enabled && !advisory.isSuccess && (
        <div className="bg-surface/60 border border-surface-border rounded-lg p-5 text-center">
          <p className="text-ink-700 text-sm mb-3">
            Generate a Gemini-powered technician advisory for this complaint
            cluster.
          </p>
          <button
            onClick={() => setEnabled(true)}
            className="btn-primary"
            data-demo-anchor="generate-advisory"
          >
            Generate Advisory
          </button>
          <p className="text-xs text-high mt-3">
            ⚠ This may take up to 10 seconds
          </p>
        </div>
      )}

      {enabled && advisory.isLoading && (
        <div className="flex items-center gap-3 py-6 px-4 bg-surface/60 rounded-lg">
          <Spinner size="md" />
          <p className="text-ink-700 text-sm">
            Gemini is analyzing complaint patterns…
          </p>
        </div>
      )}

      {advisory.isError && (
        <ErrorBanner
          message={advisory.error?.message || "Failed to generate advisory"}
          onRetry={() => {
            queryClient.removeQueries({ queryKey: ["advisory", id] });
            setEnabled(false);
            setTimeout(() => setEnabled(true), 50);
          }}
        />
      )}

      {advisory.isSuccess && sections.length > 0 && (
        <div className="bg-surface/40 rounded-lg p-4 border border-surface-border animate-fade-in">
          {sections.map((s, i) => (
            <div key={i} className="mb-4 last:mb-0">
              <h4 className="text-accent font-semibold mb-1 text-sm">
                {s.title}
              </h4>
              <p className="text-ink-700 text-sm leading-relaxed whitespace-pre-line">
                {s.body.trim()}
              </p>
            </div>
          ))}
        </div>
      )}

      {advisory.isSuccess && sections.length === 0 && text && (
        <div className="bg-surface/40 rounded-lg p-4 border border-surface-border whitespace-pre-line text-ink-700 text-sm leading-relaxed">
          {text}
        </div>
      )}
    </section>
  );
}

function TrendChart({ id }) {
  const { data, isLoading, isError } = useClusterTrend(id, 30);
  const series = useMemo(() => {
    const arr = asArray(data);
    return arr
      .map((d) => ({
        date: d.date || d.day || d.timestamp,
        count: d.count ?? d.value ?? 0,
      }))
      .filter((d) => d.date);
  }, [data]);

  if (isLoading) {
    return (
      <div className="card h-44 flex items-center justify-center">
        <Spinner size="md" />
      </div>
    );
  }
  if (isError || series.length === 0) {
    return (
      <div className="card h-44 flex items-center justify-center text-ink-500 text-sm">
        No trend data available
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-ink-900 tracking-wide">
          Daily Volume — Last 30 days
        </h3>
        <span className="text-xs text-ink-500">{series.length} pts</span>
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={series} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#e85d04" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#e85d04" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="date"
            tick={{ fill: "#64748b", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#334155" }}
          />
          <YAxis
            tick={{ fill: "#64748b", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#334155" }}
            width={28}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "8px",
              color: "#f1f5f9",
            }}
            labelStyle={{ color: "#94a3b8" }}
          />
          <Area
            type="monotone"
            dataKey="count"
            stroke="#e85d04"
            strokeWidth={2}
            fill="url(#trendFill)"
            fillOpacity={1}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function ClusterDetail({ id, onBack }) {
  const { data: cluster, isLoading, isError, error, refetch } =
    useClusterDetail(id);

  if (isLoading) {
    return (
      <div className="card min-h-[40vh] flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isError || !cluster) {
    return (
      <div className="card">
        <button onClick={onBack} className="btn-ghost text-sm mb-3">
          ← Back to map
        </button>
        <ErrorBanner
          message={error?.message || "Cluster not found"}
          onRetry={refetch}
        />
      </div>
    );
  }

  const color = clusterColor(cluster.id ?? id);
  const memberCount = cluster.member_count ?? cluster.complaint_count ?? 0;
  const avg = cluster.avg_sentiment;
  const wow =
    cluster.growth_pct_wow ??
    cluster.wow_growth_pct ??
    cluster.growth_pct ??
    null;
  const exposureRaw =
    cluster.cost_exposure_estimate ??
    cluster.exposure_inr ??
    cluster.cost_exposure ??
    null;
  // cost_exposure_estimate is Numeric in DB → arrives as a string in JSON.
  const exposure = exposureRaw != null ? Number(exposureRaw) : null;
  const isEmerging = !!cluster.is_emerging;
  const skus = cluster.top_skus || cluster.skus || [];
  const regions = cluster.top_regions || cluster.regions || [];
  const recent =
    cluster.recent_complaints ||
    cluster.complaints ||
    cluster.samples ||
    [];

  return (
    <div className="space-y-4 animate-fade-in">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-3 min-w-0">
          <button
            onClick={onBack}
            className="btn-ghost text-sm shrink-0 mt-1"
            aria-label="Back to map"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            Back
          </button>
          <div className="flex items-center gap-3 min-w-0">
            <span
              className="w-4 h-4 rounded-full flex-shrink-0 ring-4 ring-offset-2 ring-offset-surface"
              style={{ backgroundColor: color, ringColor: color }}
            />
            <h2 className="text-2xl font-bold text-ink-900 tracking-tight truncate">
              {cluster.label || `Cluster #${cluster.id ?? id}`}
            </h2>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className={sentimentBadge(avg)}>{sentimentLabel(avg)}</span>
            {isEmerging && <span className="badge-emerging">EMERGING</span>}
          </div>
        </div>
        <button
          onClick={() => exportClusterCSV(cluster)}
          className="btn-ghost text-xs"
          title="Export complaints as CSV"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          Export CSV
        </button>
      </header>

      <section
        className="grid grid-cols-2 lg:grid-cols-4 gap-3"
        data-demo-anchor="metrics"
      >
        <MetricCard value={memberCount} label="Complaints" />
        <MetricCard
          value={avg != null ? Number(avg).toFixed(2) : "—"}
          label="Avg Sentiment"
          valueClass={avg != null && avg < -0.5 ? "text-critical" : "text-ink-900"}
        />
        <MetricCard
          value={wow != null ? formatPercent(wow) : "—"}
          label="WoW Growth"
          valueClass={growthColorClass(wow)}
        />
        <MetricCard
          value={exposure != null ? formatCurrencyINR(exposure) : "—"}
          label="Cost Exposure"
        />
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="card">
          <h3 className="text-xs uppercase tracking-wider text-ink-500 font-semibold mb-2">
            Top Products
          </h3>
          <div className="flex flex-wrap gap-2">
            {skus.length === 0 ? (
              <span className="text-ink-500 text-sm">—</span>
            ) : (
              skus.slice(0, 8).map((s, i) => {
                const label = typeof s === "string" ? s : s.sku ?? s.value;
                const count = typeof s === "object" ? s.count : null;
                return (
                  <span key={`${label}-${i}`} className="chip">
                    {label}
                    {count != null && (
                      <span className="text-ink-500 ml-1">· {count}</span>
                    )}
                  </span>
                );
              })
            )}
          </div>
        </div>
        <div className="card">
          <h3 className="text-xs uppercase tracking-wider text-ink-500 font-semibold mb-2">
            Top Regions
          </h3>
          <div className="flex flex-wrap gap-2">
            {regions.length === 0 ? (
              <span className="text-ink-500 text-sm">—</span>
            ) : (
              regions.slice(0, 8).map((r, i) => {
                const label = typeof r === "string" ? r : r.region ?? r.value;
                const count = typeof r === "object" ? r.count : null;
                return (
                  <span key={`${label}-${i}`} className="chip">
                    {label}
                    {count != null && (
                      <span className="text-ink-500 ml-1">· {count}</span>
                    )}
                  </span>
                );
              })
            )}
          </div>
        </div>
      </section>

      <TrendChart id={cluster.id ?? id} />

      <section className="card">
        <h3 className="text-base font-semibold text-ink-900 mb-3 tracking-tight">
          Recent Complaints ({recent.length || 0})
        </h3>
        {recent.length === 0 ? (
          <div className="text-ink-500 text-sm">No recent complaints.</div>
        ) : (
          <ul className="space-y-2">
            {recent.slice(0, 10).map((c, i) => {
              const sLabel = c.sentiment_label || c.sentiment || sentimentLabel(c.sentiment_score);
              const badgeClass =
                sLabel === "CRITICAL"
                  ? "badge-critical"
                  : sLabel === "HIGH"
                  ? "badge-high"
                  : sLabel === "POSITIVE"
                  ? "badge-positive"
                  : "badge-normal";
              const created = c.created_at || c.timestamp;
              const text = c.clean_text || c.text || c.complaint_text || "—";
              return (
                <li
                  key={c.id ?? c.complaint_id ?? i}
                  className="flex items-start gap-3 p-3 bg-surface/40 rounded-lg border border-surface-border/60 hover:border-accent/30 transition-colors"
                >
                  <span className={`${badgeClass} mt-0.5 shrink-0`}>{sLabel}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-ink-900 text-sm leading-snug">{text}</p>
                    <p className="text-xs text-ink-500 mt-1">
                      {[c.region, c.product_sku, formatRelativeTime(created)]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <AdvisorySection id={cluster.id ?? id} cluster={cluster} />
    </div>
  );
}
