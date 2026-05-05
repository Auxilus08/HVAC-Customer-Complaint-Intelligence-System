import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import TopBar from "./components/TopBar";
import AlertBanner from "./components/AlertBanner";
import ClusterSidebar from "./components/ClusterSidebar";
import UmapScatterPlot from "./components/UmapScatterPlot";
import ClusterDetail from "./components/ClusterDetail";
import AnalyticsView from "./components/AnalyticsView";
import UploadModal from "./components/UploadModal";
import SearchView from "./components/SearchView";
import DemoMode from "./components/DemoMode";
import KeyboardHelp from "./components/KeyboardHelp";
import ErrorBoundary from "./components/ui/ErrorBoundary";
import { useClusters } from "./hooks/useClusters";
import { useUmap } from "./hooks/useUmap";
import { useAlerts } from "./hooks/useAlerts";
import { useStats } from "./hooks/useAnalytics";
import { useKeyboard } from "./hooks/useKeyboard";
import { asArray } from "./utils/format";

function Tabs({ active, onChange }) {
  const tabs = [
    { id: "map", label: "Cluster Map" },
    { id: "analytics", label: "Analytics" },
  ];
  return (
    <div className="flex items-center gap-1 bg-surface-card/60 rounded-full p-1 mb-3 w-fit border border-surface-border">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={`px-4 py-1.5 text-sm rounded-full transition-colors ${
            active === t.id
              ? "bg-accent text-white font-medium"
              : "text-slate-400 hover:text-white"
          }`}
          data-demo-anchor={`tab-${t.id}`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export default function App() {
  const [selectedClusterId, setSelectedClusterId] = useState(null);
  const [activeTab, setActiveTab] = useState("map");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [demoActive, setDemoActive] = useState(false);
  const queryClient = useQueryClient();

  // Parallel data fetching on mount — all hooks here so QueryClient
  // fires them simultaneously.
  const clustersQ = useClusters();
  useUmap();
  useAlerts();
  useStats();

  const regions = useMemo(() => {
    const set = new Set();
    asArray(clustersQ.data).forEach((c) => {
      const arr = c.regions || (c.region ? [c.region] : []);
      arr.forEach((r) => r && set.add(r));
    });
    return Array.from(set).sort();
  }, [clustersQ.data]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("demo") === "1") setDemoActive(true);
  }, []);

  const showDemoButton =
    import.meta.env.DEV ||
    (typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).get("demo") === "1");

  const handleEscape = () => {
    if (searchOpen) setSearchOpen(false);
    else if (uploadOpen) setUploadOpen(false);
    else if (demoActive) setDemoActive(false);
    else if (selectedClusterId) setSelectedClusterId(null);
  };

  const handleBack = () => {
    if (selectedClusterId) setSelectedClusterId(null);
  };

  const handleRefresh = () => {
    queryClient.invalidateQueries();
  };

  useKeyboard({
    "/": () => setSearchOpen(true),
    Escape: handleEscape,
    ArrowLeft: handleBack,
    d: () => setDemoActive((v) => !v),
    u: () => {
      setSelectedClusterId(null);
      setActiveTab("map");
    },
    a: () => {
      setSelectedClusterId(null);
      setActiveTab("analytics");
    },
    r: handleRefresh,
  });

  return (
    <div className="h-screen flex flex-col bg-surface overflow-hidden">
      <TopBar
        onUploadClick={() => setUploadOpen(true)}
        onSearchClick={() => setSearchOpen(true)}
        onDemoClick={() => setDemoActive(true)}
        showDemoButton={showDemoButton}
      />
      <ErrorBoundary>
        <AlertBanner onClusterSelect={setSelectedClusterId} />
      </ErrorBoundary>
      <div className="flex flex-1 overflow-hidden">
        <ErrorBoundary>
          <ClusterSidebar
            selectedId={selectedClusterId}
            onSelect={setSelectedClusterId}
          />
        </ErrorBoundary>
        <main className="flex-1 overflow-auto p-4">
          {selectedClusterId ? (
            <ErrorBoundary>
              <ClusterDetail
                id={selectedClusterId}
                onBack={() => setSelectedClusterId(null)}
              />
            </ErrorBoundary>
          ) : (
            <>
              <Tabs active={activeTab} onChange={setActiveTab} />
              {activeTab === "map" ? (
                <ErrorBoundary>
                  <UmapScatterPlot onClusterClick={setSelectedClusterId} />
                </ErrorBoundary>
              ) : (
                <ErrorBoundary>
                  <AnalyticsView />
                </ErrorBoundary>
              )}
            </>
          )}
        </main>
      </div>
      <KeyboardHelp />
      {uploadOpen && <UploadModal onClose={() => setUploadOpen(false)} />}
      <SearchView
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        onSelectCluster={(id) => {
          setSelectedClusterId(id);
          setSearchOpen(false);
        }}
        regions={regions}
      />
      {demoActive && (
        <DemoMode
          onExit={() => setDemoActive(false)}
          selectedClusterId={selectedClusterId}
          setSelectedClusterId={setSelectedClusterId}
          setActiveTab={setActiveTab}
        />
      )}
    </div>
  );
}
