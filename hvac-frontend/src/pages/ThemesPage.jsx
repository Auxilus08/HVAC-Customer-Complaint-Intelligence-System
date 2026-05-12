import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ClusterSidebar from "../components/ClusterSidebar";
import ClusterDetail from "../components/ClusterDetail";
import ErrorBoundary from "../components/ui/ErrorBoundary";
import { useClusters } from "../hooks/useClusters";
import { asArray } from "../utils/format";

export default function ThemesPage() {
  const { clusterId } = useParams();
  const navigate = useNavigate();
  const clustersQ = useClusters();

  // Auto-select the largest cluster when no clusterId is in the URL
  useEffect(() => {
    if (clusterId) return;
    const list = asArray(clustersQ.data);
    if (list.length === 0) return;
    const top = [...list].sort(
      (a, b) => (b.member_count ?? 0) - (a.member_count ?? 0)
    )[0];
    if (top?.id != null) {
      navigate(`/themes/${top.id}`, { replace: true });
    }
  }, [clusterId, clustersQ.data, navigate]);

  const selectedId = clusterId ? Number(clusterId) : null;

  return (
    <div className="flex h-full overflow-hidden">
      <ErrorBoundary>
        <ClusterSidebar
          selectedId={selectedId}
          onSelect={(id) => navigate(`/themes/${id}`)}
        />
      </ErrorBoundary>

      <div className="flex-1 overflow-auto p-6">
        {selectedId ? (
          <ErrorBoundary>
            <ClusterDetail
              id={selectedId}
              onBack={() => navigate("/themes")}
            />
          </ErrorBoundary>
        ) : (
          <div className="flex items-center justify-center h-full text-ink-500 text-sm">
            Select a theme from the sidebar to view details.
          </div>
        )}
      </div>
    </div>
  );
}
