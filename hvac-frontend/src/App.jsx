import { useState } from "react";
import { Routes, Route, NavLink } from "react-router-dom";

import AlertBanner from "./components/AlertBanner.jsx";
import ClusterSidebar from "./components/ClusterSidebar.jsx";
import ClusterDetail from "./components/ClusterDetail.jsx";
import UmapScatterPlot from "./components/UmapScatterPlot.jsx";
import UploadDropzone from "./components/UploadDropzone.jsx";

function DashboardLayout() {
  const [selectedClusterId, setSelectedClusterId] = useState(null);

  return (
    <div className="h-full flex flex-col">
      <AlertBanner />

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-72 flex-shrink-0 border-r border-gray-800 overflow-y-auto">
          <div className="p-4 border-b border-gray-800">
            <h1 className="text-lg font-semibold text-white tracking-tight">
              HVAC Intelligence
            </h1>
            <p className="text-xs text-gray-500 mt-0.5">Complaint Pattern Radar</p>
          </div>
          <ClusterSidebar
            selectedId={selectedClusterId}
            onSelect={setSelectedClusterId}
          />
        </aside>

        {/* Main panel */}
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <div className="xl:col-span-2">
              <UmapScatterPlot
                selectedClusterId={selectedClusterId}
                onPointClick={setSelectedClusterId}
              />
            </div>
            <div>
              {selectedClusterId ? (
                <ClusterDetail clusterId={selectedClusterId} />
              ) : (
                <div className="card h-full flex items-center justify-center text-gray-600 text-sm">
                  Select a cluster to view details
                </div>
              )}
            </div>
          </div>

          <UploadDropzone />
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/*" element={<DashboardLayout />} />
    </Routes>
  );
}
