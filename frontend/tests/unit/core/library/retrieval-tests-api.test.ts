import { afterEach, describe, expect, test, vi } from "vitest";

const { mockFetch } = vi.hoisted(() => ({ mockFetch: vi.fn() }));

vi.mock("@/core/api/fetcher", () => ({ fetch: mockFetch }));
vi.mock("@/core/config", () => ({
  getBackendBaseURL: () => "http://localhost:8000",
}));

import {
  getRetrievalTest,
  listRetrievalTests,
  runRetrievalTest,
} from "@/core/library/api";

function response(body: unknown, ok = true) {
  return { ok, json: vi.fn().mockResolvedValue(body) };
}

describe("retrieval test API facade", () => {
  afterEach(() => vi.resetAllMocks());

  test("runs a retrieval test with camelCase input mapped to snake_case", async () => {
    mockFetch.mockResolvedValueOnce(response({ id: "test-1" }));
    await expect(
      runRetrievalTest("kb-1", { revisionId: "rev-1", query: "q", topK: 5 }),
    ).resolves.toEqual({ id: "test-1" });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/resources/kb-1/retrieval-tests",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ revision_id: "rev-1", query: "q", top_k: 5 }),
      },
    );
  });

  test("omits top_k when the caller keeps the default", async () => {
    mockFetch.mockResolvedValueOnce(response({ id: "test-2" }));
    await runRetrievalTest("kb-1", { revisionId: "rev-1", query: "q" });
    const init = mockFetch.mock.calls[0]?.[1] as { body: string } | undefined;
    expect(JSON.parse(init?.body ?? "{}")).toEqual({
      revision_id: "rev-1",
      query: "q",
    });
  });

  test("lists archived retrieval tests", async () => {
    mockFetch.mockResolvedValueOnce(
      response({ items: [{ id: "t1" }], total: 1 }),
    );
    await expect(listRetrievalTests("kb-1")).resolves.toEqual([{ id: "t1" }]);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/resources/kb-1/retrieval-tests?limit=50",
    );
  });

  test("loads one archived test record", async () => {
    mockFetch.mockResolvedValueOnce(response({ id: "t1", items: [] }));
    await expect(getRetrievalTest("kb-1", "t1")).resolves.toEqual({
      id: "t1",
      items: [],
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/resources/kb-1/retrieval-tests/t1",
    );
  });

  test("propagates safe-state failures as errors", async () => {
    mockFetch.mockResolvedValueOnce(
      response({ detail: { code: "retrieval_test_unavailable" } }, false),
    );
    await expect(
      runRetrievalTest("kb-1", { revisionId: "rev-1", query: "q" }),
    ).rejects.toThrow();
  });
});
