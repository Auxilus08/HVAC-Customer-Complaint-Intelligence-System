import { useState, useEffect } from "react";
import { Outlet, NavLink, useNavigate, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Layers,
  Map,
  Search,
  Upload,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import { useHealth } from "../hooks/useHealth";
import { useClusters } from "../hooks/useClusters";
import { useKeyboard } from "../hooks/useKeyboard";
import { useQueryClient } from "@tanstack/react-query";
import UploadModal from "./UploadModal";
import AlertBanner from "./AlertBanner";
import KeyboardHelp from "./KeyboardHelp";
import ErrorBoundary from "./ui/ErrorBoundary";
import { asArray } from "../utils/format";

const SIDEBAR_KEY = "hvac_sidebar_collapsed";

const NAV_ITEMS = [
  { to: "/overview", label: "Overview", icon: LayoutDashboard },
  { to: "/themes", label: "Themes", icon: Layers },
  { to: "/map", label: "Map", icon: Map },
  { to: "/search", label: "Search", icon: Search },
];

function LivePill() {
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

function Breadcrumbs() {
  const location = useLocation();
  const { data } = useClusters();
  const clusters = asArray(data);

  const segments = [];
  const path = location.pathname;

  // Parse /themes/:clusterId from path directly — useParams() in a layout
  // route does not receive child route params in React Router v6.
  const themesMatch = path.match(/^\/themes\/(\d+)/);
  const clusterId = themesMatch ? themesMatch[1] : null;

  if (path.startsWith("/overview")) {
    segments.push({ label: "Overview" });
  } else if (path.startsWith("/themes")) {
    segments.push({ label: "Themes", to: "/themes" });
    if (clusterId) {
      const cluster = clusters.find(
        (c) => String(c.id ?? c.cluster_id) === String(clusterId)
      );
      const label = cluster
        ? cluster.label || `Cluster #${clusterId}`
        : `#${clusterId}`;
      segments.push({ label });
    }
  } else if (path.startsWith("/map")) {
    segments.push({ label: "Map" });
  } else if (path.startsWith("/search")) {
    segments.push({ label: "Search" });
  } else {
    segments.push({ label: "Not Found" });
  }

  return (
    <nav className="flex items-center gap-1.5 text-sm" aria-label="Breadcrumb">
      {segments.map((seg, i) => {
        const isLast = i === segments.length - 1;
        return (
          <span key={i} className="flex items-center gap-1.5">
            {i > 0 && <span className="text-ink-300 select-none">›</span>}
            <span
              className={
                isLast
                  ? "text-ink-900 font-medium"
                  : "text-ink-500"
              }
            >
              {seg.label}
            </span>
          </span>
        );
      })}
    </nav>
  );
}

export default function AppShell() {
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(SIDEBAR_KEY) === "true"
  );
  const [uploadOpen, setUploadOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  const toggleCollapsed = () => {
    setCollapsed((v) => {
      const next = !v;
      localStorage.setItem(SIDEBAR_KEY, String(next));
      return next;
    });
  };

  const handleEscape = () => {
    if (uploadOpen) {
      setUploadOpen(false);
      return;
    }
    if (location.pathname.startsWith("/themes/")) {
      navigate("/themes");
      return;
    }
    if (location.pathname === "/search") {
      navigate(-1);
    }
  };

  useKeyboard({
    "/": () => navigate("/search"),
    Escape: handleEscape,
    ArrowLeft: () => {
      if (location.pathname.startsWith("/themes/")) navigate("/themes");
    },
    r: () => queryClient.invalidateQueries(),
    k: (e) => {
      if (e.metaKey || e.ctrlKey) navigate("/search");
    },
  });

  // cmd+K / ctrl+K via separate listener (useKeyboard fires before metaKey check)
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        navigate("/search");
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [navigate]);

  const sidebarW = collapsed ? "w-16" : "w-60";

  return (
    <div className="h-screen flex overflow-hidden bg-surface-soft">
      {/* Sidebar */}
      <aside
        className={`${sidebarW} flex-shrink-0 bg-surface border-r border-surface-border flex flex-col transition-all duration-200 overflow-hidden z-20`}
      >
        {/* Logo block */}
        <div className="flex items-center gap-2.5 px-4 py-4 border-b border-surface-border min-h-[56px]">
          <div className="w-8 h-8 rounded bg-carrier flex items-center justify-center flex-shrink-0">
            <span className="text-white text-[10px] font-bold tracking-tight leading-none">
              HVAC
            </span>
          </div>
          {!collapsed && (
            <div className="leading-tight overflow-hidden">
              <p className="text-ink-900 font-semibold text-sm tracking-tight whitespace-nowrap">
                HVAC Intelligence
              </p>
              <p className="text-ink-500 text-[10px] leading-none">
                Intelligence
              </p>
            </div>
          )}
        </div>

        {/* Nav items */}
        <nav className="flex-1 py-3 space-y-0.5 px-2">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors relative group ${
                  isActive
                    ? "bg-carrier-light text-carrier font-semibold"
                    : "text-ink-700 hover:bg-ink-100 hover:text-ink-900"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 rounded-r bg-carrier" />
                  )}
                  <Icon className="w-5 h-5 flex-shrink-0" />
                  {!collapsed && <span>{label}</span>}
                  {collapsed && (
                    <span className="absolute left-full ml-2 px-2 py-1 bg-ink-900 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
                      {label}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Live status */}
        <div className="px-3 pb-2">
          {collapsed ? (
            <div className="flex justify-center">
              <LivePill />
            </div>
          ) : (
            <LivePill />
          )}
        </div>

        {/* Collapse toggle */}
        <div className="border-t border-surface-border p-2">
          <button
            onClick={toggleCollapsed}
            className="w-full flex items-center justify-center p-2 rounded-lg text-ink-500 hover:bg-ink-100 hover:text-ink-900 transition-colors"
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? (
              <ChevronsRight className="w-4 h-4" />
            ) : (
              <ChevronsLeft className="w-4 h-4" />
            )}
          </button>
        </div>
      </aside>

      {/* Right column: top bar + content */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Top bar */}
        <header className="h-14 flex-shrink-0 bg-surface border-b border-surface-border flex items-center justify-between px-6 z-10">
          <Breadcrumbs />

          <div className="flex items-center gap-3">
            {/* Search shortcut button */}
            <button
              onClick={() => navigate("/search")}
              className="hidden sm:flex items-center gap-2 text-sm text-ink-500 bg-surface-soft border border-surface-border rounded-lg px-3 py-1.5 hover:border-ink-300 transition-colors"
              title="Search complaints (press /)"
            >
              <Search className="w-4 h-4" />
              <span className="hidden md:inline text-ink-500">
                Search complaints…
              </span>
              <kbd className="hidden md:inline bg-surface border border-surface-border rounded px-1.5 py-0.5 text-xs font-mono text-ink-500">
                /
              </kbd>
            </button>

            {/* Upload button */}
            <button
              onClick={() => setUploadOpen(true)}
              className="bg-carrier text-white px-3 py-1.5 rounded-md text-sm font-medium inline-flex items-center gap-1.5 hover:bg-carrier-dark transition-colors"
              data-demo-anchor="upload-btn"
            >
              <Upload className="w-4 h-4" />
              <span className="hidden sm:inline">Upload</span>
            </button>
          </div>
        </header>

        {/* Alert banner */}
        <ErrorBoundary>
          <AlertBanner
            onClusterSelect={(id) => navigate(`/themes/${id}`)}
          />
        </ErrorBoundary>

        {/* Main content */}
        <main className="flex-1 overflow-auto bg-surface-soft">
          <Outlet />
        </main>
      </div>

      <KeyboardHelp />

      {uploadOpen && <UploadModal onClose={() => setUploadOpen(false)} />}
    </div>
  );
}
