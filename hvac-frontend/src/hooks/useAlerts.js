import { useQuery } from "@tanstack/react-query";
import { getAlerts } from "../api/alerts";

export const useAlerts = () =>
  useQuery({
    queryKey: ["alerts"],
    queryFn: getAlerts,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
