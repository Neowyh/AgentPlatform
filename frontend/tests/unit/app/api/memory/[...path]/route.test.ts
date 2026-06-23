import { describe, test, expect, vi, beforeEach } from "vitest";

const mockFetch = vi.fn();
global.fetch = mockFetch;

vi.mock("next/server", () => ({
  NextRequest: class {},
  NextResponse: class {
    static json(data: unknown, init?: { status?: number }) {
      return { json: () => data, status: init?.status ?? 200 };
    }
  },
}));

import { GET, POST, DELETE, PATCH } from "@/app/api/memory/[...path]/route";

function createRequest(method = "GET") {
  const headers = new Headers({
    host: "localhost:3000",
    connection: "keep-alive",
    "content-length": "0",
  });
  return {
    method,
    headers,
    arrayBuffer: () => Promise.resolve(new ArrayBuffer(0)),
  } as unknown as import("next/server").NextRequest;
}

const mockParams = { params: Promise.resolve({ path: ["facts"] }) };

describe("memory catch-all API route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("GET proxies to /api/memory/facts", async () => {
    const mockResponse = new Response(JSON.stringify({ facts: [] }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
    mockFetch.mockResolvedValueOnce(mockResponse);

    await GET(createRequest("GET"), mockParams);

    expect(mockFetch).toHaveBeenCalledOnce();
    const [url, options] = mockFetch.mock.calls[0]!;
    expect(url.toString()).toContain("/api/memory/facts");
    expect(options.method).toBe("GET");
  });

  test("POST proxies to /api/memory/facts", async () => {
    const mockResponse = new Response(JSON.stringify({ ok: true }), {
      status: 200,
    });
    mockFetch.mockResolvedValueOnce(mockResponse);

    await POST(createRequest("POST"), mockParams);

    const [url, options] = mockFetch.mock.calls[0]!;
    expect(url.toString()).toContain("/api/memory/facts");
    expect(options.method).toBe("POST");
  });

  test("DELETE proxies to /api/memory/facts", async () => {
    const mockResponse = new Response(JSON.stringify({ deleted: true }), {
      status: 200,
    });
    mockFetch.mockResolvedValueOnce(mockResponse);

    await DELETE(createRequest("DELETE"), mockParams);

    const [url, options] = mockFetch.mock.calls[0]!;
    expect(url.toString()).toContain("/api/memory/facts");
    expect(options.method).toBe("DELETE");
  });

  test("PATCH proxies to /api/memory/facts", async () => {
    const mockResponse = new Response(JSON.stringify({ updated: true }), {
      status: 200,
    });
    mockFetch.mockResolvedValueOnce(mockResponse);

    await PATCH(createRequest("PATCH"), mockParams);

    const [url, options] = mockFetch.mock.calls[0]!;
    expect(url.toString()).toContain("/api/memory/facts");
    expect(options.method).toBe("PATCH");
  });

  test("strips host and connection headers", async () => {
    const mockResponse = new Response("", { status: 200 });
    mockFetch.mockResolvedValueOnce(mockResponse);

    await GET(createRequest("GET"), mockParams);

    const [, options] = mockFetch.mock.calls[0]!;
    expect(options.headers.get("host")).toBeNull();
    expect(options.headers.get("connection")).toBeNull();
  });

  test("forwards body for POST requests", async () => {
    const mockResponse = new Response("", { status: 200 });
    mockFetch.mockResolvedValueOnce(mockResponse);

    await POST(createRequest("POST"), mockParams);

    const [, options] = mockFetch.mock.calls[0]!;
    expect(options.body).toBeDefined();
  });

  test("does not forward body for GET requests", async () => {
    const mockResponse = new Response("", { status: 200 });
    mockFetch.mockResolvedValueOnce(mockResponse);

    await GET(createRequest("GET"), mockParams);

    const [, options] = mockFetch.mock.calls[0]!;
    expect(options.body).toBeUndefined();
  });

  test("joins multiple path segments", async () => {
    const mockResponse = new Response("", { status: 200 });
    mockFetch.mockResolvedValueOnce(mockResponse);

    const multiParams = {
      params: Promise.resolve({ path: ["facts", "123", "edit"] }),
    };
    await GET(createRequest("GET"), multiParams);

    const [url] = mockFetch.mock.calls[0]!;
    expect(url.toString()).toContain("/api/memory/facts/123/edit");
  });

  test("returns the backend response", async () => {
    const body = JSON.stringify({ data: "test" });
    const mockResponse = new Response(body, {
      status: 201,
      headers: { "content-type": "application/json" },
    });
    mockFetch.mockResolvedValueOnce(mockResponse);

    const result = await GET(createRequest("GET"), mockParams);
    expect(result.status).toBe(201);
  });
});
