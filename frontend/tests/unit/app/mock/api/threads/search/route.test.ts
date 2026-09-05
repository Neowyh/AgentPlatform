import { describe, test, expect, vi, beforeEach } from "vitest";

// The merged mock search route enumerates DEMO_THREAD_IDS from the static-demo
// module and loads each thread manifest over HTTP (/demo/threads/<id>/thread.json),
// so the tests mock that seam instead of fs.
vi.mock("@/core/threads/static-demo", () => ({
  DEMO_THREAD_IDS: ["thread-1", "thread-2", "thread-3"],
}));

import { POST } from "@/app/mock/api/threads/search/route";

function threadJson(overrides: Record<string, unknown> = {}) {
  return JSON.stringify({
    thread_id: "test-thread",
    title: "Test Thread",
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-06-01T00:00:00Z",
    ...overrides,
  });
}

function mockFetchResponses(
  byId: Record<string, { ok: boolean; body?: string }>,
) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: URL | string) => {
      const url = String(input);
      const match = /\/demo\/threads\/([^/]+)\/thread\.json/.exec(url);
      const id = decodeURIComponent(match?.[1] ?? "");
      const entry = byId[id];
      if (!entry?.ok) {
        return Promise.resolve(new Response("not found", { status: 404 }));
      }
      return Promise.resolve(new Response(entry.body ?? "{}", { status: 200 }));
    }),
  );
}

