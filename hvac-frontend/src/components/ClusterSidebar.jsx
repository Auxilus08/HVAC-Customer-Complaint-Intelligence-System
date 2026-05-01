import { useClusters } from "../api/clusters.js";
import { LineChart, Line, ResponsiveContainer } from "recharts";

function SentimentBadge({ score }) {
  if (score == null) return null;
  let cls = "badge-normal";
  if (score < -0.6) cls = "badge-critical";
  else if (score < -0.2) cls = "badge-high";
  else if (score >= 0.2) cls = "badge-positive";
  return <span className={cls}>{score.toFixed(2)}</span>;
}

function Sparkline({ trend }) {
  if (!trend?.length) return null;
  return (
    <ResponsiveContainer width={60} height={24}>
      <LineChart data={trend}>
        <Line
          type="monotone"
          dataKey="count"
          stroke="#3b82f6"
          strokeWidth={1.5}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export default function ClusterSidebar({ selectedId, onSelect }) {
  const { data, isLoading } = useClusters({ limit: 100 });
  const clusters = data?.clusters ?? [];

  if (isLoading) {
    return (
      <div className="p-4 text-gray-600 text-sm animate-pulse">
        Loading clusters…
      </div>
    );
  }

  return (
    <nav className="py-2">
      {clusters.map((c) => (
        <button
          key={c.id}
          onClick={() => onSelect(c.id)}
          className={`w-full text-left px-4 py-3 border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors ${
            selectedId === c.id ? "bg-gray-800 border-l-2 border-l-brand-500" : ""
          }`}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 mb-0.5">
                {c.is_emerging && (
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-orange-400 shrink-0" />
                )}
                <span className="text-sm font-medium text-gray-200 truncate">
                  {c.label ?? `Cluster #${c.id}`}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">{c.member_count} complaints</span>
                {c.growth_pct_wow != null && (
                  <span
                    className={`text-xs ${
                      c.growth_pct_wow > 0.5
                        ? "text-orange-400"
                        : c.growth_pct_wow > 0
                        ? "text-yellow-500"
                        : "text-gray-600"
                    }`}
                  >
                    {c.growth_pct_wow > 0 ? "+" : ""}
                    {(c.growth_pct_wow * 100).toFixed(0)}% WoW
                  </span>
                )}
              </div>
            </div>
            <div className="flex flex-col items-end gap-1 shrink-0">
              <SentimentBadge score={c.avg_sentiment} />
            </div>
          </div>
        </button>
      ))}

      {clusters.length === 0 && (
        <div className="px-4 py-8 text-gray-600 text-sm text-center">
          No clusters yet. Upload complaints and run the batch job.
        </div>
      )}
    </nav>
  );
}
