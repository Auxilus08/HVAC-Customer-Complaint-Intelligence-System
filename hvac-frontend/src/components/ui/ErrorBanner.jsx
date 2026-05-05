export default function ErrorBanner({ message, onRetry }) {
  return (
    <div className="bg-critical/10 border border-critical/40 text-critical rounded-lg p-3 flex items-start gap-3 text-sm">
      <svg
        className="w-5 h-5 flex-shrink-0 mt-0.5"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
      <div className="flex-1 min-w-0">
        <div className="font-medium text-critical">Something went wrong</div>
        <div className="text-critical/80 mt-0.5 break-words">
          {message || "Unknown error"}
        </div>
      </div>
      {onRetry ? (
        <button
          onClick={onRetry}
          className="text-xs font-medium text-critical hover:text-white underline-offset-2 hover:underline whitespace-nowrap"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}
