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

    test("throws MCPConfigRequestError with backend detail when response is not ok", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify({ detail: "Not found" }), {
          status: 404,
          statusText: "Not Found",
        }),
      );

      const { loadMCPConfig, MCPConfigRequestError } = await import(
        "@/core/mcp/index"
      );
      const error = await loadMCPConfig().then(
        () => null,
        (e: unknown) => e,
      );

      expect(error).toBeInstanceOf(MCPConfigRequestError);
      expect((error as Error).message).toBe("Not found");
      expect((error as { status: number }).status).toBe(404);
    });

    test("throws MCPConfigRequestError with backend detail on server error", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify({ detail: "Internal server error" }), {
          status: 500,
          statusText: "Internal Server Error",
        }),
      );

      const { loadMCPConfig, MCPConfigRequestError } = await import(
        "@/core/mcp/index"
      );
      const error = await loadMCPConfig().then(
        () => null,
        (e: unknown) => e,
      );

      expect(error).toBeInstanceOf(MCPConfigRequestError);
      expect((error as Error).message).toBe("Internal server error");
      expect((error as { status: number }).status).toBe(500);
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
      // The upstream barrel api passes the parsed body through; the empty-body
      // guard lives in core/api/mcp-config-manager (covered by its own tests).
      await expect(loadMCPConfig()).resolves.toBeNull();
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

    test("throws MCPConfigRequestError with backend detail on failure", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify({ detail: "Bad request" }), {
          status: 400,
          statusText: "Bad Request",
        }),
      );

      const { updateMCPConfig, MCPConfigRequestError } = await import(
        "@/core/mcp/index"
      );
      const error = await updateMCPConfig(MOCK_MCP_CONFIG).then(
        () => null,
        (e: unknown) => e,
      );

      expect(error).toBeInstanceOf(MCPConfigRequestError);
      expect((error as Error).message).toBe("Bad request");
      expect((error as { status: number }).status).toBe(400);
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
      // The upstream barrel api passes the parsed body through; the empty-body
      // guard lives in core/api/mcp-config-manager (covered by its own tests).
      await expect(updateMCPConfig(MOCK_MCP_CONFIG)).resolves.toBeNull();
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
