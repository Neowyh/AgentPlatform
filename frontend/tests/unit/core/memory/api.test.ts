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

const MOCK_MEMORY = {
  version: "1.0",
  lastUpdated: "2026-01-01",
  user: {
    workContext: { summary: "work", updatedAt: "2026-01-01" },
    personalContext: { summary: "personal", updatedAt: "2026-01-01" },
    topOfMind: { summary: "mind", updatedAt: "2026-01-01" },
  },
  history: {
    recentMonths: { summary: "recent", updatedAt: "2026-01-01" },
    earlierContext: { summary: "earlier", updatedAt: "2026-01-01" },
    longTermBackground: { summary: "long", updatedAt: "2026-01-01" },
  },
  facts: [
    {
      id: "f1",
      content: "test fact",
      category: "test",
      confidence: 0.9,
      createdAt: "2026-01-01",
      source: "user",
    },
  ],
};

describe("memory api", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  describe("loadMemory", () => {
    test("returns memory data on success", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify(MOCK_MEMORY), { status: 200 }),
      );

      const { loadMemory } = await import("@/core/memory/api");
      const result = await loadMemory();

      expect(result.version).toBe("1.0");
      expect(result.facts).toHaveLength(1);
      expect(fetcher).toHaveBeenCalledWith("http://localhost:8000/api/memory");
    });

    test("calls extractError on failure", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      const errorResponse = new Response(
        JSON.stringify({ detail: "Server error" }),
        { status: 500, statusText: "Internal Server Error" },
      );
      vi.mocked(fetcher).mockResolvedValue(errorResponse);

      const { extractError } = await import("@/core/api/errors");
      vi.mocked(extractError).mockRejectedValue(new Error("Server error"));

      const { loadMemory } = await import("@/core/memory/api");
      await expect(loadMemory()).rejects.toThrow("Server error");

      expect(extractError).toHaveBeenCalledWith(
        errorResponse,
        "Failed to fetch memory",
      );
    });
  });

  describe("clearMemory", () => {
    test("sends DELETE request", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify(MOCK_MEMORY), { status: 200 }),
      );

      const { clearMemory } = await import("@/core/memory/api");
      await clearMemory();

      expect(fetcher).toHaveBeenCalledWith(
        "http://localhost:8000/api/memory",
        expect.objectContaining({ method: "DELETE" }),
      );
    });

    test("calls extractError on failure", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      const errorResponse = new Response(
        JSON.stringify({ detail: "Failed to clear" }),
        { status: 500, statusText: "Internal Server Error" },
      );
      vi.mocked(fetcher).mockResolvedValue(errorResponse);

      const { extractError } = await import("@/core/api/errors");
      vi.mocked(extractError).mockRejectedValue(new Error("Failed to clear"));

      const { clearMemory } = await import("@/core/memory/api");
      await expect(clearMemory()).rejects.toThrow("Failed to clear");

      expect(extractError).toHaveBeenCalledWith(
        errorResponse,
        "Failed to clear memory",
      );
    });
  });

  describe("deleteMemoryFact", () => {
    test("sends DELETE request with encoded fact ID", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify(MOCK_MEMORY), { status: 200 }),
      );

      const { deleteMemoryFact } = await import("@/core/memory/api");
      await deleteMemoryFact("fact/with/slash");

      expect(fetcher).toHaveBeenCalledWith(
        "http://localhost:8000/api/memory/facts/fact%2Fwith%2Fslash",
        expect.objectContaining({ method: "DELETE" }),
      );
    });

    test("calls extractError on failure", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      const errorResponse = new Response(
        JSON.stringify({ detail: "Not found" }),
        { status: 404, statusText: "Not Found" },
      );
      vi.mocked(fetcher).mockResolvedValue(errorResponse);

      const { extractError } = await import("@/core/api/errors");
      vi.mocked(extractError).mockRejectedValue(new Error("Not found"));

      const { deleteMemoryFact } = await import("@/core/memory/api");
      await expect(deleteMemoryFact("f1")).rejects.toThrow("Not found");
    });
  });

  describe("exportMemory", () => {
    test("fetches export endpoint", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify(MOCK_MEMORY), { status: 200 }),
      );

      const { exportMemory } = await import("@/core/memory/api");
      await exportMemory();

      expect(fetcher).toHaveBeenCalledWith(
        "http://localhost:8000/api/memory/export",
      );
    });

    test("calls extractError on failure", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      const errorResponse = new Response(
        JSON.stringify({ detail: "Export failed" }),
        { status: 500, statusText: "Internal Server Error" },
      );
      vi.mocked(fetcher).mockResolvedValue(errorResponse);

      const { extractError } = await import("@/core/api/errors");
      vi.mocked(extractError).mockRejectedValue(new Error("Export failed"));

      const { exportMemory } = await import("@/core/memory/api");
      await expect(exportMemory()).rejects.toThrow("Export failed");

      expect(extractError).toHaveBeenCalledWith(
        errorResponse,
        "Failed to export memory",
      );
    });
  });

  describe("importMemory", () => {
    test("sends POST with memory data", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify(MOCK_MEMORY), { status: 200 }),
      );

      const { importMemory } = await import("@/core/memory/api");
      await importMemory(MOCK_MEMORY);

      expect(fetcher).toHaveBeenCalledWith(
        "http://localhost:8000/api/memory/import",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(MOCK_MEMORY),
        }),
      );
    });

    test("calls extractError on failure", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      const errorResponse = new Response(
        JSON.stringify({ detail: "Import invalid" }),
        { status: 400, statusText: "Bad Request" },
      );
      vi.mocked(fetcher).mockResolvedValue(errorResponse);

      const { extractError } = await import("@/core/api/errors");
      vi.mocked(extractError).mockRejectedValue(new Error("Import invalid"));

      const { importMemory } = await import("@/core/memory/api");
      await expect(importMemory(MOCK_MEMORY)).rejects.toThrow("Import invalid");

      expect(extractError).toHaveBeenCalledWith(
        errorResponse,
        "Failed to import memory",
      );
    });
  });

  describe("createMemoryFact", () => {
    test("sends POST with fact input", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify(MOCK_MEMORY), { status: 200 }),
      );

      const { createMemoryFact } = await import("@/core/memory/api");
      const input = { content: "new fact", category: "test", confidence: 0.8 };
      await createMemoryFact(input);

      expect(fetcher).toHaveBeenCalledWith(
        "http://localhost:8000/api/memory/facts",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(input),
        }),
      );
    });

    test("calls extractError on failure", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      const errorResponse = new Response(
        JSON.stringify({ detail: "Validation error" }),
        { status: 422, statusText: "Unprocessable Entity" },
      );
      vi.mocked(fetcher).mockResolvedValue(errorResponse);

      const { extractError } = await import("@/core/api/errors");
      vi.mocked(extractError).mockRejectedValue(new Error("Validation error"));

      const { createMemoryFact } = await import("@/core/memory/api");
      await expect(
        createMemoryFact({ content: "bad", category: "", confidence: -1 }),
      ).rejects.toThrow("Validation error");

      expect(extractError).toHaveBeenCalledWith(
        errorResponse,
        "Failed to create memory fact",
      );
    });
  });

  describe("updateMemoryFact", () => {
    test("sends PATCH with fact ID and input", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify(MOCK_MEMORY), { status: 200 }),
      );

      const { updateMemoryFact } = await import("@/core/memory/api");
      const input = { content: "updated fact" };
      await updateMemoryFact("f1", input);

      expect(fetcher).toHaveBeenCalledWith(
        "http://localhost:8000/api/memory/facts/f1",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify(input),
        }),
      );
    });

    test("calls extractError on failure", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      const errorResponse = new Response(
        JSON.stringify({ detail: "Not found" }),
        { status: 404, statusText: "Not Found" },
      );
      vi.mocked(fetcher).mockResolvedValue(errorResponse);

      const { extractError } = await import("@/core/api/errors");
      vi.mocked(extractError).mockRejectedValue(new Error("Not found"));

      const { updateMemoryFact } = await import("@/core/memory/api");
      await expect(
        updateMemoryFact("missing-id", { content: "updated" }),
      ).rejects.toThrow("Not found");

      expect(extractError).toHaveBeenCalledWith(
        errorResponse,
        "Failed to update memory fact",
      );
    });
  });
});
