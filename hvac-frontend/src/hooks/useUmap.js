import { useQuery } from "@tanstack/react-query";
import { getUmapCoords } from "../api/umap";

export const useUmap = () =>
  useQuery({
    queryKey: ["umap"],
    queryFn: () => getUmapCoords(),
    staleTime: 300_000,
    refetchInterval: 300_000,
  });
