import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { useStats, useBuildings } from "../hooks/useAnalytics";
import { useClusters } from "../hooks/useClusters";
import { asArray, formatCompact, formatNumber } from "../utils/format";
import { sourceLabel } from "../utils/sourceLabels";
import KpiTile from "./KpiTile";
import ThemeListItem from "./ThemeListItem";

const SENT_COLORS = {
  CRITICAL: "#DC2626",
  HIGH: "#F59E0B",
  NORMAL: "#94A3B8",
  POSITIVE: "#16A34A",
};

const BUILDING_COLORS = [
  "#1E3A5F",
  "#3D5A80",
  "#64748B",
  "#94A3B8",
  "#CBD5E1",
  "#E2E8F0",
];

function SectionHeading({ title, action }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-base font-semibold text-ink-900">{title}</h2>
      {action}
    </div>
  );
}

function Skeleton({ className = "" }) {
  return <div className={`bg-ink-100 rounded animate-pulse ${className}`} />;
}

function DataStripChart({ title, data, colorMap, labelFn, loading }) {
  const total = data.reduce((s, d) => s + d.value, 0);

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs font-semibold uppercase tracking-widest text-ink-500">{title}</p>
      {loading ? (
        <Skeleton className="h-3 w-full rounded-full" />
      ) : (
        <>
          <div className="flex w-full h-3 rounded-full overflow-hidden gap-px">
            {data.map((d, i) => (
              <div
                key={d.name}
                style={{
                  width: `${((d.value / total) * 100).toFixed(2)}%`,
                  backgroundColor: colorMap ? colorMap[d.name] : BUILDING_COLORS[i % BUILDING_COLORS.length],
                }}
                title={`${labelFn ? labelFn(d.name) : d.name}: ${d.value.toLocaleString()}`}
              />
            ))}
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1">
            {data.map((d, i) => (
              <span key={d.name} className="flex items-center gap-1.5 text-xs text-ink-700">
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ backgroundColor: colorMap ? colorMap[d.name] : BUILDING_COLORS[i % BUILDING_COLORS.length] }}
                />
                {labelFn ? labelFn(d.name) : d.name}
                <span className="text-ink-500">({d.value.toLocaleString()})</span>
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

const TrendsTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-surface-card border border-surface-border rounded-lg px-3 py-2 shadow-sm text-sm">
      <p className="font-semibold text-ink-900 mb-0.5">{d.fullLabel}</p>
      <p className="text-ink-700">{d.value.toLocaleString()} complaints</p>
    </div>
  );
};

export default function OverviewView() {
  const navigate = useNavigate();
  const onTabChange = (tab) => navigate(`/${tab}`);
  const statsQ = useStats();
  const clustersQ = useClusters({ limit: 10 });
  const buildingsQ = useBuildings();

  const s = statsQ.data || {};
  const statsLoading = statsQ.isLoading;

  const topClusters = useMemo(() => {
    const list = asArray(clustersQ.data);
    return [...list].sort((a, b) => (b.member_count ?? 0) - (a.member_count ?? 0)).slice(0, 10);
  }, [clustersQ.data]);

  const trendData = useMemo(() => {
    const list = asArray(clustersQ.data);
    return [...list]
      .sort((a, b) => (b.member_count ?? 0) - (a.member_count ?? 0))
      .slice(0, 5)
      .map((c) => ({
        label: (c.label || "").length > 22 ? (c.label || "").slice(0, 21) + "…" : (c.label || ""),
        fullLabel: c.label || `Cluster #${c.id}`,
        value: c.member_count ?? 0,
      }));
  }, [clustersQ.data]);

  const sourceStripData = useMemo(() => {
    const dist = s.source_distribution || {};
    return Object.entries(dist)
      .filter(([, v]) => v > 0)
      .sort((a, b) => b[1] - a[1])
      .map(([name, value]) => ({ name, value }));
  }, [s.source_distribution]);

  const sentimentStripData = useMemo(() => {
    const dist = s.sentiment_distribution || {};
    const order = ["CRITICAL", "HIGH", "NORMAL", "POSITIVE"];
    return order.filter((k) => dist[k] > 0).map((k) => ({ name: k, value: dist[k] }));
  }, [s.sentiment_distribution]);

  const buildingStripData = useMemo(() => {
    const list = buildingsQ.data?.by_primary_use || [];
    return list
      .slice()
      .sort((a, b) => b.count - a.count)
      .slice(0, 6)
      .map((d) => ({ name: d.primary_use, value: d.count }));
  }, [buildingsQ.data]);

  const totalClusters = s.total_clusters ?? 0;
  const criticalCount = s.sentiment_distribution?.CRITICAL ?? 0;

  return (
    <div className="px-6 py-6 lg:px-8 lg:py-8 space-y-6 animate-fade-in">

      {/* Hero KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiTile
          label="Total Complaints"
          value={statsLoading ? null : formatNumber(s.total_complaints)}
          footnote="across all sources"
          loading={statsLoading}
        />
        <KpiTile
          label="Active Themes"
          value={statsLoading ? null : formatNumber(totalClusters)}
          footnote="all emerging"
          loading={statsLoading}
        />
        <KpiTile
          label="Critical Alerts"
          value={statsLoading ? null : formatNumber(criticalCount)}
          footnote="critical sentiment"
          accent={criticalCount > 0}
          loading={statsLoading}
        />
        <KpiTile
          label="Cost Exposure"
          value={statsLoading ? null : formatCompact(s.total_cost_exposure)}
          footnote="this quarter"
          accent
          loading={statsLoading}
        />
      </div>

      {/* Themes + Trends row */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

        {/* Top Themes — wider, 3/5 */}
        <div className="lg:col-span-3 bg-surface-card border border-surface-border rounded-xl p-6 shadow-sm flex flex-col">
          <SectionHeading
            title="Top Complaint Themes"
            action={
              <button
                onClick={() => onTabChange?.("themes")}
                className="text-xs text-carrier hover:text-carrier-dark font-medium transition-colors"
              >
                View all {totalClusters > 0 ? totalClusters : ""}  →
              </button>
            }
          />

          {clustersQ.isLoading ? (
            <div className="space-y-3">
              {[...Array(7)].map((_, i) => (
                <Skeleton key={i} className={`h-10 w-full ${i % 3 === 0 ? "opacity-60" : ""}`} />
              ))}
            </div>
          ) : clustersQ.isError ? (
            <p className="text-ink-500 text-sm">Could not load themes.</p>
          ) : (
            <div>
              {topClusters.map((c, i) => (
                <ThemeListItem
                  key={c.id}
                  rank={i + 1}
                  label={c.label || `Cluster #${c.id}`}
                  memberCount={c.member_count ?? 0}
                  avgSentiment={c.avg_sentiment}
                  isEmerging={!!c.is_emerging}
                />
              ))}
            </div>
          )}
        </div>

        {/* Fastest-Growing Issues — narrower, 2/5 */}
        <div className="lg:col-span-2 bg-surface-card border border-surface-border rounded-xl p-6 shadow-sm flex flex-col">
          <SectionHeading title="Fastest-Growing Issues This Week" />

          {clustersQ.isLoading ? (
            <Skeleton className="flex-1 min-h-[240px] w-full" />
          ) : clustersQ.isError ? (
            <p className="text-ink-500 text-sm">Could not load trend data.</p>
          ) : (
            <div className="flex-1 min-h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={trendData}
                  layout="vertical"
                  margin={{ top: 0, right: 16, left: 0, bottom: 0 }}
                >
                  <XAxis
                    type="number"
                    tick={{ fill: "#64748B", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="label"
                    width={148}
                    tick={{ fill: "#0F172A", fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip content={<TrendsTooltip />} cursor={{ fill: "#F1F5F9" }} />
                  <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                    {trendData.map((_, i) => (
                      <Cell key={i} fill="#1E3A5F" fillOpacity={1 - i * 0.12} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {/* Data Origin Strip */}
      <div className="bg-surface-card border border-surface-border rounded-xl p-6 shadow-sm">
        <h2 className="text-base font-semibold text-ink-900 mb-6">Where Complaints Come From</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <DataStripChart
            title="Sources"
            data={sourceStripData}
            labelFn={sourceLabel}
            loading={statsQ.isLoading}
          />
          <DataStripChart
            title="Sentiment Mix"
            data={sentimentStripData}
            colorMap={SENT_COLORS}
            loading={statsQ.isLoading}
          />
          <DataStripChart
            title="Building Types"
            data={buildingStripData}
            loading={buildingsQ.isLoading}
          />
        </div>
      </div>
    </div>
  );
}