async function makeRequest(body: unknown = {}) {
  return new Request("http://localhost/api/threads/search", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("mock search route", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  test("POST returns threads array", async () => {
    mockFetchResponses({
      "thread-1": { ok: true, body: threadJson() },
      "thread-2": { ok: true, body: threadJson() },
      "thread-3": { ok: false },
    });

    const response = await POST(await makeRequest());
    const data = await response.json();

    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBe(2);
  });

  test("filters out threads whose manifest cannot be loaded", async () => {
    mockFetchResponses({
      "thread-1": { ok: true, body: threadJson() },
      "thread-2": { ok: false },
      "thread-3": { ok: false },
    });

    const response = await POST(await makeRequest());
    const data = await response.json();

    expect(data).toHaveLength(1);
    expect(data[0].thread_id).toBe("thread-1");
  });

  test("falls back to created_at when updated_at is missing", async () => {
    mockFetchResponses({
      "thread-1": {
        ok: true,
        body: threadJson({ updated_at: null, created_at: "2025-02-02T00:00:00Z" }),
      },
      "thread-2": { ok: true, body: threadJson() },
      "thread-3": { ok: false },
    });

    const response = await POST(await makeRequest());
    const data = await response.json();

    const first = data.find((t: any) => t.thread_id === "thread-1");
    expect(first.updated_at).toBe("2025-02-02T00:00:00Z");
  });

  test("applies default limit of 50", async () => {
    mockFetchResponses({
      "thread-1": { ok: true, body: threadJson() },
      "thread-2": { ok: true, body: threadJson() },
      "thread-3": { ok: true, body: threadJson() },
    });

    const response = await POST(await makeRequest());
    const data = await response.json();

    expect(data.length).toBe(3);
  });

  test("respects custom limit", async () => {
    mockFetchResponses({
      "thread-1": { ok: true, body: threadJson() },
      "thread-2": { ok: true, body: threadJson() },
      "thread-3": { ok: true, body: threadJson() },
    });

    const response = await POST(await makeRequest({ limit: 1 }));
    const data = await response.json();

    expect(data.length).toBe(1);
  });

  test("respects offset", async () => {
    mockFetchResponses({
      "thread-1": { ok: true, body: threadJson() },
      "thread-2": { ok: true, body: threadJson() },
      "thread-3": { ok: true, body: threadJson() },
    });

    const response = await POST(await makeRequest({ limit: 2, offset: 1 }));
    const data = await response.json();

    expect(data.length).toBe(2);
    expect(data.map((t: any) => t.thread_id)).toEqual([
      "thread-2",
      "thread-3",
    ]);
  });

  test("sorts by updated_at desc by default", async () => {
    mockFetchResponses({
      "thread-1": {
        ok: true,
        body: threadJson({ updated_at: "2025-01-01T00:00:00Z" }),
      },
      "thread-2": {
        ok: true,
        body: threadJson({ updated_at: "2025-06-01T00:00:00Z" }),
      },
      "thread-3": { ok: false },
    });

    const response = await POST(await makeRequest());
    const data = await response.json();

    expect(data[0].thread_id).toBe("thread-2");
    expect(data[1].thread_id).toBe("thread-1");
  });

  test("sorts by updated_at asc when specified", async () => {
    mockFetchResponses({
      "thread-1": {
        ok: true,
        body: threadJson({ updated_at: "2025-06-01T00:00:00Z" }),
      },
      "thread-2": {
        ok: true,
        body: threadJson({ updated_at: "2025-01-01T00:00:00Z" }),
      },
      "thread-3": { ok: false },
    });

    const response = await POST(
      await makeRequest({ sortOrder: "asc" }),
    );
    const data = await response.json();

    expect(data[0].thread_id).toBe("thread-2");
    expect(data[1].thread_id).toBe("thread-1");
  });

  test("sorts by created_at when specified", async () => {
    mockFetchResponses({
      "thread-1": {
        ok: true,
        body: threadJson({ created_at: "2025-01-01T00:00:00Z" }),
      },
      "thread-2": {
        ok: true,
        body: threadJson({ created_at: "2025-05-01T00:00:00Z" }),
      },
      "thread-3": { ok: false },
    });

    const response = await POST(
      await makeRequest({ sortBy: "created_at", sortOrder: "desc" }),
    );
    const data = await response.json();

    expect(data[0].thread_id).toBe("thread-2");
  });

  test("handles empty request body", async () => {
    mockFetchResponses({
      "thread-1": { ok: true, body: threadJson() },
      "thread-2": { ok: true, body: threadJson() },
      "thread-3": { ok: true, body: threadJson() },
    });

    const response = await POST(
      new Request("http://localhost/api/threads/search", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: "not-json",
      }),
    );
    const data = await response.json();

    expect(data.length).toBe(3);
  });

  test("returns empty array when no thread manifests load", async () => {
    mockFetchResponses({
      "thread-1": { ok: false },
      "thread-2": { ok: false },
      "thread-3": { ok: false },
    });

    const response = await POST(await makeRequest());
    const data = await response.json();

    expect(data).toEqual([]);
  });

  test("each thread result has thread_id field", async () => {
    mockFetchResponses({
      "thread-1": { ok: true, body: threadJson() },
      "thread-2": { ok: true, body: threadJson() },
      "thread-3": { ok: true, body: threadJson() },
    });

    const response = await POST(await makeRequest());
    const data = await response.json();

    for (const thread of data) {
      expect(typeof thread.thread_id).toBe("string");
    }
  });

  test("handles NaN limit gracefully", async () => {
    mockFetchResponses({
      "thread-1": { ok: true, body: threadJson() },
      "thread-2": { ok: true, body: threadJson() },
      "thread-3": { ok: true, body: threadJson() },
    });

    // NaN limit normalizes to NaN → rejected → default limit applies.
    const response = await POST(await makeRequest({ limit: Number.NaN }));
    const data = await response.json();

    expect(data.length).toBe(3);
  });

  test("handles negative limit gracefully", async () => {
    mockFetchResponses({
      "thread-1": { ok: true, body: threadJson() },
      "thread-2": { ok: true, body: threadJson() },
      "thread-3": { ok: true, body: threadJson() },
    });

    const response = await POST(await makeRequest({ limit: -5 }));
    const data = await response.json();

    expect(data.length).toBe(0);
  });
});
