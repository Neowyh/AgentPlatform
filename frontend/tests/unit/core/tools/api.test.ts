import { afterEach, describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("@/core/api/fetcher", () => ({
  fetch: vi.fn(),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => "http://localhost:8000"),
}));

vi.mock("@/core/api/errors", () => ({
  extractError: vi.fn(async (res: Response, action: string) => {
    throw new Error(`${action}: ${res.statusText}`);
  }),
}));

import { extractError } from "@/core/api/errors";
import { fetch as mockFetch } from "@/core/api/fetcher";
import { listTools, getToolDetail, testTool } from "@/core/tools/api";

const mockedFetch = vi.mocked(mockFetch);
const mockedExtractError = vi.mocked(extractError);

describe("tools API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("listTools sends GET request", async () => {
    const mockTools = { tools: [], total: 0 };
    mockedFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockTools),
    } as Response);

    const result = await listTools();

    expect(mockedFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/tools"),
    );
    expect(result).toEqual(mockTools);
  });

  it("listTools sends query params when provided", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ tools: [], total: 0 }),
    } as Response);

    await listTools({ group: "web", search: "search" });

    expect(mockedFetch).toHaveBeenCalledWith(
      expect.stringContaining("group=web"),
    );
  });

  it("listTools with only group param", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ tools: [], total: 0 }),
    } as Response);

    await listTools({ group: "mcp" });

    expect(mockedFetch).toHaveBeenCalledWith(
      expect.stringContaining("group=mcp"),
    );
  });

  it("listTools with only search param", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ tools: [], total: 0 }),
    } as Response);

    await listTools({ search: "query" });

    expect(mockedFetch).toHaveBeenCalledWith(
      expect.stringContaining("search=query"),
    );
  });

  it("getToolDetail sends GET request", async () => {
    const mockTool = { name: "web_search", description: "Search the web" };
    mockedFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockTool),
    } as Response);

    const result = await getToolDetail("web_search");

    expect(mockedFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/tools/web_search"),
    );
    expect(result).toEqual(mockTool);
  });

  it("testTool sends POST with params", async () => {
    const mockResult = { success: true, output: "Test completed" };
    mockedFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResult),
    } as Response);

    const result = await testTool("web_search", { query: "test" });

    expect(mockedFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/tools/web_search/test"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ params: { query: "test" } }),
      }),
    );
    expect(result).toEqual(mockResult);
  });

  it("getToolDetail throws on non-ok response", async () => {
    mockedFetch.mockResolvedValue({
      ok: false,
      statusText: "Not Found",
      json: () => Promise.resolve({}),
    } as Response);

    await expect(getToolDetail("nonexistent")).rejects.toThrow();
    expect(mockedExtractError).toHaveBeenCalled();
  });

  it("testTool throws on non-ok response", async () => {
    mockedFetch.mockResolvedValue({
      ok: false,
      statusText: "Internal Server Error",
      json: () => Promise.resolve({ detail: "Test failed" }),
    } as Response);

    await expect(testTool("broken_tool", { input: "test" })).rejects.toThrow();
    expect(mockedExtractError).toHaveBeenCalled();
  });

  it("listTools throws on non-ok response", async () => {
    mockedFetch.mockResolvedValue({
      ok: false,
      statusText: "Forbidden",
      json: () => Promise.resolve({}),
    } as Response);

    await expect(listTools()).rejects.toThrow();
    expect(mockedExtractError).toHaveBeenCalled();
  });

  it("testTool sends correct Content-Type header", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true }),
    } as Response);

    await testTool("tool", { key: "value" });

    expect(mockedFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: { "Content-Type": "application/json" },
      }),
    );
  });

  it("listTools returns json result on success", async () => {
    const mockData = {
      tools: [{ name: "test", description: "A test tool" }],
      total: 1,
    };
    mockedFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockData),
    } as Response);

    const result = await listTools();
    expect(result).toEqual(mockData);
    expect(result.tools).toHaveLength(1);
    expect(result.total).toBe(1);
  });

  it("listTools with no params omits query string", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ tools: [], total: 0 }),
    } as Response);

    await listTools();

    // URL should not have a query string when no params
    expect(mockedFetch).toHaveBeenCalledWith(
      expect.stringMatching(/^http:\/\/localhost:8000\/api\/tools$/),
    );
  });
});
