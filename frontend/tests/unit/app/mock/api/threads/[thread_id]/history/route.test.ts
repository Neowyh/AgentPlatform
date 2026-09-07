import { NextRequest } from "next/server";
import { describe, test, expect, vi, beforeEach } from "vitest";

// The merged mock history route validates the thread against DEMO_THREAD_IDS
// and loads its manifest over HTTP (/demo/threads/<id>/thread.json).
vi.mock("@/core/threads/static-demo", () => ({
  DEMO_THREAD_IDS: ["test-123", "test-456", "test-789"],
}));

import { POST } from "@/app/mock/api/threads/[thread_id]/history/route";

function makeParams(threadId: string) {
  return { params: Promise.resolve({ thread_id: threadId }) };
}

function mockFetchResponses(byId: Record<string, object | null>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: URL | string) => {
      const url = String(input);
      const match = /\/demo\/threads\/([^/]+)\/thread\.json/.exec(url);
      const id = match ? decodeURIComponent(match[1]!) : "";
      const body = byId[id];
      if (body === null || body === undefined) {
        return Promise.resolve(new Response("not found", { status: 404 }));
      }
      return Promise.resolve(
        new Response(JSON.stringify(body), { status: 200 }),
      );
    }),
  );
}

function makeRequest(threadId: string) {
  return new NextRequest(
    `http://localhost/api/threads/${threadId}/history`,
    { method: "POST" },
  );
}

describe("mock history route", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  test("POST returns single-element array when no history field", async () => {
    mockFetchResponses({
      "test-123": { thread_id: "test-123", title: "Test Thread" },
    });

    const response = await POST(makeRequest("test-123"), makeParams("test-123"));
    const data = await response.json();

    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBe(1);
    expect(data[0].thread_id).toBe("test-123");
  });

  test("POST returns full json when history field is an array", async () => {
    const history = [
      { type: "human", content: "Hello" },
      { type: "ai", content: "Hi there" },
    ];
    mockFetchResponses({
      "test-456": { thread_id: "test-456", history },
    });

    const response = await POST(makeRequest("test-456"), makeParams("test-456"));
    const data = await response.json();

    // When history is an array, the route returns the full json object
    expect(data).toHaveProperty("thread_id", "test-456");
    expect(data.history).toEqual(history);
  });

  test("POST returns full json when history is an empty array", async () => {
    mockFetchResponses({
      "test-789": { thread_id: "test-789", history: [] },
    });

    const response = await POST(makeRequest("test-789"), makeParams("test-789"));
    const data = await response.json();

    // history: [] is an array, so the route returns the full json object
    expect(data).toHaveProperty("thread_id", "test-789");
    expect(data).toHaveProperty("history");
  });

  test("reads thread.json from the demo path for the requested thread", async () => {
    const fetchMock = vi.fn((input: URL | string) => {
      void String(input);
      return Promise.resolve(
        new Response(JSON.stringify({ thread_id: "test-123" }), {
          status: 200,
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    await POST(makeRequest("test-123"), makeParams("test-123"));

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(String(fetchMock.mock.calls[0]![0])).toContain(
      "/demo/threads/test-123/thread.json",
    );
  });

  test("returns 404 for threads outside DEMO_THREAD_IDS", async () => {
    const response = await POST(
      makeRequest("unknown-thread"),
      makeParams("unknown-thread"),
    );

    expect(response.status).toBe(404);
  });

  test("returns 404 when the manifest cannot be loaded", async () => {
    mockFetchResponses({ "test-123": null });

    const response = await POST(makeRequest("test-123"), makeParams("test-123"));

    expect(response.status).toBe(404);
  });

  test("returns Response with JSON content type", async () => {
    mockFetchResponses({ "test-123": { thread_id: "test-123" } });

    const response = await POST(makeRequest("test-123"), makeParams("test-123"));

    expect(response.headers.get("content-type")).toContain("application/json");
  });
});
