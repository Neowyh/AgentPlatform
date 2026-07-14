import { afterAll, beforeEach, describe, expect, test, vi } from "vitest";

vi.hoisted(() => {
  vi.stubEnv(
    "IDEER_INTERNAL_GATEWAY_BASE_URL",
    "http://internal-gateway.test:9123",
  );
  vi.stubEnv("NEXT_PUBLIC_BACKEND_BASE_URL", "http://public-gateway.test:8123");
});

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

import { GET, DELETE } from "@/app/api/memory/route";

afterAll(() => {
  vi.unstubAllEnvs();
});

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

describe("memory API route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("GET proxies to /api/memory backend endpoint", async () => {
    const mockResponse = new Response(JSON.stringify({ messages: [] }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
    mockFetch.mockResolvedValueOnce(mockResponse);

    const request = createRequest("GET");
    await GET(request);

    expect(mockFetch).toHaveBeenCalledOnce();
    const [url, options] = mockFetch.mock.calls[0]!;
    expect(url.toString()).toBe("http://internal-gateway.test:9123/api/memory");
    expect(options.method).toBe("GET");
    expect(options.headers.get("host")).toBeNull();
    expect(options.headers.get("connection")).toBeNull();
  });

  test("GET returns response with correct status", async () => {
    const mockResponse = new Response(JSON.stringify({ ok: true }), {
      status: 200,
    });
    mockFetch.mockResolvedValueOnce(mockResponse);

    const result = await GET(createRequest("GET"));
    expect(result.status).toBe(200);
  });

  test("DELETE proxies to /api/memory backend endpoint", async () => {
    const mockResponse = new Response(JSON.stringify({ deleted: true }), {
      status: 200,
    });
    mockFetch.mockResolvedValueOnce(mockResponse);

    const request = createRequest("DELETE");
    await DELETE(request);

    const [url, options] = mockFetch.mock.calls[0]!;
    expect(url.toString()).toContain("/api/memory");
    expect(options.method).toBe("DELETE");
  });

  test("GET strips host and connection headers", async () => {
    const mockResponse = new Response("", { status: 200 });
    mockFetch.mockResolvedValueOnce(mockResponse);

    await GET(createRequest("GET"));

    const [, options] = mockFetch.mock.calls[0]!;
    expect(options.headers.get("host")).toBeNull();
    expect(options.headers.get("connection")).toBeNull();
  });

  test("DELETE strips host and connection headers", async () => {
    const mockResponse = new Response("", { status: 200 });
    mockFetch.mockResolvedValueOnce(mockResponse);

    await DELETE(createRequest("DELETE"));

    const [, options] = mockFetch.mock.calls[0]!;
    expect(options.headers.get("host")).toBeNull();
    expect(options.headers.get("connection")).toBeNull();
  });

  test("GET forwards non-GET method without body", async () => {
    const mockResponse = new Response("", { status: 200 });
    mockFetch.mockResolvedValueOnce(mockResponse);

    await GET(createRequest("GET"));

    const [, options] = mockFetch.mock.calls[0]!;
    expect(options.body).toBeUndefined();
  });
});
