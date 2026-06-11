import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/core/api/fetcher", () => ({
  fetch: vi.fn(),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => ""),
}));

describe("tools API", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("listTools sends GET request", async () => {
    const { fetch: mockFetch } = await import("@/core/api/fetcher");
    const mockTools = { tools: [], total: 0 };
    (mockFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockTools),
    });

    const { listTools } = await import("@/core/tools/api");
    const result = await listTools();

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/tools"),
    );
    expect(result).toEqual(mockTools);
  });

  it("listTools sends query params when provided", async () => {
    const { fetch: mockFetch } = await import("@/core/api/fetcher");
    (mockFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ tools: [], total: 0 }),
    });

    const { listTools } = await import("@/core/tools/api");
    await listTools({ group: "web", search: "search" });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("group=web"),
    );
  });

  it("getToolDetail sends GET request", async () => {
    const { fetch: mockFetch } = await import("@/core/api/fetcher");
    const mockTool = { name: "web_search", description: "Search the web" };
    (mockFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockTool),
    });

    const { getToolDetail } = await import("@/core/tools/api");
    const result = await getToolDetail("web_search");

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/tools/web_search"),
    );
    expect(result).toEqual(mockTool);
  });

  it("testTool sends POST with params", async () => {
    const { fetch: mockFetch } = await import("@/core/api/fetcher");
    const mockResult = { success: true, output: "Test completed" };
    (mockFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResult),
    });

    const { testTool } = await import("@/core/tools/api");
    const result = await testTool("web_search", { query: "test" });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/tools/web_search/test"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ params: { query: "test" } }),
      }),
    );
    expect(result).toEqual(mockResult);
  });

  it("throws on non-ok response", async () => {
    const { fetch: mockFetch } = await import("@/core/api/fetcher");
    (mockFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      statusText: "Not Found",
      json: () => Promise.resolve({}),
    });

    const { getToolDetail } = await import("@/core/tools/api");
    await expect(getToolDetail("nonexistent")).rejects.toThrow();
  });
});
