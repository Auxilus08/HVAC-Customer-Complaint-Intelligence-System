import { useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useClusterDetail, useGenerateAdvisory } from "../api/clusters.js";
import AdvisoryModal from "./AdvisoryModal.jsx";

export default function ClusterDetail({ clusterId }) {
  const { data: cluster, isLoading } = useClusterDetail(clusterId);
  const advisoryMutation = useGenerateAdvisory();
  const [advisory, setAdvisory] = useState(null);

  if (isLoading) {
    return <div className="card animate-pulse text-gray-600 text-sm">Loading…</div>;
  }
  if (!cluster) return null;

  const handleAdvisory = async () => {
    const result = await advisoryMutation.mutateAsync(clusterId);
    setAdvisory(result);
  };

  return (
    <div className="card space-y-4">
      <div>
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-base font-semibold text-white leading-tight">
            {cluster.label ?? `Cluster #${cluster.id}`}
          </h2>
          {cluster.is_emerging && (
            <span className="shrink-0 text-xs bg-orange-900 text-orange-300 px-2 py-0.5 rounded-full">
              Emerging
            </span>
          )}
        </div>

        <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 text-xs text-gray-400">
          <div>
            <span className="text-gray-600">Complaints</span>
            <div className="font-medium text-white">{cluster.member_count ?? "—"}</div>
          </div>
          <div>
            <span className="text-gray-600">Avg Sentiment</span>
            <div
              className={`font-medium ${
                (cluster.avg_sentiment ?? 0) < -0.6
                  ? "text-red-400"
                  : (cluster.avg_sentiment ?? 0) < -0.2
                  ? "text-orange-400"
                  : "text-green-400"
              }`}
            >
              {cluster.avg_sentiment?.toFixed(3) ?? "—"}
            </div>
          </div>
          <div>
            <span className="text-gray-600">WoW Growth</span>
            <div className="font-medium text-white">
              {cluster.growth_pct_wow != null
                ? `${(cluster.growth_pct_wow * 100).toFixed(0)}%`
                : "—"}
            </div>
          </div>
          <div>
            <span className="text-gray-600">Cost Exposure</span>
            <div className="font-medium text-white">
              {cluster.cost_exposure_estimate != null
                ? `₹${Number(cluster.cost_exposure_estimate).toLocaleString("en-IN")}`
                : "—"}
            </div>
          </div>
        </div>
      </div>

      {cluster.trend?.length > 0 && (
        <div>
          <p className="text-xs text-gray-600 mb-1">14-day volume</p>
          <ResponsiveContainer width="100%" height={80}>
            <AreaChart data={cluster.trend}>
              <defs>
                <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" hide />
              <YAxis hide />
              <Tooltip
                contentStyle={{ background: "#111827", border: "1px solid #374151", fontSize: 11 }}
                labelStyle={{ color: "#9ca3af" }}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke="#3b82f6"
                fill="url(#trendGrad)"
                strokeWidth={2}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      <button
        onClick={handleAdvisory}
        disabled={advisoryMutation.isPending}
        className="w-full py-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
      >
        {advisoryMutation.isPending ? "Generating…" : "Generate Technician Advisory"}
      </button>

      {advisory && (
        <AdvisoryModal advisory={advisory} onClose={() => setAdvisory(null)} />
      )}
    </div>
  );
}
