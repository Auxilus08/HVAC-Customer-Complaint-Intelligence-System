const SENTIMENT_DOT = {
  CRITICAL: "bg-status-critical",
  HIGH: "bg-status-high",
  NORMAL: "bg-status-normal",
  POSITIVE: "bg-status-positive",
};

function sentimentKey(avg) {
  if (avg == null) return "NORMAL";
  if (avg < -0.8) return "CRITICAL";
  if (avg < -0.5) return "HIGH";
  if (avg >= 0.2) return "POSITIVE";
  return "NORMAL";
}

export default function ThemeListItem({ rank, label, memberCount, avgSentiment, isEmerging }) {
  const sentKey = sentimentKey(avgSentiment);
  const dotClass = SENTIMENT_DOT[sentKey];

  return (
    <div className="flex items-center gap-4 py-3 border-b border-surface-border last:border-0">
      <span className="w-7 h-7 rounded-full bg-ink-100 text-ink-500 text-xs font-semibold flex items-center justify-center flex-shrink-0">
        {rank}
      </span>

      <span className="flex-1 font-semibold text-ink-900 text-sm leading-snug">
        {label}
      </span>

      <div className="flex items-center gap-2 flex-shrink-0">
        {isEmerging && (
          <svg
            className="w-3.5 h-3.5 text-carrier"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-label="Emerging"
          >
            <polyline points="18 15 12 9 6 15" />
          </svg>
        )}
        <span className="text-xs bg-ink-100 text-ink-700 px-2.5 py-1 rounded-full font-medium">
          {memberCount.toLocaleString()} complaints
        </span>
        <span
          className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${dotClass}`}
          title={sentKey}
        />
      </div>
    </div>
  );
}
