import { useQuery } from "@tanstack/react-query";
import { searchComplaints } from "../api/search";

export const useSearch = (params, enabled = true) =>
  useQuery({
    queryKey: ["search", params],
    queryFn: () => searchComplaints(params),
    enabled,
    staleTime: 10_000,
    keepPreviousData: true,
  });
