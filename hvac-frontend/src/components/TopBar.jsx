import { useHealth } from "../hooks/useHealth";

const NAV_TABS = [
  { id: "overview", label: "Overview" },
  { id: "themes", label: "Themes" },
  { id: "map", label: "Map" },
  { id: "search", label: "Search" },
];

function HealthPill() {
  const health = useHealth();
  const ok = health.isSuccess && !health.isError;
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${
        ok
          ? "bg-status-positive/10 text-status-positive"
          : "bg-status-critical/10 text-status-critical"
      }`}
    >
      <span className="relative flex h-1.5 w-1.5">
        {ok && (
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-status-positive opacity-60" />
        )}
        <span
          className={`relative inline-flex rounded-full h-1.5 w-1.5 ${
            ok ? "bg-status-positive" : "bg-status-critical"
          }`}
        />
      </span>
      {ok ? "Live" : "Offline"}
    </span>
  );
}

export default function TopBar({ activeTab, onTabChange, onUploadClick, onSearchClick }) {
  return (
    <header
      className="h-14 bg-surface-card border-b border-surface-border px-6 flex items-center justify-between flex-shrink-0 shadow-sm"
      data-demo-anchor="topbar"
    >
      {/* Logo */}
      <div className="flex items-center gap-3">
        <div className="w-2 h-7 rounded-sm bg-carrier flex-shrink-0" />
        <div className="leading-tight">
          <h1 className="font-bold text-ink-900 text-base tracking-tight">
            HVAC Intelligence
          </h1>
          <p className="text-ink-500 text-[10px] leading-none">by Carrier</p>
        </div>
      </div>

      {/* Nav tabs */}
      <nav className="hidden md:flex items-center gap-1">
        {NAV_TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`px-4 py-2 text-sm font-medium rounded-md transition-colors relative ${
                isActive
                  ? "text-carrier"
                  : "text-ink-700 hover:text-ink-900 hover:bg-ink-100"
              }`}
            >
              {tab.label}
              {isActive && (
                <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-3/4 h-0.5 bg-carrier rounded-full" />
              )}
            </button>
          );
        })}
      </nav>

      {/* Right side */}
      <div className="flex items-center gap-3">
        <HealthPill />
        <button
          onClick={onSearchClick}
          className="btn-ghost text-sm"
          title="Search (press /)"
          aria-label="Search"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="7" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </button>
        <button
          onClick={onUploadClick}
          className="btn-primary text-sm"
          data-demo-anchor="upload-btn"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          Upload
        </button>
      </div>
    </header>
  );
}
