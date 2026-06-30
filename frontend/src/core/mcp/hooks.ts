import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { loadMCPConfig, updateMCPConfig } from "./api";
import type { MCPConfig } from "./types";

export function useMCPConfig() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["mcpConfig"],
    queryFn: () => loadMCPConfig(),
  });
  return { config: data, isLoading, error };
}

export function useEnableMCPServer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      serverName,
      enabled,
    }: {
      serverName: string;
      enabled: boolean;
    }) => {
      const config = queryClient.getQueryData<MCPConfig>(["mcpConfig"]);
      if (!config) {
        throw new Error("MCP config not found");
      }
      if (!config.mcp_servers[serverName]) {
        throw new Error(`MCP server ${serverName} not found`);
      }
      await updateMCPConfig({
        mcp_servers: {
          ...config.mcp_servers,
          [serverName]: {
            ...config.mcp_servers[serverName],
            enabled,
          },
        },
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["mcpConfig"] });
    },
  });
}

export function useAddMCPServer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      name,
      serverConfig,
    }: {
      name: string;
      serverConfig: MCPConfig["mcp_servers"][string];
    }) => {
      const config = queryClient.getQueryData<MCPConfig>(["mcpConfig"]);
      if (!config) {
        throw new Error("MCP config not found");
      }
      if (config.mcp_servers[name]) {
        throw new Error(`MCP server ${name} already exists`);
      }
      await updateMCPConfig({
        mcp_servers: {
          ...config.mcp_servers,
          [name]: serverConfig,
        },
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["mcpConfig"] });
    },
  });
}

export function useUpdateMCPServer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      name,
      serverConfig,
    }: {
      name: string;
      serverConfig: MCPConfig["mcp_servers"][string];
    }) => {
      const config = queryClient.getQueryData<MCPConfig>(["mcpConfig"]);
      if (!config) {
        throw new Error("MCP config not found");
      }
      if (!config.mcp_servers[name]) {
        throw new Error(`MCP server ${name} not found`);
      }
      await updateMCPConfig({
        mcp_servers: {
          ...config.mcp_servers,
          [name]: serverConfig,
        },
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["mcpConfig"] });
    },
  });
}

export function useDeleteMCPServer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ name }: { name: string }) => {
      const config = queryClient.getQueryData<MCPConfig>(["mcpConfig"]);
      if (!config) {
        throw new Error("MCP config not found");
      }
      const { [name]: _, ...rest } = config.mcp_servers;
      void _;
      await updateMCPConfig({
        mcp_servers: rest,
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["mcpConfig"] });
    },
  });
}
