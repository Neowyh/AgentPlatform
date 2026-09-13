import { afterEach, describe, expect, test, vi } from "vitest";

const { mockFetch } = vi.hoisted(() => ({ mockFetch: vi.fn() }));

vi.mock("@/core/api/fetcher", () => ({ fetch: mockFetch }));
vi.mock("@/core/config", () => ({
  getBackendBaseURL: () => "http://localhost:8000",
}));

import {
  createKnowledgeBase,
  deleteKnowledgeDocument,
  listKnowledgeBases,
  listKnowledgeDocuments,
  uploadKnowledgeDocument,
} from "@/core/library/api";

function response(body: unknown, ok = true) {
  return { ok, json: vi.fn().mockResolvedValue(body) };
}

describe("KnowledgeBase API facade", () => {
  afterEach(() => vi.resetAllMocks());

  test("lists only canonical KnowledgeBase resources", async () => {
    mockFetch.mockResolvedValueOnce(
      response({
        items: [
          {
            id: "kb-1",
            type: "knowledge_base",
            slug: "research",
            display_name: "Research",
            visibility: "private",
            can_modify: true,
          },
        ],
        total: 1,
      }),
    );

    await expect(listKnowledgeBases()).resolves.toEqual([
      expect.objectContaining({ id: "kb-1", display_name: "Research" }),
    ]);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/resources?type=knowledge_base&limit=200",
    );
  });

  test("creates a private canonical KnowledgeBase without provider fields", async () => {
    mockFetch.mockResolvedValueOnce(
      response({
        id: "kb-1",
        type: "knowledge_base",
        slug: "research",
        display_name: "Research",
        visibility: "private",
        can_modify: true,
      }),
    );

    await createKnowledgeBase({ slug: "research", displayName: "Research" });

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/resources",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          type: "knowledge_base",
          slug: "research",
          display_name: "Research",
          storage_kind: "database",
        }),
      }),
    );
  });

  test("lists documents below the canonical KnowledgeBase", async () => {
    mockFetch.mockResolvedValueOnce(response({ items: [] }));

    await expect(listKnowledgeDocuments("kb/1")).resolves.toEqual([]);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/resources/kb%2F1/documents",
    );
  });

  test("uploads a document as multipart without exposing provider fields", async () => {
    mockFetch.mockResolvedValueOnce(
      response({
        id: "doc-1",
        resource_id: "kb-1",
        name: "guide.pdf",
        size: 10,
        source: "upload",
        status: "uploaded",
      }),
    );
    const file = new File(["contents"], "guide.pdf", {
      type: "application/pdf",
    });

    await uploadKnowledgeDocument("kb-1", file);

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/resources/kb-1/documents",
      expect.objectContaining({ method: "POST", body: expect.any(FormData) }),
    );
  });

  test("deletes a document through its KnowledgeBase resource", async () => {
    mockFetch.mockResolvedValueOnce(
      response({ id: "doc-1", status: "deleted" }),
    );

    await expect(deleteKnowledgeDocument("kb/1", "doc/1")).resolves.toEqual({
      id: "doc-1",
      status: "deleted",
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/resources/kb%2F1/documents/doc%2F1",
      { method: "DELETE" },
    );
  });
});
