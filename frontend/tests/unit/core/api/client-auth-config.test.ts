import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

vi.mock("@/core/auth/types", () => ({
  buildLoginUrl: vi.fn(
    (path: string) => `/login?redirect=${encodeURIComponent(path)}`,
  ),
}));

describe("core api client", () => {
  const originalCookie = document.cookie;

  beforeEach(() => {
    vi.resetModules();
    vi.restoreAllMocks();
    document.cookie = "csrf_token=; Max-Age=0; path=/";
  });

  afterEach(() => {
    document.cookie = originalCookie;
    vi.unstubAllGlobals();
  });

  test("readCsrfCookie returns decoded token or null", async () => {
    const { readCsrfCookie } = await import("@/core/api/client");

    expect(readCsrfCookie()).toBeNull();

    document.cookie = "csrf_token=token%20value; path=/";
    expect(readCsrfCookie()).toBe("token value");
  });

  test("clientFetch includes credentials and injects CSRF for state-changing requests", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    document.cookie = "csrf_token=csrf-123; path=/";
    const { clientFetch } = await import("@/core/api/client");

    await clientFetch("/api/items", { method: "POST" });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.credentials).toBe("include");
    expect(init.headers.get("X-CSRF-Token")).toBe("csrf-123");
  });

  test("clientFetch preserves existing CSRF header and can skip 401 redirect", async () => {
    const existingHeaders = new Headers({ "X-CSRF-Token": "already-set" });
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);
    document.cookie = "csrf_token=new-token; path=/";
    const { clientFetch } = await import("@/core/api/client");

    const response = await clientFetch("/api/items", {
      method: "DELETE",
      headers: existingHeaders,
      redirectOn401: false,
    });

    expect(response.status).toBe(401);
    expect(fetchMock.mock.calls[0][1].headers.get("X-CSRF-Token")).toBe(
      "already-set",
    );
  });

  test("clientFetch redirects on 401 by default", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("window", {
      location: {
        pathname: "/workspace",
        href: "",
      },
    });
    const { clientFetch } = await import("@/core/api/client");

    await expect(clientFetch("/api/protected")).rejects.toThrow("Unauthorized");

    expect(window.location.href).toBe("/login?redirect=%2Fworkspace");
  });

  test("getCsrfHeaders returns a token header only when the cookie exists", async () => {
    const { getCsrfHeaders } = await import("@/core/api/client");

    expect(getCsrfHeaders()).toEqual({});

    document.cookie = "csrf_token=csrf-456; path=/";
    expect(getCsrfHeaders()).toEqual({ "X-CSRF-Token": "csrf-456" });
  });
});

describe("auth provider api helpers", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("fetchCurrentUser returns user for ok responses and null otherwise", async () => {
    const user = { id: "u1", email: "user@example.com", role: "user" };
    vi.doMock("@/core/api/client", () => ({
      clientFetch: vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify(user), { status: 200 }),
        )
        .mockResolvedValueOnce(new Response("Unauthorized", { status: 401 }))
        .mockResolvedValueOnce(new Response("Server error", { status: 500 })),
    }));
    const { fetchCurrentUser } = await import("@/core/api/auth-provider");

    await expect(fetchCurrentUser()).resolves.toEqual(user);
    await expect(fetchCurrentUser()).resolves.toBeNull();
    await expect(fetchCurrentUser()).resolves.toBeNull();
  });

  test("fetchCurrentUser and performLogout handle thrown fetch errors", async () => {
    vi.doMock("@/core/api/client", () => ({
      clientFetch: vi.fn().mockRejectedValue(new Error("network")),
    }));
    const { fetchCurrentUser, performLogout } =
      await import("@/core/api/auth-provider");

    await expect(fetchCurrentUser()).resolves.toBeNull();
    await expect(performLogout()).resolves.toBe(false);
  });

  test("performLogout returns true when logout request completes", async () => {
    const clientFetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.doMock("@/core/api/client", () => ({ clientFetch }));
    const { performLogout } = await import("@/core/api/auth-provider");

    await expect(performLogout()).resolves.toBe(true);
    expect(clientFetch).toHaveBeenCalledWith("/api/v1/auth/logout", {
      method: "POST",
      redirectOn401: false,
    });
  });
});

describe("api config urls", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("builds backend and langgraph URLs from explicit env values", async () => {
    vi.doMock("@/env", () => ({
      env: {
        NEXT_PUBLIC_BACKEND_BASE_URL: "/backend/",
        NEXT_PUBLIC_LANGGRAPH_BASE_URL: "https://langgraph.example.test/api",
      },
    }));
    vi.stubGlobal("window", {
      location: { origin: "https://app.example.test" },
    });
    const { getBackendBaseURL, getLangGraphBaseURL } =
      await import("@/core/api/config");

    expect(getBackendBaseURL()).toBe("https://app.example.test/backend");
    expect(getLangGraphBaseURL()).toBe("https://langgraph.example.test/api");
  });

  test("uses mock and SSR fallbacks when env values are empty", async () => {
    vi.doMock("@/env", () => ({
      env: {
        NEXT_PUBLIC_BACKEND_BASE_URL: "",
        NEXT_PUBLIC_LANGGRAPH_BASE_URL: "",
      },
    }));
    vi.stubGlobal("window", undefined);
    const { getBackendBaseURL, getLangGraphBaseURL, isDevEnvironment } =
      await import("@/core/api/config");

    expect(getBackendBaseURL()).toBe("");
    expect(getLangGraphBaseURL(true)).toBe("http://localhost:3000/mock/api");
    expect(getLangGraphBaseURL(false)).toBe(
      "http://localhost:2026/api/langgraph",
    );
    expect(isDevEnvironment()).toBe(false);
  });

  test("uses SSR origin for relative explicit backend URL", async () => {
    vi.doMock("@/env", () => ({
      env: {
        NEXT_PUBLIC_BACKEND_BASE_URL: "/backend/",
        NEXT_PUBLIC_LANGGRAPH_BASE_URL: "",
      },
    }));
    vi.stubGlobal("window", undefined);
    const { getBackendBaseURL } = await import("@/core/api/config");

    expect(getBackendBaseURL()).toBe("http://localhost:2026/backend");
  });

  test("uses window origin for mock and default LangGraph URLs", async () => {
    vi.doMock("@/env", () => ({
      env: {
        NEXT_PUBLIC_BACKEND_BASE_URL: "",
        NEXT_PUBLIC_LANGGRAPH_BASE_URL: "",
      },
    }));
    vi.stubGlobal("window", {
      location: { origin: "https://app.example.test" },
    });
    const { getLangGraphBaseURL } = await import("@/core/api/config");

    expect(getLangGraphBaseURL(true)).toBe("https://app.example.test/mock/api");
    expect(getLangGraphBaseURL()).toBe(
      "https://app.example.test/api/langgraph",
    );
  });

  test("isDevEnvironment returns false when process is unavailable", async () => {
    vi.doMock("@/env", () => ({
      env: {
        NEXT_PUBLIC_BACKEND_BASE_URL: "",
        NEXT_PUBLIC_LANGGRAPH_BASE_URL: "",
      },
    }));
    vi.stubGlobal("process", undefined);
    const { isDevEnvironment } = await import("@/core/api/config");

    expect(isDevEnvironment()).toBe(false);
  });
});
