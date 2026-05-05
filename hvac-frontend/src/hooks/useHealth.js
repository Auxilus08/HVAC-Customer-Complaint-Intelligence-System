import { useQuery } from "@tanstack/react-query";
import { getHealth } from "../api/health";

export const useHealth = () =>
  useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
    staleTime: 15_000,
    retry: 0,
  });
