import { useQuery } from "@tanstack/react-query";
import { getComplaintLocations } from "../api/complaints";

export const useComplaintLocations = (limit = 5000) =>
  useQuery({
    queryKey: ["complaints-locations", limit],
    queryFn: () => getComplaintLocations(limit),
    staleTime: 120_000,
    refetchOnWindowFocus: false,
  });
