import { useQuery } from "@tanstack/react-query";
import { getStats, getHeatmap, getSkus, getSources, getBuildings, getRegionHeatmap, getGeo, getCities } from "../api/analytics";

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

export const useSources = () =>
  useQuery({
    queryKey: ["analytics", "sources"],
    queryFn: getSources,
    refetchInterval: 300_000,
    staleTime: 120_000,
  });

export const useBuildings = () =>
  useQuery({
    queryKey: ["analytics", "buildings"],
    queryFn: getBuildings,
    refetchInterval: 300_000,
    staleTime: 120_000,
  });

export const useRegionHeatmap = () =>
  useQuery({
    queryKey: ["region-heatmap"],
    queryFn: getRegionHeatmap,
    staleTime: 60_000,
  });

export const useGeo = (level) =>
  useQuery({
    queryKey: ["geo", level],
    queryFn: () => getGeo(level),
    staleTime: 5 * 60_000,
    enabled: level === "world" || level === "usa" || level === "india",
  });

export const useCities = () =>
  useQuery({
    queryKey: ["analytics-cities"],
    queryFn: getCities,
    staleTime: 5 * 60_000,
  });
