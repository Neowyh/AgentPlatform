import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/core/api/errors", () => ({
  extractError: vi.fn(),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => "http://localhost:8000"),
}));

const config = {
  mcp_servers: {
    server: {
      enabled: true,
      type: "stdio" as const,
      command: "node",
      args: ["server.js"],
      env: {},
      headers: {},
      description: "Server",
    },
  },
};

describe("mcp-config-manager api", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("loads MCP config from backend", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(config), { status: 200 }));

    const { loadMCPConfig } = await import("@/core/api/mcp-config-manager");

    await expect(loadMCPConfig()).resolves.toEqual(config);
    expect(fetchSpy).toHaveBeenCalledWith(
      "http://localhost:8000/api/mcp/config",
    );
  });

  test("delegates load failures to extractError", async () => {
    const response = new Response("{}", { status: 500 });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response);
    const { extractError } = await import("@/core/api/errors");
    vi.mocked(extractError).mockRejectedValue(new Error("load failed"));

    const { loadMCPConfig } = await import("@/core/api/mcp-config-manager");

    await expect(loadMCPConfig()).rejects.toThrow("load failed");
    expect(extractError).toHaveBeenCalledWith(
      response,
      "Failed to load MCP config",
    );
  });

  test("rejects empty load responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("null", { status: 200 }),
    );

    const { loadMCPConfig } = await import("@/core/api/mcp-config-manager");

    await expect(loadMCPConfig()).rejects.toThrow("empty response");
  });

  test("updates MCP config with JSON body", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(config), { status: 200 }));

    const { updateMCPConfig } = await import("@/core/api/mcp-config-manager");

    await expect(updateMCPConfig(config)).resolves.toEqual(config);
    expect(fetchSpy).toHaveBeenCalledWith(
      "http://localhost:8000/api/mcp/config",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      },
    );
  });

  test("delegates update failures to extractError", async () => {
    const response = new Response("{}", { status: 400 });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response);
    const { extractError } = await import("@/core/api/errors");
    vi.mocked(extractError).mockRejectedValue(new Error("update failed"));

    const { updateMCPConfig } = await import("@/core/api/mcp-config-manager");

    await expect(updateMCPConfig(config)).rejects.toThrow("update failed");
    expect(extractError).toHaveBeenCalledWith(
      response,
      "Failed to update MCP config",
    );
  });

  test("rejects empty update responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("null", { status: 200 }),
    );

    const { updateMCPConfig } = await import("@/core/api/mcp-config-manager");

    await expect(updateMCPConfig(config)).rejects.toThrow("empty response");
  });
});
