import { useMemo } from "react";
import Plot from "react-plotly.js";
import { useUmapCoords } from "../api/umap.js";

const CLUSTER_COLORS = [
  "#3b82f6", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6",
  "#06b6d4", "#f97316", "#84cc16", "#ec4899", "#14b8a6",
  "#6366f1", "#eab308", "#22c55e", "#dc2626", "#a855f7",
];

const SENTIMENT_COLOR = {
  CRITICAL: "#dc2626",
  HIGH: "#ea580c",
  NORMAL: "#6b7280",
  POSITIVE: "#22c55e",
};

export default function UmapScatterPlot({ selectedClusterId, onPointClick }) {
  const { data, isLoading } = useUmapCoords();
  const points = data?.points ?? [];

  const traces = useMemo(() => {
    if (!points.length) return [];

    const byCluster = {};
    for (const p of points) {
      const key = p.cluster_id ?? -1;
      if (!byCluster[key]) byCluster[key] = [];
      byCluster[key].push(p);
    }

    return Object.entries(byCluster).map(([clusterId, pts], idx) => {
      const cid = Number(clusterId);
      const isSelected = selectedClusterId === cid;
      const isNoise = cid === -1;
      const color = isNoise
        ? "#374151"
        : CLUSTER_COLORS[idx % CLUSTER_COLORS.length];

      return {
        type: "scatter",
        mode: "markers",
        name: isNoise ? "Noise" : `Cluster #${cid}`,
        x: pts.map((p) => p.x),
        y: pts.map((p) => p.y),
        customdata: pts.map((p) => p.complaint_id),
        text: pts.map(
          (p) =>
            `Complaint #${p.complaint_id}<br>` +
            `Source: ${p.source ?? "—"}<br>` +
            `SKU: ${p.product_sku ?? "—"}<br>` +
            `Region: ${p.region ?? "—"}<br>` +
            `Sentiment: ${p.sentiment_label ?? "—"}`
        ),
        hoverinfo: "text",
        marker: {
          color: pts.map((p) =>
            p.sentiment_label ? SENTIMENT_COLOR[p.sentiment_label] ?? color : color
          ),
          size: isSelected ? 8 : isNoise ? 3 : 5,
          opacity: isNoise ? 0.3 : isSelected ? 1.0 : 0.75,
          line: isSelected ? { color: "#fff", width: 1 } : undefined,
        },
      };
    });
  }, [points, selectedClusterId]);

  const layout = {
    paper_bgcolor: "#111827",
    plot_bgcolor: "#111827",
    margin: { t: 24, r: 16, b: 32, l: 32 },
    xaxis: { showgrid: false, zeroline: false, showticklabels: false, color: "#374151" },
    yaxis: { showgrid: false, zeroline: false, showticklabels: false, color: "#374151" },
    legend: {
      bgcolor: "transparent",
      font: { color: "#9ca3af", size: 11 },
      itemsizing: "constant",
    },
    font: { color: "#9ca3af" },
    hoverlabel: {
      bgcolor: "#1f2937",
      bordercolor: "#374151",
      font: { color: "#f3f4f6", size: 12 },
    },
  };

  if (isLoading) {
    return (
      <div className="card h-96 flex items-center justify-center text-gray-600 text-sm animate-pulse">
        Loading UMAP…
      </div>
    );
  }

  return (
    <div className="card">
      <h3 className="text-sm font-medium text-gray-400 mb-3">
        Complaint Cluster Map (UMAP 2D)
        {data?.run_id && (
          <span className="ml-2 text-xs text-gray-600 font-mono">{data.run_id}</span>
        )}
      </h3>
      <Plot
        data={traces}
        layout={layout}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: "100%", height: 380 }}
        onClick={(e) => {
          const clusterId = Number(e.points?.[0]?.data?.name?.replace("Cluster #", ""));
          if (!isNaN(clusterId) && clusterId !== -1) onPointClick?.(clusterId);
        }}
      />
      {points.length === 0 && (
        <p className="text-center text-gray-600 text-xs mt-2">
          No UMAP data yet — run the nightly batch job.
        </p>
      )}
    </div>
  );
}
