import { useQuery } from "@tanstack/react-query";

import {
  fetchBrowserControlEnabled,
  fetchMcpTasksEnabled,
  fetchKnowledgeCapability,
  fetchSubagentBatchesCapability,
} from "./api";

export function useKnowledgeCapability() {
  const { data, isPending, error } = useQuery({
    queryKey: ["features", "knowledge"],
    queryFn: fetchKnowledgeCapability,
    staleTime: 5000,
    retry: false,
  });
  return {
    enabled: data?.enabled ?? false,
    providerAvailable: data?.providerAvailable ?? false,
    workerRunning: data?.workerRunning ?? false,
    maxFileSize: data?.maxFileSize ?? 0,
    supportedExtensions: data?.supportedExtensions ?? [],
    isLoading: isPending,
    error,
  };
}

export function useBrowserControlEnabled() {
  const { data, isPending } = useQuery({
    queryKey: ["features", "browser_control"],
    queryFn: () => fetchBrowserControlEnabled(),
    staleTime: 0,
    refetchOnMount: true,
    retry: false,
  });

  return {
    enabled: data ?? false,
    isLoading: isPending,
  };
}

export function useMcpTasksEnabled() {
  const { data, isPending } = useQuery({
    queryKey: ["features", "mcp_tasks"],
    queryFn: () => fetchMcpTasksEnabled(),
    staleTime: 0,
    refetchOnMount: true,
    retry: false,
  });

  return {
    enabled: data ?? false,
    isLoading: isPending,
  };
}

export function useSubagentBatchesCapability() {
  const { data, isPending } = useQuery({
    queryKey: ["features", "subagent_batches"],
    queryFn: () => fetchSubagentBatchesCapability(),
    staleTime: 0,
    refetchOnMount: true,
    retry: false,
  });
  return {
    repositoryAvailable: data?.repositoryAvailable ?? false,
    workerRunning: data?.workerRunning ?? false,
    maxRunning: data?.maxRunning ?? 0,
    isLoading: isPending,
  };
}
