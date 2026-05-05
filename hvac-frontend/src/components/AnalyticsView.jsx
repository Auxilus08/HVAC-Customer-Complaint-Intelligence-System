import { useMemo } from "react";
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { useStats, useHeatmap } from "../hooks/useAnalytics";
import { useClusters } from "../hooks/useClusters";
import { useAlerts } from "../hooks/useAlerts";
import {
  asArray,
  CLUSTER_COLORS,
  formatCurrencyINR,
  formatPercent,
} from "../utils/format";
import { exportSystemReport } from "../hooks/useExport";
import Spinner from "./ui/Spinner";

const SENT_COLORS = {
  CRITICAL: "#dc2626",
  HIGH: "#f59e0b",
  NORMAL: "#6b7280",
  POSITIVE: "#16a34a",
};

const regionBarColor = (avg) => {
  if (avg == null) return "#6366f1";
  if (avg < -0.6) return "#dc2626";
  if (avg < -0.4) return "#f59e0b";
  return "#6366f1";
};

function MetricCard({ value, label, valueClass = "text-slate-100", pulse = false }) {
  return (
    <div className="bg-surface-card rounded-xl p-4 border border-surface-border">
      <div className={`text-2xl font-bold ${valueClass} ${pulse ? "animate-pulse-slow" : ""}`}>
        {value}
      </div>
      <div className="text-xs text-slate-400 mt-1">{label}</div>
    </div>
  );
}

const RegionTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-surface-card border border-surface-border rounded-lg p-3 text-sm">
      <p className="font-semibold text-slate-100 mb-1">{d.region}</p>
      <p className="text-slate-300">{d.total_complaints} complaints</p>
      {d.emerging_count > 0 && (
        <p className="text-accent">🚨 {d.emerging_count} emerging</p>
      )}
      <p className="text-slate-400 text-xs mt-1">
        {formatCurrencyINR(d.cost_exposure)} exposure · {formatPercent(d.complaint_change_pct)} WoW
      </p>
    </div>
  );
};

const PieTooltip = ({ active, payload, total }) => {
  if (!active || !payload?.length) return null;
  const p = payload[0];
  const pct = total ? ((p.value / total) * 100).toFixed(1) : "0";
  return (
    <div className="bg-surface-card border border-surface-border rounded-lg p-3 text-sm">
      <p className="font-semibold" style={{ color: p.payload.fill }}>
        {p.name}
      </p>
      <p className="text-slate-300">
        {p.value} complaints · {pct}%
      </p>
    </div>
  );
};

