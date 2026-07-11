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

describe("MCP config mutations", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("adds a new server", async () => {
    const { updateMCPConfig } = await import("@/core/mcp/api");
    vi.mocked(updateMCPConfig).mockResolvedValue(MOCK_MCP_CONFIG);
    const queryClient = createQueryClient();
    queryClient.setQueryData(["mcpConfig"], MOCK_MCP_CONFIG);

    const { useAddMCPServer } = await import("@/core/mcp/hooks");
    const { wrapper } = makeWrapper(queryClient);
    const { result } = renderHook(() => useAddMCPServer(), { wrapper });

    result.current.mutate({
      name: "new-server",
      serverConfig: {
        enabled: true,
        type: "http",
        url: "http://localhost:3333",
        args: [],
        env: {},
        headers: {},
        description: "New server",
      },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(updateMCPConfig).toHaveBeenCalledWith(
      expect.objectContaining({
        mcp_servers: expect.objectContaining({
          "new-server": expect.objectContaining({ type: "http" }),
        }),
      }),
    );
  });

  test("rejects adding without loaded config or with duplicate name", async () => {
    const queryClient = createQueryClient();
    const { useAddMCPServer } = await import("@/core/mcp/hooks");
    const { wrapper, queryClient: client } = makeWrapper(queryClient);
    const { result, rerender } = renderHook(() => useAddMCPServer(), {
      wrapper,
    });

    result.current.mutate({
      name: "new-server",
      serverConfig: MOCK_MCP_CONFIG.mcp_servers["test-server"],
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toEqual(new Error("MCP config not found"));

    client.setQueryData(["mcpConfig"], MOCK_MCP_CONFIG);
    rerender();
    result.current.reset();
    result.current.mutate({
      name: "test-server",
      serverConfig: MOCK_MCP_CONFIG.mcp_servers["test-server"],
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toEqual(
      new Error("MCP server test-server already exists"),
    );
  });

  test("updates an existing server and rejects missing state", async () => {
    const { updateMCPConfig } = await import("@/core/mcp/api");
    vi.mocked(updateMCPConfig).mockResolvedValue(MOCK_MCP_CONFIG);
    const queryClient = createQueryClient();
    queryClient.setQueryData(["mcpConfig"], MOCK_MCP_CONFIG);

    const { useUpdateMCPServer } = await import("@/core/mcp/hooks");
    const { wrapper } = makeWrapper(queryClient);
    const { result } = renderHook(() => useUpdateMCPServer(), { wrapper });

    result.current.mutate({
      name: "test-server",
      serverConfig: {
        ...MOCK_MCP_CONFIG.mcp_servers["test-server"],
        command: "python",
      },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(updateMCPConfig).toHaveBeenCalledWith(
      expect.objectContaining({
        mcp_servers: expect.objectContaining({
          "test-server": expect.objectContaining({ command: "python" }),
        }),
      }),
    );

    result.current.reset();
    result.current.mutate({
      name: "missing",
      serverConfig: MOCK_MCP_CONFIG.mcp_servers["test-server"],
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toEqual(
      new Error("MCP server missing not found"),
    );
  });

  test("deletes a server and preserves the rest", async () => {
    const { updateMCPConfig } = await import("@/core/mcp/api");
    vi.mocked(updateMCPConfig).mockResolvedValue(MOCK_MCP_CONFIG);
    const queryClient = createQueryClient();
    queryClient.setQueryData(["mcpConfig"], MOCK_MCP_CONFIG);

    const { useDeleteMCPServer } = await import("@/core/mcp/hooks");
    const { wrapper } = makeWrapper(queryClient);
    const { result } = renderHook(() => useDeleteMCPServer(), { wrapper });

    result.current.mutate({ name: "test-server" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(updateMCPConfig).toHaveBeenCalledWith({
      mcp_servers: {
        "another-server": MOCK_MCP_CONFIG.mcp_servers["another-server"],
      },
    });
  });

  test("rejects delete and update when config is absent", async () => {
    const { useDeleteMCPServer, useUpdateMCPServer } =
      await import("@/core/mcp/hooks");
    const { wrapper } = makeWrapper();

    const deleteHook = renderHook(() => useDeleteMCPServer(), { wrapper });
    deleteHook.result.current.mutate({ name: "test-server" });
    await waitFor(() => expect(deleteHook.result.current.isError).toBe(true));
    expect(deleteHook.result.current.error).toEqual(
      new Error("MCP config not found"),
    );

    const updateHook = renderHook(() => useUpdateMCPServer(), { wrapper });
    updateHook.result.current.mutate({
      name: "test-server",
      serverConfig: MOCK_MCP_CONFIG.mcp_servers["test-server"],
    });
    await waitFor(() => expect(updateHook.result.current.isError).toBe(true));
    expect(updateHook.result.current.error).toEqual(
      new Error("MCP config not found"),
    );
  });
});
