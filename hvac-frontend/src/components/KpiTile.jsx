export default function KpiTile({ label, value, footnote, accent = false, loading = false }) {
  return (
    <div
      className={`bg-surface-card border border-surface-border rounded-xl p-6 shadow-sm flex flex-col gap-1 relative overflow-hidden ${
        accent ? "border-t-4 border-t-carrier" : ""
      }`}
    >
      <span className="text-xs font-semibold uppercase tracking-widest text-ink-500">
        {label}
      </span>
      {loading ? (
        <div className="h-10 w-32 bg-ink-100 rounded animate-pulse mt-1" />
      ) : (
        <span className="text-4xl font-bold text-ink-900 leading-none mt-1">
          {value}
        </span>
      )}
      <span className="text-sm text-ink-500 mt-0.5">{footnote}</span>
    </div>
  );
}
