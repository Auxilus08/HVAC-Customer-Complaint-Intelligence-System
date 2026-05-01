import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "./client.js";

export const CLUSTERS_KEY = ["clusters"];

export function useClusters({ isEmerging, runId, limit = 50, offset = 0 } = {}) {
  return useQuery({
    queryKey: [...CLUSTERS_KEY, { isEmerging, runId, limit, offset }],
    queryFn: async () => {
      const params = { limit, offset };
      if (isEmerging !== undefined) params.is_emerging = isEmerging;
      if (runId) params.run_id = runId;
      const { data } = await client.get("/api/v1/clusters", { params });
      return data;
    },
    staleTime: 60_000,
  });
}

export function useClusterDetail(clusterId) {
  return useQuery({
    queryKey: [...CLUSTERS_KEY, clusterId],
    queryFn: async () => {
      const { data } = await client.get(`/api/v1/clusters/${clusterId}`);
      return data;
    },
    enabled: clusterId != null,
  });
}

export function useGenerateAdvisory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (clusterId) => {
      const { data } = await client.post(`/api/v1/clusters/${clusterId}/advisory`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CLUSTERS_KEY });
    },
  });
}
