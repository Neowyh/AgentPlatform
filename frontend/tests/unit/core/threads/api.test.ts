import { beforeEach, describe, expect, test, vi } from "vitest";

const extractErrorMock = vi.fn((_res: unknown, _msg: string): never => {
  throw new Error("extractError called");
});
const fetchWithAuth = vi.fn();

vi.mock("@/core/api/errors", () => ({
  extractError: extractErrorMock,
}));

vi.mock("@/core/api/fetcher", () => ({
  fetch: fetchWithAuth,
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => "http://localhost:8000"),
}));

beforeEach(() => {
  fetchWithAuth.mockReset();
  extractErrorMock.mockReset();
  extractErrorMock.mockImplementation((_res: unknown, _msg: string): never => {
    throw new Error("extractError called");
  });
});

describe("fetchThreadTokenUsage", () => {
  test("success returns token usage data", async () => {
    fetchWithAuth.mockResolvedValue({
      ok: true,
      json: async () => ({
        thread_id: "thread-1",
        total_input_tokens: 3,
        total_output_tokens: 4,
        total_tokens: 7,
        total_runs: 1,
        by_model: { unknown: { tokens: 7, runs: 1 } },
        by_caller: {
          lead_agent: 0,
          subagent: 0,
          middleware: 0,
        },
      }),
    });

    const { fetchThreadTokenUsage } = await import("@/core/threads/api");

    const result = await fetchThreadTokenUsage("thread-1");
    expect(result).toEqual({
      thread_id: "thread-1",
      total_input_tokens: 3,
      total_output_tokens: 4,
      total_tokens: 7,
      total_runs: 1,
      by_model: { unknown: { tokens: 7, runs: 1 } },
      by_caller: {
        lead_agent: 0,
        subagent: 0,
        middleware: 0,
      },
    });
  });

  test("403 response returns null", async () => {
    fetchWithAuth.mockResolvedValue({
      ok: false,
      status: 403,
    });

    const { fetchThreadTokenUsage } = await import("@/core/threads/api");

    await expect(fetchThreadTokenUsage("thread-1")).resolves.toBeNull();
  });

  test("404 response returns null", async () => {
    fetchWithAuth.mockResolvedValue({
      ok: false,
      status: 404,
    });

    const { fetchThreadTokenUsage } = await import("@/core/threads/api");

    await expect(fetchThreadTokenUsage("thread-1")).resolves.toBeNull();
  });

  test("other error response throws via extractError", async () => {
    const errorResponse = {
      ok: false,
      status: 500,
    };
    fetchWithAuth.mockResolvedValue(errorResponse);

    const { fetchThreadTokenUsage } = await import("@/core/threads/api");

    await expect(fetchThreadTokenUsage("thread-1")).rejects.toThrow(
      "extractError called",
    );
    expect(extractErrorMock).toHaveBeenCalledWith(
      errorResponse,
      "Failed to load thread token usage",
    );
  });

  test("URL includes encoded threadId", async () => {
    fetchWithAuth.mockResolvedValue({
      ok: true,
      json: async () => ({
        thread_id: "t/1",
        total_input_tokens: 0,
        total_output_tokens: 0,
        total_tokens: 0,
        total_runs: 0,
        by_model: {},
        by_caller: { lead_agent: 0, subagent: 0, middleware: 0 },
      }),
    });

    const { fetchThreadTokenUsage } = await import("@/core/threads/api");

    await fetchThreadTokenUsage("t/1");

    expect(fetchWithAuth).toHaveBeenCalledWith(
      "http://localhost:8000/api/threads/t%2F1/token-usage",
      { method: "GET" },
    );
  });
});
