import { useQuery } from "@tanstack/react-query";
import { getStats, getHeatmap, getSkus } from "../api/analytics";

export const useStats = () =>
  useQuery({
    queryKey: ["analytics", "stats"],
    queryFn: getStats,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

export const useHeatmap = () =>
  useQuery({
    queryKey: ["analytics", "heatmap"],
    queryFn: getHeatmap,
    refetchInterval: 300_000,
    staleTime: 120_000,
  });

export const useSkus = () =>
  useQuery({
    queryKey: ["analytics", "skus"],
    queryFn: getSkus,
    refetchInterval: 300_000,
    staleTime: 120_000,
  });
