import { useEffect, useMemo, useState } from "react";
import Plot from "react-plotly.js";
import { useUmap } from "../hooks/useUmap";
import { useClusters } from "../hooks/useClusters";
import {
  asArray,
  CLUSTER_COLORS,
  truncate,
} from "../utils/format";
import Spinner from "./ui/Spinner";
import EmptyState from "./ui/EmptyState";
import ErrorBanner from "./ui/ErrorBanner";

const NOISE_COLOR = "#334155";

export default function UmapScatterPlot({ onClusterClick }) {
  const { data: umapData, isLoading, isError, error, refetch } = useUmap();
  const { data: clustersData } = useClusters();
  const allPoints = asArray(umapData);
  const clusters = asArray(clustersData);

  // Progressive rendering: paint first 200 points immediately, then the rest.
  const [visibleCap, setVisibleCap] = useState(200);
  useEffect(() => {
    if (allPoints.length <= 200) {
      setVisibleCap(Infinity);
      return undefined;
    }
    setVisibleCap(200);
    const t = setTimeout(() => setVisibleCap(Infinity), 100);
    return () => clearTimeout(t);
  }, [allPoints.length]);
  const points = visibleCap === Infinity ? allPoints : allPoints.slice(0, visibleCap);

  const labelById = useMemo(() => {
    const m = new Map();
    clusters.forEach((c) => {
      const id = c.id ?? c.cluster_id;
      m.set(id, c.label || `Cluster #${id}`);
    });
    return m;
  }, [clusters]);

  const traces = useMemo(() => {
    if (points.length === 0) return [];
    const groups = new Map();
    points.forEach((p) => {
      const cid = p.cluster_id ?? null;
      const key = cid === null || cid === undefined || cid === -1 ? "noise" : cid;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(p);
    });

    const tArr = [];
    const sortedKeys = Array.from(groups.keys()).sort((a, b) => {
      if (a === "noise") return 1;
      if (b === "noise") return -1;
      return a - b;
    });

    sortedKeys.forEach((key) => {
      const list = groups.get(key);
      const isNoise = key === "noise";
      const cid = isNoise ? -1 : key;
      const color = isNoise
        ? NOISE_COLOR
        : CLUSTER_COLORS[((cid % CLUSTER_COLORS.length) + CLUSTER_COLORS.length) % CLUSTER_COLORS.length];
      const name = isNoise
        ? "Noise / unclustered"
        : labelById.get(cid) || `Cluster #${cid}`;

      tArr.push({
        type: "scatter",
        mode: "markers",
        name,
        x: list.map((p) => p.x ?? p.coord_x ?? 0),
        y: list.map((p) => p.y ?? p.coord_y ?? 0),
        text: list.map((p) =>
          truncate(p.clean_text || p.text || p.complaint_text || "", 100)
        ),
        customdata: list.map((p) => [
          p.complaint_id ?? p.id ?? null,
          p.source ?? "—",
          p.sentiment_label ?? p.sentiment ?? "—",
          isNoise ? -1 : cid,
        ]),
        marker: {
          color,
          size: isNoise ? 4 : 7,
          opacity: isNoise ? 0.4 : 0.8,
          line: { width: 0.5, color: "#0f172a" },
        },
        hovertemplate:
          "<b>%{text}</b><br>" +
          "Source: %{customdata[1]}<br>" +
          "Sentiment: %{customdata[2]}<br>" +
          "<extra>%{fullData.name}</extra>",
      });
    });
    return tArr;
  }, [points, labelById]);

  const layout = useMemo(
    () => ({
      paper_bgcolor: "#0f172a",
      plot_bgcolor: "#1e293b",
      font: { color: "#94a3b8", family: "Inter" },
      margin: { t: 40, r: 20, b: 40, l: 20 },
      showlegend: true,
      legend: {
        bgcolor: "#1e293b",
        bordercolor: "#334155",
        borderwidth: 1,
        font: { color: "#94a3b8", size: 11 },
        x: 1.02,
        y: 1,
      },
      xaxis: {
        showgrid: false,
        zeroline: false,
        showticklabels: false,
        title: "",
      },
      yaxis: {
        showgrid: false,
        zeroline: false,
        showticklabels: false,
        title: "",
      },
      title: {
        text: "Complaint Cluster Map",
        font: { color: "#f1f5f9", size: 16 },
        x: 0.02,
      },
      hoverlabel: {
        bgcolor: "#1e293b",
        bordercolor: "#334155",
        font: { color: "#f1f5f9", size: 12 },
      },
      autosize: true,
    }),
    []
  );

  const config = useMemo(
    () => ({
      responsive: true,
      displayModeBar: true,
      modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d"],
      displaylogo: false,
      toImageButtonOptions: { filename: "hvac_clusters" },
    }),
    []
  );

  if (isLoading) {
    return (
      <div className="card flex flex-col items-center justify-center min-h-[60vh]">
        <Spinner size="lg" />
        <p className="text-slate-400 mt-4 text-sm">Loading cluster map…</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="card">
        <ErrorBanner
          message={error?.message || "Failed to load UMAP coordinates"}
          onRetry={refetch}
        />
      </div>
    );
  }

  if (points.length === 0) {
    return (
      <div className="card min-h-[60vh] flex items-center justify-center">
        <EmptyState
          icon="🗺️"
          title="No UMAP data available"
          description="Run the nightly clustering job to populate the cluster map."
        />
        <pre className="absolute bottom-8 left-1/2 -translate-x-1/2 text-xs bg-surface px-3 py-1.5 rounded-md font-mono text-accent border border-surface-border">
          make cluster
        </pre>
      </div>
    );
  }

  return (
    <div className="card p-2 overflow-hidden" data-demo-anchor="umap">
      <Plot
        data={traces}
        layout={layout}
        config={config}
        useResizeHandler
        style={{ width: "100%", height: "calc(100vh - 160px)" }}
        onClick={(evt) => {
          const pt = evt?.points?.[0];
          if (!pt) return;
          const cid = pt.customdata?.[3];
          if (cid !== undefined && cid !== null && cid !== -1) {
            onClusterClick?.(cid);
          }
        }}
      />
    </div>
  );
}