export default function AnalyticsView() {
  const stats = useStats();
  const heatmap = useHeatmap();
  const clusters = useClusters();
  const alerts = useAlerts();

  const sentData = useMemo(() => {
    const dist = stats.data?.sentiment_distribution || {};
    return Object.entries(dist).map(([name, value]) => ({
      name,
      value,
      fill: SENT_COLORS[name] || "#6b7280",
    }));
  }, [stats.data]);

  const sentTotal = useMemo(
    () => sentData.reduce((s, r) => s + r.value, 0),
    [sentData]
  );

  const sourceData = useMemo(() => {
    const dist = stats.data?.source_distribution || {};
    return Object.entries(dist)
      .sort((a, b) => b[1] - a[1])
      .map(([name, value], i) => ({
        name,
        value,
        fill: CLUSTER_COLORS[i % CLUSTER_COLORS.length],
      }));
  }, [stats.data]);

  const regionData = useMemo(() => {
    const arr = heatmap.data?.regions || [];
    return arr.slice().sort((a, b) => b.total_complaints - a.total_complaints);
  }, [heatmap.data]);

  const handleExportReport = () => {
    exportSystemReport({
      stats: stats.data,
      clusters: asArray(clusters.data),
      alerts: asArray(alerts.data),
    });
  };

  if (stats.isLoading) {
    return (
      <div className="card flex items-center justify-center min-h-[60vh]">
        <Spinner size="lg" />
      </div>
    );
  }

  const s = stats.data || {};
  const sil = s.last_silhouette_score;
  const silColor =
    sil == null ? "text-slate-100" : sil > 0.5 ? "text-positive" : sil > 0.3 ? "text-high" : "text-critical";
  const emergingColor = (s.emerging_clusters ?? 0) > 0 ? "text-critical" : "text-positive";

  return (
    <div className="space-y-4 animate-fade-in" data-demo-anchor="analytics">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Analytics</h2>
          <p className="text-slate-400 text-xs mt-0.5">Operational view across regions, SKUs and channels</p>
        </div>
        <button onClick={handleExportReport} className="btn-ghost text-sm" title="Download Markdown report">
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          Export Report
        </button>
      </div>

      <section className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <MetricCard value={s.total_complaints ?? "—"} label="Total Complaints" />
        <MetricCard value={s.total_clusters ?? "—"} label="Clusters Found" />
        <MetricCard
          value={`${s.emerging_clusters ?? 0}`}
          label="🚨 Emerging Clusters"
          valueClass={emergingColor}
          pulse={(s.emerging_clusters ?? 0) > 0}
        />
        <MetricCard
          value={sil != null ? sil.toFixed(3) : "—"}
          label="Silhouette Score"
          valueClass={silColor}
        />
        <MetricCard
          value={formatCurrencyINR(s.total_cost_exposure ?? 0)}
          label="Total Exposure"
        />
        <MetricCard
          value={
            s.total_complaints
              ? `${((s.noise_complaints / s.total_complaints) * 100).toFixed(1)}%`
              : "—"
          }
          label="Noise Rate"
        />
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div className="card">
          <h3 className="text-sm font-semibold text-white mb-2 tracking-wide uppercase">
            Complaint Sentiment Distribution
          </h3>
          {sentData.length === 0 ? (
            <p className="text-slate-500 text-sm">No sentiment data yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={sentData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={50}
                  outerRadius={90}
                  paddingAngle={2}
                  stroke="#0f172a"
                >
                  {sentData.map((d, i) => (
                    <Cell key={i} fill={d.fill} />
                  ))}
                </Pie>
                <Tooltip content={<PieTooltip total={sentTotal} />} />
                <Legend
                  iconType="circle"
                  formatter={(value) => (
                    <span style={{ color: "#94a3b8", fontSize: 12 }}>{value}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card">
          <h3 className="text-sm font-semibold text-white mb-2 tracking-wide uppercase">
            Complaints by Source Channel
          </h3>
          {sourceData.length === 0 ? (
            <p className="text-slate-500 text-sm">No source data yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={sourceData} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis
                  dataKey="name"
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                  axisLine={{ stroke: "#334155" }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                  axisLine={{ stroke: "#334155" }}
                  tickLine={false}
                  width={28}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1e293b",
                    border: "1px solid #334155",
                    borderRadius: "8px",
                  }}
                  cursor={{ fill: "#2d3f5520" }}
                />
                <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                  {sourceData.map((d, i) => (
                    <Cell key={i} fill={d.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </section>

      <section className="card">
        <h3 className="text-sm font-semibold text-white mb-2 tracking-wide uppercase">
          Complaints by Region
        </h3>
        {heatmap.isLoading ? (
          <div className="h-64 flex items-center justify-center"><Spinner /></div>
        ) : regionData.length === 0 ? (
          <p className="text-slate-500 text-sm">No region data yet.</p>
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(240, regionData.length * 32)}>
            <BarChart
              data={regionData}
              layout="vertical"
              margin={{ top: 4, right: 16, left: 4, bottom: 4 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                axisLine={{ stroke: "#334155" }}
              />
              <YAxis
                type="category"
                dataKey="region"
                width={90}
                tick={{ fill: "#cbd5e1", fontSize: 12 }}
                axisLine={{ stroke: "#334155" }}
                tickLine={false}
              />
              <Tooltip content={<RegionTooltip />} cursor={{ fill: "#2d3f5520" }} />
              <Bar dataKey="total_complaints" radius={[0, 6, 6, 0]}>
                {regionData.map((d, i) => (
                  <Cell key={i} fill={regionBarColor(d.avg_sentiment)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </section>
    </div>
  );
}
