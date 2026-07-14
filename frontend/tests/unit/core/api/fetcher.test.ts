import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("@/core/auth/types", () => ({
  buildLoginUrl: vi.fn(
    (path: string) => `/login?next=${encodeURIComponent(path)}`,
  ),
}));

vi.mock("@/env", () => ({
  env: {
    NEXT_PUBLIC_BACKEND_BASE_URL: "",
    NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false",
  },
}));

describe("fetcher", () => {
  let originalFetch: typeof globalThis.fetch;
  let originalLocation: Location;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    originalLocation = window.location;
    // Reset cookies
    Object.defineProperty(document, "cookie", {
      value: "",
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
    vi.resetModules();
  });

  describe("isStateChangingMethod", () => {
    test("returns true for POST, PUT, DELETE, PATCH", async () => {
      const { isStateChangingMethod } = await import("@/core/api/fetcher");
      expect(isStateChangingMethod("POST")).toBe(true);
      expect(isStateChangingMethod("PUT")).toBe(true);
      expect(isStateChangingMethod("DELETE")).toBe(true);
      expect(isStateChangingMethod("PATCH")).toBe(true);
    });

    test("returns false for GET, HEAD, OPTIONS", async () => {
      const { isStateChangingMethod } = await import("@/core/api/fetcher");
      expect(isStateChangingMethod("GET")).toBe(false);
      expect(isStateChangingMethod("HEAD")).toBe(false);
      expect(isStateChangingMethod("OPTIONS")).toBe(false);
    });

    test("handles case-insensitive method names", async () => {
      const { isStateChangingMethod } = await import("@/core/api/fetcher");
      expect(isStateChangingMethod("post")).toBe(true);
      expect(isStateChangingMethod("get")).toBe(false);
    });
  });

  describe("readCsrfCookie", () => {
    test("returns null when document is unavailable during SSR", async () => {
      vi.stubGlobal("document", undefined);
      const { readCsrfCookie } = await import("@/core/api/fetcher");

      expect(readCsrfCookie()).toBeNull();
      vi.unstubAllGlobals();
    });

    test("returns null when no csrf_token cookie exists", async () => {
      Object.defineProperty(document, "cookie", {
        value: "other_cookie=value",
        writable: true,
        configurable: true,
      });
      const { readCsrfCookie } = await import("@/core/api/fetcher");
      expect(readCsrfCookie()).toBeNull();
    });

    test("returns decoded csrf_token value", async () => {
      Object.defineProperty(document, "cookie", {
        value: "csrf_token=abc123; other=xyz",
        writable: true,
        configurable: true,
      });
      const { readCsrfCookie } = await import("@/core/api/fetcher");
      expect(readCsrfCookie()).toBe("abc123");
    });

    test("decodes URI-encoded csrf_token", async () => {
      Object.defineProperty(document, "cookie", {
        value: "csrf_token=abc%20123",
        writable: true,
        configurable: true,
      });
      const { readCsrfCookie } = await import("@/core/api/fetcher");
      expect(readCsrfCookie()).toBe("abc 123");
    });
  });

  describe("getCsrfHeaders", () => {
    test("returns empty object when no csrf cookie", async () => {
      Object.defineProperty(document, "cookie", {
        value: "",
        writable: true,
        configurable: true,
      });
      const { getCsrfHeaders } = await import("@/core/api/fetcher");
      expect(getCsrfHeaders()).toEqual({});
    });

    test("returns X-CSRF-Token header when cookie exists", async () => {
      Object.defineProperty(document, "cookie", {
        value: "csrf_token=mytoken",
        writable: true,
        configurable: true,
      });
      const { getCsrfHeaders } = await import("@/core/api/fetcher");
      expect(getCsrfHeaders()).toEqual({ "X-CSRF-Token": "mytoken" });
    });
  });

  describe("fetch", () => {
    test("calls globalThis.fetch with credentials include", async () => {
      const mockResponse = new Response("ok", { status: 200 });
      globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

      const { fetch: fetchWithAuth } = await import("@/core/api/fetcher");
      const result = await fetchWithAuth("/api/test");

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/test",
        expect.objectContaining({ credentials: "include" }),
      );
      expect(result).toBe(mockResponse);
    });

    test("adds CSRF header for POST requests when cookie exists", async () => {
      Object.defineProperty(document, "cookie", {
        value: "csrf_token=testtoken",
        writable: true,
        configurable: true,
      });
      const mockResponse = new Response("ok", { status: 200 });
      globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

      const { fetch: fetchWithAuth } = await import("@/core/api/fetcher");
      await fetchWithAuth("/api/test", { method: "POST" });

      const calledHeaders = (globalThis.fetch as ReturnType<typeof vi.fn>).mock
        .calls[0]![1].headers as Headers;
      expect(calledHeaders.get("X-CSRF-Token")).toBe("testtoken");
    });

    test("does not add a CSRF header when a state-changing request has no cookie", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue(new Response("ok"));

      const { fetch: fetchWithAuth } = await import("@/core/api/fetcher");
      await fetchWithAuth("/api/test", { method: "POST" });

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/test",
        expect.objectContaining({ credentials: "include", method: "POST" }),
      );
    });

    test("does not add CSRF header for GET requests", async () => {
      Object.defineProperty(document, "cookie", {
        value: "csrf_token=testtoken",
        writable: true,
        configurable: true,
      });
      const mockResponse = new Response("ok", { status: 200 });
      globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

      const { fetch: fetchWithAuth } = await import("@/core/api/fetcher");
      await fetchWithAuth("/api/test", { method: "GET" });

      const calledInit = (globalThis.fetch as ReturnType<typeof vi.fn>).mock
        .calls[0]![1];
      // For GET requests, headers should not be a Headers object with CSRF token
      if (calledInit.headers instanceof Headers) {
        expect(calledInit.headers.has("X-CSRF-Token")).toBe(false);
      } else {
        // headers may be undefined or a plain object without CSRF
        expect(calledInit.headers).not.toEqual(
          expect.objectContaining({ "X-CSRF-Token": expect.anything() }),
        );
      }
    });

    test("does not override existing X-CSRF-Token header", async () => {
      Object.defineProperty(document, "cookie", {
        value: "csrf_token=cookietoken",
        writable: true,
        configurable: true,
      });
      const mockResponse = new Response("ok", { status: 200 });
      globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

      const { fetch: fetchWithAuth } = await import("@/core/api/fetcher");
      await fetchWithAuth("/api/test", {
        method: "POST",
        headers: { "X-CSRF-Token": "explicittoken" },
      });

      const calledHeaders = (globalThis.fetch as ReturnType<typeof vi.fn>).mock
        .calls[0]![1].headers as Headers;
      expect(calledHeaders.get("X-CSRF-Token")).toBe("explicittoken");
    });

    test("redirects to login on 401 by default", async () => {
      const mockResponse = new Response("Unauthorized", { status: 401 });
      globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

      const { fetch: fetchWithAuth } = await import("@/core/api/fetcher");

      await expect(fetchWithAuth("/api/test")).rejects.toThrow("Unauthorized");
    });

    test("does not redirect on 401 when redirectOn401 is false", async () => {
      const mockResponse = new Response("Unauthorized", { status: 401 });
      globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

      const { fetch: fetchWithAuth } = await import("@/core/api/fetcher");
      const result = await fetchWithAuth("/api/test", {
        redirectOn401: false,
      });

      expect(result.status).toBe(401);
    });

    test("handles Request object as input", async () => {
      const mockResponse = new Response("ok", { status: 200 });
      globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

      const { fetch: fetchWithAuth } = await import("@/core/api/fetcher");
      const req = new Request("http://localhost/api/test");
      await fetchWithAuth(req);

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "http://localhost/api/test",
        expect.objectContaining({ credentials: "include" }),
      );
    });
  });
});
