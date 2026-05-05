import { useQuery } from "@tanstack/react-query";
import {
  getClusters,
  getClusterDetail,
  getAdvisory,
  getClusterTrend,
} from "../api/clusters";

export const useClusters = (filters = {}) =>
  useQuery({
    queryKey: ["clusters", filters],
    queryFn: () => getClusters(filters),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

export const useClusterDetail = (id) =>
  useQuery({
    queryKey: ["cluster", id],
    queryFn: () => getClusterDetail(id),
    enabled: !!id,
  });

export const useAdvisory = (id, enabled = false) =>
  useQuery({
    queryKey: ["advisory", id],
    queryFn: () => getAdvisory(id),
    enabled: !!id && enabled,
    staleTime: Infinity,
    retry: 1,
  });

export const useClusterTrend = (id, days = 30) =>
  useQuery({
    queryKey: ["cluster-trend", id, days],
    queryFn: () => getClusterTrend(id, days),
    enabled: !!id,
    staleTime: 60_000,
  });
