import { afterEach, describe, expect, test, vi } from "vitest";

const { mockFetch } = vi.hoisted(() => ({ mockFetch: vi.fn() }));

vi.mock("@/core/api/fetcher", () => ({ fetch: mockFetch }));
vi.mock("@/core/config", () => ({
  getBackendBaseURL: () => "http://localhost:8000",
}));

import {
  createKnowledgeEvalCase,
  deleteKnowledgeEvalCase,
  getEvalCaseRevisionApplicability,
  getKnowledgeEvalCase,
  listKnowledgeEvalCases,
  updateKnowledgeEvalCase,
} from "@/core/library/api";

function response(body: unknown, ok = true) {
  return { ok, json: vi.fn().mockResolvedValue(body) };
}

describe("eval case API facade", () => {
  afterEach(() => vi.resetAllMocks());

  test("lists eval cases for a knowledge base", async () => {
    mockFetch.mockResolvedValueOnce(
      response({ items: [{ id: "case-1" }], total: 1 }),
    );
    await expect(listKnowledgeEvalCases("kb-1")).resolves.toEqual([
      { id: "case-1" },
    ]);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/resources/kb-1/eval-cases",
    );
  });

  test("creates an eval case without exposing provider identities", async () => {
    mockFetch.mockResolvedValueOnce(response({ id: "case-1" }));
    await expect(
      createKnowledgeEvalCase("kb-1", {
        question: "q",
        expectedDocumentIds: ["doc-1"],
        tags: ["regression"],
      }),
    ).resolves.toEqual({ id: "case-1" });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/resources/kb-1/eval-cases",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: "q",
          expected_document_ids: ["doc-1"],
          tags: ["regression"],
        }),
      },
    );
  });

  test("loads case detail with version history", async () => {
    mockFetch.mockResolvedValueOnce(
      response({ id: "case-1", versions: [{ version_no: 1 }] }),
    );
    await expect(getKnowledgeEvalCase("kb-1", "case-1")).resolves.toEqual({
      id: "case-1",
      versions: [{ version_no: 1 }],
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/resources/kb-1/eval-cases/case-1",
    );
  });

  test("patches only provided fields", async () => {
    mockFetch.mockResolvedValueOnce(response({ id: "case-1" }));
    await updateKnowledgeEvalCase("kb-1", "case-1", { tags: ["smoke"] });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/resources/kb-1/eval-cases/case-1",
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: undefined,
          expected_document_ids: undefined,
          tags: ["smoke"],
        }),
      },
    );
  });

  test("deletes a case", async () => {
    mockFetch.mockResolvedValueOnce(response(undefined));
    await expect(
      deleteKnowledgeEvalCase("kb-1", "case-1"),
    ).resolves.toBeUndefined();
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/resources/kb-1/eval-cases/case-1",
      { method: "DELETE" },
    );
  });

  test("loads revision applicability", async () => {
    mockFetch.mockResolvedValueOnce(
      response({
        revision_id: "rev-1",
        revision_no: 1,
        status: "published",
        manifest_hash: "a".repeat(64),
        items: [],
        total: 0,
      }),
    );
    await expect(
      getEvalCaseRevisionApplicability("kb-1", "rev-1"),
    ).resolves.toEqual(
      expect.objectContaining({ revision_id: "rev-1", total: 0 }),
    );
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/resources/kb-1/eval-cases/revisions/rev-1/applicability",
    );
  });

  test("surfaces backend validation errors", async () => {
    mockFetch.mockResolvedValueOnce(
      response(
        { detail: "a case requires at least one expected document" },
        false,
      ),
    );
    await expect(
      createKnowledgeEvalCase("kb-1", {
        question: "q",
        expectedDocumentIds: [],
        tags: [],
      }),
    ).rejects.toThrow(/expected document/);
  });
});
