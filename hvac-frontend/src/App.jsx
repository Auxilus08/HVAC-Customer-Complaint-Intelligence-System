import { useEffect, useState } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import AppShell from "./components/AppShell";
import OverviewView from "./components/OverviewView";
import GeographicView from "./components/GeographicView";
import DrilldownMap from "./components/DrilldownMap";
import DemoMode from "./components/DemoMode";
import ErrorBoundary from "./components/ui/ErrorBoundary";
import SupportInboxView from "./components/SupportInboxView";
import ThemesPage from "./pages/ThemesPage";
import SearchPage from "./pages/SearchPage";
import NotFoundPage from "./pages/NotFoundPage";

function DemoOverlay() {
  const [demoActive, setDemoActive] = useState(false);
  const [selectedClusterId, setSelectedClusterId] = useState(null);
  const location = useLocation();

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get("demo") === "1") setDemoActive(true);
  }, [location.search]);

  if (!demoActive) return null;

  return (
    <DemoMode
      onExit={() => setDemoActive(false)}
      selectedClusterId={selectedClusterId}
      setSelectedClusterId={setSelectedClusterId}
    />
  );
}

export default function App() {
  return (
    <>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route
            path="overview"
            element={
              <ErrorBoundary>
                <OverviewView />
              </ErrorBoundary>
            }
          />
          <Route path="themes" element={<ThemesPage />} />
          <Route path="themes/:clusterId" element={<ThemesPage />} />
          <Route
            path="map"
            element={
              <ErrorBoundary>
                <div className="h-full">
                  <DrilldownMap />
                </div>
              </ErrorBoundary>
            }
          />
          <Route path="search" element={<SearchPage />} />
          <Route
            path="inbox"
            element={
              <ErrorBoundary>
                <SupportInboxView />
              </ErrorBoundary>
            }
          />
          <Route
            path="inbox/:ticketId"
            element={
              <ErrorBoundary>
                <SupportInboxView />
              </ErrorBoundary>
            }
          />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>

      <DemoOverlay />
    </>
  );
}
