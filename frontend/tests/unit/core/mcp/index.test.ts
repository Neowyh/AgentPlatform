import { describe, expect, test, vi, afterEach } from "vitest";

vi.mock("@/core/api/errors", () => ({
  extractError: vi.fn(),
}));

vi.mock("@/core/api/fetcher", () => ({
  fetch: vi.fn(),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => "http://localhost:8000"),
}));

vi.mock("@/env", () => ({
  env: {
    NEXT_PUBLIC_BACKEND_BASE_URL: "http://localhost:8000",
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
    "sse-server": {
      enabled: false,
      type: "sse" as const,
      url: "http://localhost:3001",
      args: [],
      env: {},
      headers: {},
      description: "SSE server",
    },
  },
};

describe("mcp index", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  describe("re-exports api functions", () => {
    test("loadMCPConfig is exported as a function", async () => {
      const mcp = await import("@/core/mcp/index");
      expect(typeof mcp.loadMCPConfig).toBe("function");
    });

    test("updateMCPConfig is exported as a function", async () => {
      const mcp = await import("@/core/mcp/index");
      expect(typeof mcp.updateMCPConfig).toBe("function");
    });
  });

  describe("re-exports types", () => {
    test("exports loadMCPConfig and updateMCPConfig from the barrel", async () => {
      const mcp = await import("@/core/mcp/index");
      expect(Object.keys(mcp)).toEqual(
        expect.arrayContaining(["loadMCPConfig", "updateMCPConfig"]),
      );
    });
  });

  describe("loadMCPConfig via barrel", () => {
    test("fetches config from the correct endpoint", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify(MOCK_MCP_CONFIG), { status: 200 }),
      );

      const { loadMCPConfig } = await import("@/core/mcp/index");
      const result = await loadMCPConfig();

      expect(fetcher).toHaveBeenCalledWith(
        "http://localhost:8000/api/mcp/config",
      );
      expect(result.mcp_servers["test-server"]?.enabled).toBe(true);
      expect(result.mcp_servers["test-server"]?.type).toBe("stdio");
      expect(result.mcp_servers["sse-server"]?.enabled).toBe(false);
      expect(result.mcp_servers["sse-server"]?.type).toBe("sse");
    });

    test("returns full config structure with all server fields", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify(MOCK_MCP_CONFIG), { status: 200 }),
      );

      const { loadMCPConfig } = await import("@/core/mcp/index");
      const result = await loadMCPConfig();

      const server = result.mcp_servers["test-server"];
      expect(server?.command).toBe("node");
      expect(server?.args).toEqual(["server.js"]);
      expect(server?.env).toEqual({});
      expect(server?.headers).toEqual({});
      expect(server?.description).toBe("Test server");
    });

    test("calls extractError when response is not ok", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      const errorResponse = new Response(
        JSON.stringify({ detail: "Not found" }),
        { status: 404, statusText: "Not Found" },
      );
      vi.mocked(fetcher).mockResolvedValue(errorResponse);

      const { extractError } = await import("@/core/api/errors");
      vi.mocked(extractError).mockRejectedValue(new Error("Not found"));

      const { loadMCPConfig } = await import("@/core/mcp/index");
      await expect(loadMCPConfig()).rejects.toThrow("Not found");

      expect(extractError).toHaveBeenCalledWith(
        errorResponse,
        "Failed to load MCP config",
      );
    });

    test("calls extractError on server error", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      const errorResponse = new Response(
        JSON.stringify({ detail: "Internal server error" }),
        { status: 500, statusText: "Internal Server Error" },
      );
      vi.mocked(fetcher).mockResolvedValue(errorResponse);

      const { extractError } = await import("@/core/api/errors");
      vi.mocked(extractError).mockRejectedValue(
        new Error("Internal server error"),
      );

      const { loadMCPConfig } = await import("@/core/mcp/index");
      await expect(loadMCPConfig()).rejects.toThrow("Internal server error");

      expect(extractError).toHaveBeenCalledWith(
        errorResponse,
        "Failed to load MCP config",
      );
    });

    test("handles empty mcp_servers object", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify({ mcp_servers: {} }), { status: 200 }),
      );

      const { loadMCPConfig } = await import("@/core/mcp/index");
      const result = await loadMCPConfig();

      expect(result.mcp_servers).toEqual({});
    });

    test("rejects on network error", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockRejectedValue(new Error("Network error"));

      const { loadMCPConfig } = await import("@/core/mcp/index");
      await expect(loadMCPConfig()).rejects.toThrow("Network error");
    });

    test("propagates SyntaxError from response.json for non-JSON response", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response("not-json", { status: 200 }),
      );

      const { loadMCPConfig } = await import("@/core/mcp/index");
      await expect(loadMCPConfig()).rejects.toThrow(SyntaxError);
    });

    test("rejects when server returns null body", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response("null", { status: 200 }),
      );

      const { loadMCPConfig } = await import("@/core/mcp/index");
      await expect(loadMCPConfig()).rejects.toThrow(
        "Invalid MCP config: server returned empty response",
      );
    });
  });

  describe("updateMCPConfig via barrel", () => {
    test("sends PUT request with correct URL, headers, and body", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify(MOCK_MCP_CONFIG), { status: 200 }),
      );

      const { updateMCPConfig } = await import("@/core/mcp/index");
      const result = await updateMCPConfig(MOCK_MCP_CONFIG);

      expect(fetcher).toHaveBeenCalledWith(
        "http://localhost:8000/api/mcp/config",
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(MOCK_MCP_CONFIG),
        },
      );
      expect(result.mcp_servers).toBeDefined();
      expect(result.mcp_servers["test-server"]?.enabled).toBe(true);
    });

    test("serializes config as JSON in request body", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify(MOCK_MCP_CONFIG), { status: 200 }),
      );

      const configToSend = {
        mcp_servers: {
          "custom-server": {
            enabled: true,
            type: "http" as const,
            url: "http://localhost:5000",
            args: ["--verbose"],
            env: { API_KEY: "secret" },
            headers: { Authorization: "Bearer token" },
            description: "Custom HTTP server",
          },
        },
      };

      const { updateMCPConfig } = await import("@/core/mcp/index");
      await updateMCPConfig(configToSend);

      expect(fetcher).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify(configToSend),
        }),
      );
    });

    test("calls extractError on failure", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      const errorResponse = new Response(
        JSON.stringify({ detail: "Bad request" }),
        { status: 400, statusText: "Bad Request" },
      );
      vi.mocked(fetcher).mockResolvedValue(errorResponse);

      const { extractError } = await import("@/core/api/errors");
      vi.mocked(extractError).mockRejectedValue(new Error("Bad request"));

      const { updateMCPConfig } = await import("@/core/mcp/index");
      await expect(updateMCPConfig(MOCK_MCP_CONFIG)).rejects.toThrow(
        "Bad request",
      );

      expect(extractError).toHaveBeenCalledWith(
        errorResponse,
        "Failed to update MCP config",
      );
    });

    test("returns the updated config from server", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      const updatedConfig = {
        mcp_servers: {
          ...MOCK_MCP_CONFIG.mcp_servers,
          "new-server": {
            enabled: true,
            type: "http" as const,
            url: "http://localhost:5000",
            args: [],
            env: {},
            headers: {},
            description: "Newly added",
          },
        },
      };
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify(updatedConfig), { status: 200 }),
      );

      const { updateMCPConfig } = await import("@/core/mcp/index");
      const result = await updateMCPConfig(MOCK_MCP_CONFIG);

      expect(result.mcp_servers["new-server"]?.description).toBe("Newly added");
      expect(result.mcp_servers["test-server"]?.enabled).toBe(true);
    });

    test("rejects on network error", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockRejectedValue(new Error("Network error"));

      const { updateMCPConfig } = await import("@/core/mcp/index");
      await expect(updateMCPConfig(MOCK_MCP_CONFIG)).rejects.toThrow(
        "Network error",
      );
    });

    test("rejects when server returns null body", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response("null", { status: 200 }),
      );

      const { updateMCPConfig } = await import("@/core/mcp/index");
      await expect(updateMCPConfig(MOCK_MCP_CONFIG)).rejects.toThrow(
        "Invalid MCP config: server returned empty response",
      );
    });
  });

  describe("type consistency", () => {
    test("exports same function reference as direct api import", async () => {
      const barrel = await import("@/core/mcp/index");
      const direct = await import("@/core/mcp/api");

      expect(barrel.loadMCPConfig).toBe(direct.loadMCPConfig);
      expect(barrel.updateMCPConfig).toBe(direct.updateMCPConfig);
    });
  });
});
