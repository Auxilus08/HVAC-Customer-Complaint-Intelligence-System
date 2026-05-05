import { formatCurrencyINR, formatPercent } from "../utils/format";

const downloadBlob = (content, filename, mime) => {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

const csvCell = (v) => {
  if (v === null || v === undefined) return "";
  const s = String(v);
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
};

const safeName = (s) =>
  String(s || "")
    .replace(/[^a-zA-Z0-9_-]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 60);

export const exportClusterCSV = (cluster) => {
  const id = cluster.id ?? cluster.cluster_id ?? "0";
  const label = safeName(cluster.label) || `cluster_${id}`;
  const date = new Date().toISOString().slice(0, 10);
  const rows = cluster.recent_complaints || cluster.complaints || cluster.samples || [];
  const cols = [
    "id",
    "clean_text",
    "source",
    "region",
    "product_sku",
    "sentiment_label",
    "sentiment_score",
    "created_at",
  ];
  const header = cols.join(",");
  const body = rows
    .map((r) =>
      cols
        .map((c) => csvCell(r[c] ?? r.text ?? (c === "product_sku" ? r.sku : "")))
        .join(",")
    )
    .join("\n");
  downloadBlob(`${header}\n${body}\n`, `cluster_${id}_${label}_${date}.csv`, "text/csv");
};

export const exportAdvisoryText = (advisoryText, cluster) => {
  const id = cluster.id ?? cluster.cluster_id ?? "0";
  const label = cluster.label || `Cluster #${id}`;
  const date = new Date().toISOString();
  const lines = [
    "HVAC SERVICE ADVISORY",
    "=====================",
    `Cluster: ${label}`,
    `Generated: ${date}`,
    "Powered by: Gemini 2.5 Flash Lite",
    "",
    advisoryText.replace(/^##\s*/gm, "").replace(/\*\*/g, ""),
  ];
  downloadBlob(
    lines.join("\n"),
    `advisory_${id}_${date.slice(0, 10)}.txt`,
    "text/plain"
  );
};

export const exportSystemReport = ({ stats, clusters, alerts }) => {
  const date = new Date().toISOString();
  const total = stats?.total_complaints ?? 0;
  const emerging = stats?.emerging_clusters ?? 0;
  const sil = stats?.last_silhouette_score;
  const expo = stats?.total_cost_exposure ?? 0;

  const md = [
    "# HVAC Complaint Intelligence Report",
    `Generated: ${date}`,
    "",
    "## Executive Summary",
    `The system processed **${total} complaints** across ${stats?.total_clusters ?? 0} clusters. ` +
      `${emerging} emerging pattern${emerging === 1 ? "" : "s"} detected. ` +
      `Total cost exposure: **${formatCurrencyINR(expo)}**.` +
      (sil != null ? ` Last silhouette score: **${sil.toFixed(3)}**.` : ""),
    "",
    "## Active Clusters",
    "| ID | Label | Members | Avg Sentiment | Growth WoW | Exposure |",
    "|---:|---|---:|---:|---:|---:|",
    ...(clusters || []).map((c) => {
      const id = c.id ?? c.cluster_id;
      const sent = c.avg_sentiment != null ? Number(c.avg_sentiment).toFixed(2) : "—";
      const growth = c.growth_pct_wow != null ? formatPercent(c.growth_pct_wow) : "—";
      const exposureCell = c.cost_exposure_estimate != null
        ? formatCurrencyINR(c.cost_exposure_estimate)
        : "—";
      return `| ${id} | ${c.label || "Unlabeled"} | ${c.member_count ?? 0} | ${sent} | ${growth} | ${exposureCell} |`;
    }),
    "",
    "## Emerging Alerts",
    ...(alerts && alerts.length
      ? [
          "| Cluster | Region | Growth | Exposure | Severity |",
          "|---|---|---:|---:|---|",
          ...alerts.map(
            (a) =>
              `| ${a.cluster_label || a.label || "—"} | ${a.region || "—"} | ${
                a.growth_pct_wow != null ? formatPercent(a.growth_pct_wow) : "—"
              } | ${a.exposure_inr != null ? formatCurrencyINR(a.exposure_inr) : "—"} | ${a.severity || "—"} |`
          ),
        ]
      : ["_No active emerging alerts._"]),
    "",
    "## Recommendations",
    "1. Prioritize the highest-growth emerging cluster — dispatch field engineering review.",
    "2. Audit the SKU with the highest critical-sentiment ratio before next service quarter.",
    "3. Monitor regions with WoW growth > 30% for cascading failure patterns.",
    "",
  ].join("\n");
  downloadBlob(md, `hvac_report_${date.slice(0, 10)}.md`, "text/markdown");
};
