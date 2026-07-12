import { useQuery } from "@tanstack/react-query";

import { getAdminStats } from "./api";

export function useAdminStats(enabled = true) {
  return useQuery({
    queryKey: ["adminStats"],
    queryFn: getAdminStats,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
    enabled,
  });
}
