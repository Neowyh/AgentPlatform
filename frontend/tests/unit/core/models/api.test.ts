import { describe, test, expect, vi, afterEach } from "vitest";

vi.mock("@/core/api/errors", () => ({
  extractError: vi.fn(),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => "http://localhost:8000"),
}));

vi.mock("@/core/static-mode", () => ({
  isStaticWebsiteOnly: vi.fn(() => false),
}));

vi.mock("@/env", () => ({
  env: {
    NEXT_PUBLIC_BACKEND_BASE_URL: "http://localhost:8000",
    NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false",
  },
}));

describe("loadModels", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("returns models list on success", async () => {
    const mockResponse = {
      models: [
        {
          id: "gpt-4",
          name: "gpt-4",
          model: "gpt-4",
          display_name: "GPT-4",
        },
      ],
      token_usage: { enabled: true },
    };

    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify(mockResponse), { status: 200 }),
      );

    const { loadModels } = await import("@/core/models/api");
    const result = await loadModels();

    expect(result.models).toHaveLength(1);
    expect(result.models[0]!.name).toBe("gpt-4");
    expect(result.token_usage.enabled).toBe(true);
  });

  test("returns defaults when response has missing fields", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    const { loadModels } = await import("@/core/models/api");
    const result = await loadModels();

    expect(result.models).toEqual([]);
    expect(result.token_usage).toEqual({ enabled: false });
  });

  test("throws error on non-ok response", async () => {
    const errorRes = new Response(JSON.stringify({ detail: "Server error" }), {
      status: 500,
      statusText: "Internal Server Error",
    });
    globalThis.fetch = vi.fn().mockResolvedValue(errorRes);

    const { loadModels } = await import("@/core/models/api");
    const { extractError } = await import("@/core/api/errors");
    vi.mocked(extractError).mockRejectedValue(new Error("Server error"));

    await expect(loadModels()).rejects.toThrow("Server error");
    expect(extractError).toHaveBeenCalledWith(
      errorRes,
      "Failed to load models",
    );
  });

  test("returns static response in static mode", async () => {
    // Clear any globalThis.fetch from previous tests
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn();

    // Override the hoisted mock to return true for static mode
    const { isStaticWebsiteOnly } = await import("@/core/static-mode");
    vi.mocked(isStaticWebsiteOnly).mockReturnValue(true);

    const { loadModels } = await import("@/core/models/api");
    const result = await loadModels();

    expect(result.models).toEqual([]);
    expect(result.token_usage.enabled).toBe(false);
    expect(globalThis.fetch).not.toHaveBeenCalled();

    globalThis.fetch = originalFetch;
  });
});
