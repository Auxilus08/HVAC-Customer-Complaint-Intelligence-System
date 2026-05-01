import { useQuery } from "@tanstack/react-query";
import client from "./client.js";

export const ALERTS_KEY = ["alerts"];

const POLLING_INTERVAL = Number(import.meta.env.VITE_POLLING_INTERVAL_MS) || 60_000;

export function useAlerts({ severity, limit = 20 } = {}) {
  return useQuery({
    queryKey: [...ALERTS_KEY, { severity, limit }],
    queryFn: async () => {
      const params = { limit };
      if (severity) params.severity = severity;
      const { data } = await client.get("/api/v1/alerts", { params });
      return data;
    },
    refetchInterval: POLLING_INTERVAL,
    staleTime: POLLING_INTERVAL / 2,
  });
}
