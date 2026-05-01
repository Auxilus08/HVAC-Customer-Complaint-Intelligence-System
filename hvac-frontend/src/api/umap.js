import { useQuery } from "@tanstack/react-query";
import client from "./client.js";

export const UMAP_KEY = ["umap"];

export function useUmapCoords({ runId = "latest", clusterId } = {}) {
  return useQuery({
    queryKey: [...UMAP_KEY, runId, clusterId],
    queryFn: async () => {
      const params = { run_id: runId };
      if (clusterId != null) params.cluster_id = clusterId;
      const { data } = await client.get("/api/v1/umap", { params });
      return data;
    },
    staleTime: 5 * 60_000,
  });
}
