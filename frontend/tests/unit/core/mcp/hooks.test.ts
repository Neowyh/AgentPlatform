import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { describe, test, expect, vi, afterEach } from "vitest";

vi.mock("@/core/mcp/api", () => {
  class MCPConfigRequestError extends Error {
    readonly status: number;
    constructor(status: number, message: string) {
      super(message);
      this.name = "MCPConfigRequestError";
      this.status = status;
    }
    get isAdminRequired(): boolean {
      return this.status === 403;
    }
  }
  return {
    MCPConfigRequestError,
    loadMCPConfig: vi.fn(),
    updateMCPConfig: vi.fn(),
    createMCPServers: vi.fn(),
    updateMCPServer: vi.fn(),
    deleteMCPServer: vi.fn(),
    updateMCPServerState: vi.fn(),
  };
});

vi.mock("@/env", () => ({
  env: {
    NEXT_PUBLIC_BACKEND_BASE_URL: "",
    NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false",
  },
}));

const MOCK_MCP_CONFIG = {
  mcp_servers: {
    "test-server": {
      enabled: true,
      type: "stdio" as const,
      command: "node",
      args: ["server.js"],
      env: {},
      headers: {},
      description: "Test server",
    },
    "another-server": {
      enabled: false,
      type: "sse" as const,
      url: "http://localhost:3001",
      args: [],
      env: {},
      headers: {},
      description: "Another server",
    },
  },
};

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function makeWrapper(queryClient?: QueryClient) {
  const client = queryClient ?? createQueryClient();
  return {
    wrapper: function Wrapper({ children }: { children: React.ReactNode }) {
      return React.createElement(QueryClientProvider, { client }, children);
    },
    queryClient: client,
  };
}

describe("useMCPConfig", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("returns MCP config on success", async () => {
    const { loadMCPConfig } = await import("@/core/mcp/api");
    vi.mocked(loadMCPConfig).mockResolvedValue(MOCK_MCP_CONFIG);

    const { useMCPConfig } = await import("@/core/mcp/hooks");
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useMCPConfig(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.config).toBeDefined();
    expect(result.current.config?.mcp_servers["test-server"]?.enabled).toBe(
      true,
    );
    expect(result.current.error).toBeNull();
  });

  test("returns undefined config on error", async () => {
    const { loadMCPConfig, MCPConfigRequestError } = await import(
      "@/core/mcp/api"
    );
    // A typed MCPConfigRequestError skips the query's retry policy so the
    // error settles immediately.
    vi.mocked(loadMCPConfig).mockRejectedValue(
      new MCPConfigRequestError(500, "Network error"),
    );

    const { useMCPConfig } = await import("@/core/mcp/hooks");
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useMCPConfig(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.config).toBeUndefined();
    expect(result.current.error).toBeDefined();
  });
});

describe("useEnableMCPServer", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("enables a disabled server via the state endpoint", async () => {
    const { updateMCPServerState } = await import("@/core/mcp/api");
    vi.mocked(updateMCPServerState).mockResolvedValue(MOCK_MCP_CONFIG);

    const { useEnableMCPServer } = await import("@/core/mcp/hooks");
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useEnableMCPServer(), { wrapper });

    result.current.mutate({ serverName: "another-server", enabled: true });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(updateMCPServerState).toHaveBeenCalledWith(
      "another-server",
      true,
    );
  });

  test("surfaces an error when the state update fails", async () => {
    const { updateMCPServerState, MCPConfigRequestError } = await import(
      "@/core/mcp/api"
    );
    vi.mocked(updateMCPServerState).mockRejectedValue(
      new MCPConfigRequestError(500, "Failed to update server state"),
    );

    const { useEnableMCPServer } = await import("@/core/mcp/hooks");
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useEnableMCPServer(), { wrapper });

    result.current.mutate({ serverName: "test-server", enabled: false });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeDefined();
  });
});

describe("MCP config mutations", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("creates servers via the create endpoint", async () => {
    const { createMCPServers } = await import("@/core/mcp/api");
    vi.mocked(createMCPServers).mockResolvedValue(MOCK_MCP_CONFIG);
    const queryClient = createQueryClient();

    const { useMCPServerMutation } = await import("@/core/mcp/hooks");
    const { wrapper } = makeWrapper(queryClient);
    const { result } = renderHook(() => useMCPServerMutation(), { wrapper });

    result.current.mutate({
      operation: "create",
      servers: {
        "new-server": {
          enabled: true,
          type: "http",
          url: "http://localhost:3333",
          args: [],
          env: {},
          headers: {},
          description: "New server",
        },
      },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(createMCPServers).toHaveBeenCalledWith(
      expect.objectContaining({
        "new-server": expect.objectContaining({ type: "http" }),
      }),
    );
  });

  test("updates an existing server via the update endpoint", async () => {
    const { updateMCPServer } = await import("@/core/mcp/api");
    vi.mocked(updateMCPServer).mockResolvedValue(MOCK_MCP_CONFIG);
    const queryClient = createQueryClient();

    const { useMCPServerMutation } = await import("@/core/mcp/hooks");
    const { wrapper } = makeWrapper(queryClient);
    const { result } = renderHook(() => useMCPServerMutation(), { wrapper });

    result.current.mutate({
      operation: "update",
      serverName: "test-server",
      server: {
        ...MOCK_MCP_CONFIG.mcp_servers["test-server"]!,
        command: "python",
      },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(updateMCPServer).toHaveBeenCalledWith(
      "test-server",
      expect.objectContaining({ command: "python" }),
    );
  });

  test("deletes a server via the delete endpoint", async () => {
    const { deleteMCPServer } = await import("@/core/mcp/api");
    vi.mocked(deleteMCPServer).mockResolvedValue(MOCK_MCP_CONFIG);
    const queryClient = createQueryClient();

    const { useMCPServerMutation } = await import("@/core/mcp/hooks");
    const { wrapper } = makeWrapper(queryClient);
    const { result } = renderHook(() => useMCPServerMutation(), { wrapper });

    result.current.mutate({ operation: "delete", serverName: "test-server" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(deleteMCPServer).toHaveBeenCalledWith("test-server");
  });

  test("surfaces an error when the mutation fails", async () => {
    const { deleteMCPServer, MCPConfigRequestError } = await import(
      "@/core/mcp/api"
    );
    vi.mocked(deleteMCPServer).mockRejectedValue(
      new MCPConfigRequestError(500, "Failed to delete server"),
    );
    const queryClient = createQueryClient();

    const { useMCPServerMutation } = await import("@/core/mcp/hooks");
    const { wrapper } = makeWrapper(queryClient);
    const { result } = renderHook(() => useMCPServerMutation(), { wrapper });

    result.current.mutate({ operation: "delete", serverName: "test-server" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeDefined();
  });
});
