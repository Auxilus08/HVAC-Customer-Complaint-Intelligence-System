import { useEffect, useMemo, useRef, useState } from "react";
import { useSearch } from "../hooks/useSearch";
import { asArray, formatRelativeTime, sentimentBadge, sentimentLabel } from "../utils/format";
import Spinner from "./ui/Spinner";

const SOURCES = ["crm", "whatsapp", "email", "app", "field_tech", "call_center"];
const SENTIMENTS = ["CRITICAL", "HIGH", "NORMAL", "POSITIVE"];

export default function SearchView({ open, onClose, onSelectCluster, regions = [] }) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [source, setSource] = useState("");
  const [region, setRegion] = useState("");
  const [sentiment, setSentiment] = useState("");
  const [limit, setLimit] = useState(20);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open && inputRef.current) {
      const t = setTimeout(() => inputRef.current?.focus(), 80);
      return () => clearTimeout(t);
    }
  }, [open]);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 400);
    return () => clearTimeout(t);
  }, [query]);

  useEffect(() => {
    setLimit(20);
  }, [debounced, source, region, sentiment]);

  const params = useMemo(() => {
    const p = { limit };
    if (debounced) p.q = debounced;
    if (source) p.source = source;
    if (region) p.region = region;
    if (sentiment) p.sentiment = sentiment;
    return p;
  }, [debounced, source, region, sentiment, limit]);

  const { data, isLoading, isFetching, isError, error } = useSearch(params, open);
  const results = data?.complaints || [];
  const total = data?.total ?? 0;

  if (!open) return null;

  const activeFilters = [
    source && { key: "source", value: source, clear: () => setSource("") },
    region && { key: "region", value: region, clear: () => setRegion("") },
    sentiment && { key: "sentiment", value: sentiment, clear: () => setSentiment("") },
  ].filter(Boolean);

  return (
    <div
      className="fixed inset-0 z-40 flex justify-end bg-black/40 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <aside
        className="w-full max-w-[480px] h-full bg-surface-card border-l border-surface-border flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between px-5 py-4 border-b border-surface-border">
          <h2 className="text-base font-bold text-white tracking-tight">Search Complaints</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded hover:bg-surface-hover"
            aria-label="Close"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </header>

        <div className="px-5 py-3 border-b border-surface-border space-y-3">
          <div className="relative">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="7" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search complaint text..."
              className="w-full bg-surface text-slate-100 text-sm rounded-lg pl-9 pr-3 py-2 border border-surface-border focus:outline-none focus:border-accent"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="bg-surface text-slate-200 text-xs border border-surface-border rounded-md px-2 py-1.5 focus:outline-none focus:border-accent"
            >
              <option value="">All Sources</option>
              {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="bg-surface text-slate-200 text-xs border border-surface-border rounded-md px-2 py-1.5 focus:outline-none focus:border-accent"
            >
              <option value="">All Regions</option>
              {regions.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <select
              value={sentiment}
              onChange={(e) => setSentiment(e.target.value)}
              className="bg-surface text-slate-200 text-xs border border-surface-border rounded-md px-2 py-1.5 focus:outline-none focus:border-accent"
            >
              <option value="">All Sentiment</option>
              {SENTIMENTS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          {activeFilters.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {activeFilters.map((f) => (
                <button
                  key={f.key}
                  onClick={f.clear}
                  className="text-xs bg-accent/20 text-accent rounded-full px-2 py-0.5 hover:bg-accent/30"
                >
                  {f.value} ✕
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-3">
          {isError && (
            <p className="text-sm text-critical p-3 bg-critical/10 rounded">
              {error?.message || "Search failed"}
            </p>
          )}
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <Spinner size="md" />
            </div>
          )}
          {!isLoading && results.length === 0 && (
            <p className="text-slate-400 text-sm text-center py-12">
              No complaints found matching your search.
            </p>
          )}
          {!isLoading && results.length > 0 && (
            <>
              <p className="text-xs text-slate-500 mb-2">
                Showing {results.length} of {total} results
              </p>
              <ul className="space-y-2">
                {results.map((c) => {
                  const lbl = c.sentiment_label || sentimentLabel(c.sentiment_score);
                  const cls =
                    lbl === "CRITICAL"
                      ? "badge-critical"
                      : lbl === "HIGH"
                      ? "badge-high"
                      : lbl === "POSITIVE"
                      ? "badge-positive"
                      : "badge-normal";
                  return (
                    <li
                      key={c.id}
                      onClick={() => {
                        if (c.cluster_id != null) onSelectCluster?.(c.cluster_id);
                        onClose?.();
                      }}
                      className="p-3 bg-surface/40 rounded-lg border border-surface-border/60 hover:border-accent/40 cursor-pointer transition-colors"
                    >
                      <div className="flex items-start gap-2">
                        <span className={`${cls} mt-0.5 shrink-0`}>{lbl}</span>
                        <p className="text-slate-200 text-sm leading-snug">{c.clean_text}</p>
                      </div>
                      <p className="text-xs text-slate-400 mt-1.5 ml-1">
                        {[c.region, c.product_sku, c.source, formatRelativeTime(c.created_at)]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    </li>
                  );
                })}
              </ul>
              {data?.has_more && (
                <button
                  onClick={() => setLimit((l) => l + 20)}
                  disabled={isFetching}
                  className="btn-ghost w-full mt-3 text-sm"
                >
                  {isFetching ? "Loading..." : "Load more"}
                </button>
              )}
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

void asArray;
void sentimentBadge;
