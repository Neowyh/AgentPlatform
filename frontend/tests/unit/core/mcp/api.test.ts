import { describe, test, expect, vi, afterEach } from "vitest";

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
  },
};

describe("mcp api", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  describe("loadMCPConfig", () => {
    test("returns MCP config on success", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify(MOCK_MCP_CONFIG), { status: 200 }),
      );

      const { loadMCPConfig } = await import("@/core/mcp/api");
      const result = await loadMCPConfig();

      expect(result.mcp_servers).toBeDefined();
      expect(result.mcp_servers["test-server"]?.enabled).toBe(true);
      expect(result.mcp_servers["test-server"]?.type).toBe("stdio");
      expect(fetcher).toHaveBeenCalledWith(
        "http://localhost:8000/api/mcp/config",
      );
    });

    test("throws MCPConfigRequestError with backend detail on failure", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify({ detail: "Unauthorized" }), {
          status: 401,
          statusText: "Unauthorized",
        }),
      );

      const { loadMCPConfig, MCPConfigRequestError } = await import(
        "@/core/mcp/api"
      );
      const error = await loadMCPConfig().then(
        () => null,
        (e: unknown) => e,
      );

      // The backend's `detail` is surfaced as the error message.
      expect(error).toBeInstanceOf(MCPConfigRequestError);
      expect((error as Error).message).toBe("Unauthorized");
      expect((error as { status: number }).status).toBe(401);
    });
  });

  describe("updateMCPConfig", () => {
    test("sends PUT request with config body", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify(MOCK_MCP_CONFIG), { status: 200 }),
      );

      const { updateMCPConfig } = await import("@/core/mcp/api");
      const result = await updateMCPConfig(MOCK_MCP_CONFIG);

      expect(fetcher).toHaveBeenCalledWith(
        "http://localhost:8000/api/mcp/config",
        expect.objectContaining({
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(MOCK_MCP_CONFIG),
        }),
      );
      expect(result.mcp_servers["test-server"]?.enabled).toBe(true);
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
        "@/core/mcp/api"
      );
      const error = await updateMCPConfig(MOCK_MCP_CONFIG).then(
        () => null,
        (e: unknown) => e,
      );

      // The backend's `detail` is surfaced as the error message.
      expect(error).toBeInstanceOf(MCPConfigRequestError);
      expect((error as Error).message).toBe("Bad request");
      expect((error as { status: number }).status).toBe(400);
    });
  });
});
