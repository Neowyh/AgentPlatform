import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { describe, test, expect, vi, afterEach } from "vitest";

vi.mock("@/core/mcp/api", () => ({
  loadMCPConfig: vi.fn(),
  updateMCPConfig: vi.fn(),
}));

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
    const { loadMCPConfig } = await import("@/core/mcp/api");
    vi.mocked(loadMCPConfig).mockRejectedValue(new Error("Network error"));

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

  test("enables a disabled server", async () => {
    const { loadMCPConfig, updateMCPConfig } = await import("@/core/mcp/api");
    vi.mocked(loadMCPConfig).mockResolvedValue(MOCK_MCP_CONFIG);
    vi.mocked(updateMCPConfig).mockResolvedValue({
      mcp_servers: {
        ...MOCK_MCP_CONFIG.mcp_servers,
        "another-server": {
          ...MOCK_MCP_CONFIG.mcp_servers["another-server"],
          enabled: true,
        },
      },
    });

    // Pre-populate the query cache so useEnableMCPServer's internal
    // useMCPConfig() call resolves immediately.
    const queryClient = createQueryClient();
    queryClient.setQueryData(["mcpConfig"], MOCK_MCP_CONFIG);

    const { useEnableMCPServer } = await import("@/core/mcp/hooks");
    const { wrapper } = makeWrapper(queryClient);
    const { result } = renderHook(() => useEnableMCPServer(), { wrapper });

    result.current.mutate({ serverName: "another-server", enabled: true });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(updateMCPConfig).toHaveBeenCalledWith(
      expect.objectContaining({
        mcp_servers: expect.objectContaining({
          "another-server": expect.objectContaining({ enabled: true }),
        }),
      }),
    );
  });

  test("throws when config is not loaded", async () => {
    const { loadMCPConfig } = await import("@/core/mcp/api");
    vi.mocked(loadMCPConfig).mockRejectedValue(new Error("Network error"));

    const { useEnableMCPServer } = await import("@/core/mcp/hooks");
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useEnableMCPServer(), { wrapper });

    // Wait for the internal query to settle with an error
    await waitFor(() => expect(result.current.status).toBeDefined());

    result.current.mutate({ serverName: "test-server", enabled: false });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeDefined();
  });

  test("throws when server name does not exist", async () => {
    const { loadMCPConfig } = await import("@/core/mcp/api");
    vi.mocked(loadMCPConfig).mockResolvedValue(MOCK_MCP_CONFIG);

    // Pre-populate cache so the hook has config immediately
    const queryClient = createQueryClient();
    queryClient.setQueryData(["mcpConfig"], MOCK_MCP_CONFIG);

    const { useEnableMCPServer } = await import("@/core/mcp/hooks");
    const { wrapper } = makeWrapper(queryClient);
    const { result } = renderHook(() => useEnableMCPServer(), { wrapper });

    result.current.mutate({
      serverName: "nonexistent-server",
      enabled: true,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeDefined();
  });
});
