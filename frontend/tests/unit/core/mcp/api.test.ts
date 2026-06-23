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
      expect(result.mcp_servers["test-server"]!.enabled).toBe(true);
      expect(result.mcp_servers["test-server"]!.type).toBe("stdio");
      expect(fetcher).toHaveBeenCalledWith(
        "http://localhost:8000/api/mcp/config",
      );
    });

    test("calls extractError on failure", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      const errorResponse = new Response(
        JSON.stringify({ detail: "Unauthorized" }),
        { status: 401, statusText: "Unauthorized" },
      );
      vi.mocked(fetcher).mockResolvedValue(errorResponse);

      const { extractError } = await import("@/core/api/errors");
      vi.mocked(extractError).mockRejectedValue(new Error("Unauthorized"));

      const { loadMCPConfig } = await import("@/core/mcp/api");
      await expect(loadMCPConfig()).rejects.toThrow("Unauthorized");

      expect(extractError).toHaveBeenCalledWith(
        errorResponse,
        "Failed to load MCP config",
      );
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
      expect(result.mcp_servers["test-server"]!.enabled).toBe(true);
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

      const { updateMCPConfig } = await import("@/core/mcp/api");
      await expect(updateMCPConfig(MOCK_MCP_CONFIG)).rejects.toThrow(
        "Bad request",
      );

      expect(extractError).toHaveBeenCalledWith(
        errorResponse,
        "Failed to update MCP config",
      );
    });
  });
});
