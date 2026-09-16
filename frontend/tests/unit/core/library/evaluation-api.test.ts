import { afterEach, describe, expect, test, vi } from "vitest";

const { mockFetch } = vi.hoisted(() => ({ mockFetch: vi.fn() }));

vi.mock("@/core/api/fetcher", () => ({ fetch: mockFetch }));
vi.mock("@/core/config", () => ({
  getBackendBaseURL: () => "http://localhost:8000",
}));

import { startKnowledgeEvaluationComparison } from "@/core/library/api";

describe("evaluation comparison API facade", () => {
  afterEach(() => vi.resetAllMocks());

  test("sends both candidate profiles and the shared selected case set", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: vi.fn().mockResolvedValue({ id: "comparison-1" }),
    });

    await startKnowledgeEvaluationComparison("kb-1", {
      leftRevisionId: "rev-a",
      leftProfileId: "frozen",
      rightRevisionId: "rev-b",
      rightProfileId: "configured",
      topK: 5,
      caseIds: ["case-1", "case-2"],
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/resources/kb-1/evaluation-comparisons",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          left_revision_id: "rev-a",
          left_profile_id: "frozen",
          right_revision_id: "rev-b",
          right_profile_id: "configured",
          top_k: 5,
          case_ids: ["case-1", "case-2"],
        }),
      },
    );
  });
});
