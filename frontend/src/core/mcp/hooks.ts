import {
  type QueryClient,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "sonner";

import {
  createMCPServers,
  deleteMCPServer,
  loadMCPConfig,
  MCPConfigRequestError,
  updateMCPServer,
  updateMCPServerState,
} from "./api";
import type { MCPServerConfig } from "./types";

export function useMCPConfig() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["mcpConfig"],
    queryFn: () => loadMCPConfig(),
    retry: (count, error) =>
      !(error instanceof MCPConfigRequestError) && count < 3,
  });
  return { config: data, isLoading, error };
}

interface EnableMCPServerVariables {
  serverName: string;
  enabled: boolean;
}

function getMCPErrorMessage(error: Error): string {
  if (
    error instanceof MCPConfigRequestError &&
    (error.isAdminRequired || error.status === 403)
  ) {
    return "MCP configuration is managed by super administrators. Please contact your admin.";
  }
  return error.message;
}

export function getEnableMCPServerMutationOptions(queryClient: QueryClient) {
  return {
    mutationFn: ({ serverName, enabled }: EnableMCPServerVariables) =>
      updateMCPServerState(serverName, enabled),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["mcpConfig"] }),
    onError: (error: Error) => {
      toast.error(getMCPErrorMessage(error));
    },
  };
}

export function useEnableMCPServer() {
  const queryClient = useQueryClient();
  return useMutation(getEnableMCPServerMutationOptions(queryClient));
}

export type MCPServerMutationVariables =
  | {
      operation: "create";
      servers: Record<string, MCPServerConfig>;
    }
  | {
      operation: "update";
      serverName: string;
      server: MCPServerConfig;
    }
  | {
      operation: "delete";
      serverName: string;
    };

export function getMCPServerMutationOptions(queryClient: QueryClient) {
  return {
    mutationFn: (variables: MCPServerMutationVariables) => {
      switch (variables.operation) {
        case "create":
          return createMCPServers(variables.servers);
        case "update":
          return updateMCPServer(variables.serverName, variables.server);
        case "delete":
          return deleteMCPServer(variables.serverName);
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["mcpConfig"] }),
    onError: (error: Error) => {
      toast.error(getMCPErrorMessage(error));
    },
  };
}

export function useMCPServerMutation() {
  const queryClient = useQueryClient();
  return useMutation(getMCPServerMutationOptions(queryClient));
}
