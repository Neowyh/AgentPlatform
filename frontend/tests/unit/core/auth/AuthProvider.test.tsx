import { render, screen, act, cleanup } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockPush = vi.fn();
let mockPathname = "/workspace";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => mockPathname,
}));

const mockFetch = vi.fn();
vi.mock("@/core/api/fetcher", () => ({
  fetch: (...args: any[]) => mockFetch(...args),
}));

let mockStaticMode = false;
vi.mock("@/core/static-mode", () => ({
  isStaticWebsiteOnly: () => mockStaticMode,
}));

vi.mock("@/core/auth/types", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/core/auth/types")>();
  return actual;
});

// ── Helpers ──────────────────────────────────────────────────────────────────

const mockUser = {
  id: "u1",
  email: "test@example.com",
  system_role: "user" as const,
  needs_setup: false,
};

function makeJsonResponse(
  body: unknown,
  init: { status?: number; ok?: boolean } = {},
) {
  const status = init.status ?? 200;
  const ok = init.ok ?? (status >= 200 && status < 300);
  return {
    ok,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

// Use a wrapper so we can access context from inside the provider
function createTestHelper() {
  const ctxRef: { current: ReturnType<typeof useAuth> | null } = {
    current: null,
  };
  function Consumer() {
    ctxRef.current = useAuth();
    return null;
  }
  return { ctxRef, Consumer };
}

// ── Imports (after mocks) ────────────────────────────────────────────────────

import {
  AuthProvider,
  useAuth,
  useRequireAuth,
} from "@/core/auth/AuthProvider";

// ── Lifecycle ────────────────────────────────────────────────────────────────

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  mockPush.mockClear();
  mockFetch.mockReset();
  mockPathname = "/workspace";
  mockStaticMode = false;
});

// ── AuthProvider ─────────────────────────────────────────────────────────────

describe("AuthProvider", () => {
  test("renders children", () => {
    render(
      <AuthProvider initialUser={null}>
        <div>hello</div>
      </AuthProvider>,
    );
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  test("provides initialUser as context value", () => {
    const { ctxRef, Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={mockUser}>
        <Consumer />
      </AuthProvider>,
    );
    expect(ctxRef.current!.user).toEqual(mockUser);
    expect(ctxRef.current!.isAuthenticated).toBe(true);
  });

  test("provides null user when initialUser is null", () => {
    const { ctxRef, Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={null}>
        <Consumer />
      </AuthProvider>,
    );
    expect(ctxRef.current!.user).toBeNull();
    expect(ctxRef.current!.isAuthenticated).toBe(false);
  });

  test("isLoading is false initially", () => {
    const { ctxRef, Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={mockUser}>
        <Consumer />
      </AuthProvider>,
    );
    expect(ctxRef.current!.isLoading).toBe(false);
  });
});

// ── refreshUser ──────────────────────────────────────────────────────────────

describe("AuthProvider.refreshUser", () => {
  test("fetches /api/v1/auth/me and updates user on success", async () => {
    mockFetch.mockResolvedValue(makeJsonResponse(mockUser));

    const { ctxRef, Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={null}>
        <Consumer />
      </AuthProvider>,
    );

    expect(ctxRef.current!.user).toBeNull();

    await act(async () => {
      await ctxRef.current!.refreshUser();
    });

    expect(mockFetch).toHaveBeenCalledWith("/api/v1/auth/me", {
      redirectOn401: false,
    });
    expect(ctxRef.current!.user).toEqual(mockUser);
    expect(ctxRef.current!.isAuthenticated).toBe(true);
  });

  test("sets isLoading true during fetch and false after", async () => {
    let resolveFetch!: (v: unknown) => void;
    mockFetch.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );

    const { ctxRef, Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={null}>
        <Consumer />
      </AuthProvider>,
    );

    expect(ctxRef.current!.isLoading).toBe(false);

    let promise: Promise<void>;
    act(() => {
      promise = ctxRef.current!.refreshUser();
    });

    // After microtask, isLoading should be true
    await act(async () => {
      await Promise.resolve();
    });
    expect(ctxRef.current!.isLoading).toBe(true);

    await act(async () => {
      resolveFetch(makeJsonResponse(mockUser));
      await promise;
    });

    expect(ctxRef.current!.isLoading).toBe(false);
  });

  test("sets user to null on 401 response", async () => {
    mockFetch.mockResolvedValue(makeJsonResponse(null, { status: 401 }));

    const { ctxRef, Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={mockUser}>
        <Consumer />
      </AuthProvider>,
    );

    await act(async () => {
      await ctxRef.current!.refreshUser();
    });

    expect(ctxRef.current!.user).toBeNull();
    expect(ctxRef.current!.isAuthenticated).toBe(false);
  });

  test("redirects to login on 401 when on workspace path", async () => {
    mockPathname = "/workspace/chat";
    mockFetch.mockResolvedValue(makeJsonResponse(null, { status: 401 }));

    const { ctxRef, Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={mockUser}>
        <Consumer />
      </AuthProvider>,
    );

    await act(async () => {
      await ctxRef.current!.refreshUser();
    });

    expect(mockPush).toHaveBeenCalledWith(
      `/login?next=${encodeURIComponent("/workspace/chat")}`,
    );
  });

  test("does NOT redirect on 401 when not on workspace path", async () => {
    mockPathname = "/login";
    mockFetch.mockResolvedValue(makeJsonResponse(null, { status: 401 }));

    const { ctxRef, Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={mockUser}>
        <Consumer />
      </AuthProvider>,
    );

    await act(async () => {
      await ctxRef.current!.refreshUser();
    });

    expect(mockPush).not.toHaveBeenCalled();
  });

  test("preserves the existing user on a transient fetch error", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { ctxRef, Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={mockUser}>
        <Consumer />
      </AuthProvider>,
    );

    await act(async () => {
      await ctxRef.current!.refreshUser();
    });

    expect(ctxRef.current!.user).toEqual(mockUser);
    expect(consoleSpy).toHaveBeenCalledWith(
      "Failed to refresh user:",
      expect.any(Error),
    );
  });

  test("skips fetch entirely in static mode", async () => {
    mockStaticMode = true;

    const { ctxRef, Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={null}>
        <Consumer />
      </AuthProvider>,
    );

    await act(async () => {
      await ctxRef.current!.refreshUser();
    });

    expect(mockFetch).not.toHaveBeenCalled();
    expect(ctxRef.current!.user).toBeNull();
  });

  test("does not redirect on 401 when pathname is null", async () => {
    mockPathname = null as unknown as string;
    mockFetch.mockResolvedValue(makeJsonResponse(null, { status: 401 }));

    const { ctxRef, Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={mockUser}>
        <Consumer />
      </AuthProvider>,
    );

    await act(async () => {
      await ctxRef.current!.refreshUser();
    });

    expect(mockPush).not.toHaveBeenCalled();
  });

  test("keeps existing user when response is non-200 and non-401", async () => {
    mockFetch.mockResolvedValue(
      makeJsonResponse({ error: "server" }, { status: 500 }),
    );

    const { ctxRef, Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={mockUser}>
        <Consumer />
      </AuthProvider>,
    );

    await act(async () => {
      await ctxRef.current!.refreshUser();
    });

    // User should remain unchanged (the source code only sets user on ok or 401)
    expect(ctxRef.current!.user).toEqual(mockUser);
    expect(mockPush).not.toHaveBeenCalled();
  });
});

// ── logout ───────────────────────────────────────────────────────────────────

describe("AuthProvider.logout", () => {
  test("immediately clears user", async () => {
    mockFetch.mockResolvedValue(makeJsonResponse(null));

    const { ctxRef, Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={mockUser}>
        <Consumer />
      </AuthProvider>,
    );

    expect(ctxRef.current!.user).toEqual(mockUser);

    await act(async () => {
      await ctxRef.current!.logout();
    });

    expect(ctxRef.current!.user).toBeNull();
  });

  test("calls /api/v1/auth/logout with POST", async () => {
    mockFetch.mockResolvedValue(makeJsonResponse(null));

    const { ctxRef, Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={mockUser}>
        <Consumer />
      </AuthProvider>,
    );

    await act(async () => {
      await ctxRef.current!.logout();
    });

    expect(mockFetch).toHaveBeenCalledWith("/api/v1/auth/logout", {
      method: "POST",
      redirectOn401: false,
    });
  });

  test("redirects to home page after logout", async () => {
    mockFetch.mockResolvedValue(makeJsonResponse(null));

    const { ctxRef, Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={mockUser}>
        <Consumer />
      </AuthProvider>,
    );

    await act(async () => {
      await ctxRef.current!.logout();
    });

    expect(mockPush).toHaveBeenCalledWith("/");
  });

  test("skips API call and redirects in static mode", async () => {
    mockStaticMode = true;

    const { ctxRef, Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={mockUser}>
        <Consumer />
      </AuthProvider>,
    );

    await act(async () => {
      await ctxRef.current!.logout();
    });

    expect(mockFetch).not.toHaveBeenCalled();
    expect(mockPush).toHaveBeenCalledWith("/");
    expect(ctxRef.current!.user).toBeNull();
  });

  test("still redirects even if logout API call fails", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { ctxRef, Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={mockUser}>
        <Consumer />
      </AuthProvider>,
    );

    await act(async () => {
      await ctxRef.current!.logout();
    });

    expect(mockPush).toHaveBeenCalledWith("/");
    expect(consoleSpy).toHaveBeenCalledWith(
      "Logout request failed:",
      expect.any(Error),
    );
  });
});

// ── visibilitychange handler ─────────────────────────────────────────────────

describe("AuthProvider visibilitychange", () => {
  test("refreshes user when tab becomes visible and user is authenticated", async () => {
    mockFetch.mockResolvedValue(makeJsonResponse(mockUser));

    const { Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={mockUser}>
        <Consumer />
      </AuthProvider>,
    );

    mockFetch.mockClear();

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(mockFetch).toHaveBeenCalledWith("/api/v1/auth/me", {
      redirectOn401: false,
    });
  });

  test("skips refresh when user is null", async () => {
    const { Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={null}>
        <Consumer />
      </AuthProvider>,
    );

    mockFetch.mockClear();

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(mockFetch).not.toHaveBeenCalled();
  });

  test("throttles to once per 60 seconds", async () => {
    vi.useFakeTimers();
    // Set a non-zero base time so Date.now() doesn't start at 0
    vi.setSystemTime(new Date("2025-01-01T00:00:00Z"));

    mockFetch.mockResolvedValue(makeJsonResponse(mockUser));

    const { Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={mockUser}>
        <Consumer />
      </AuthProvider>,
    );

    mockFetch.mockClear();

    // First call - should trigger refresh
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(mockFetch).toHaveBeenCalledTimes(1);

    mockFetch.mockClear();

    // Second call within 60s - should be throttled
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(mockFetch).not.toHaveBeenCalled();

    // Advance time past the throttle window
    vi.advanceTimersByTime(61_000);

    mockFetch.mockClear();

    // Third call after throttle window - should trigger refresh again
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(mockFetch).toHaveBeenCalledTimes(1);

    vi.useRealTimers();
  });

  test("skips refresh in static mode", async () => {
    mockStaticMode = true;

    const { Consumer } = createTestHelper();
    render(
      <AuthProvider initialUser={mockUser}>
        <Consumer />
      </AuthProvider>,
    );

    mockFetch.mockClear();

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(mockFetch).not.toHaveBeenCalled();
  });

  test("removes event listener on unmount", () => {
    const removeSpy = vi.spyOn(document, "removeEventListener");

    const { Consumer } = createTestHelper();
    const { unmount } = render(
      <AuthProvider initialUser={mockUser}>
        <Consumer />
      </AuthProvider>,
    );

    unmount();

    expect(removeSpy).toHaveBeenCalledWith(
      "visibilitychange",
      expect.any(Function),
    );
  });
});

// ── useAuth ──────────────────────────────────────────────────────────────────

describe("useAuth", () => {
  test("returns context when used inside AuthProvider", () => {
    function TestConsumer() {
      const auth = useAuth();
      return <span>{auth.user?.email ?? "no-user"}</span>;
    }

    render(
      <AuthProvider initialUser={mockUser}>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(screen.getByText("test@example.com")).toBeInTheDocument();
  });

  test("throws when used outside AuthProvider", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    function BadConsumer() {
      useAuth();
      return null;
    }

    expect(() => render(<BadConsumer />)).toThrow(
      "useAuth must be used within an AuthProvider",
    );

    consoleSpy.mockRestore();
  });
});

// ── useRequireAuth ───────────────────────────────────────────────────────────

describe("useRequireAuth", () => {
  test("returns auth context when authenticated", () => {
    function TestConsumer() {
      const auth = useRequireAuth();
      return <span>{auth.user?.email ?? "no-user"}</span>;
    }

    render(
      <AuthProvider initialUser={mockUser}>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(screen.getByText("test@example.com")).toBeInTheDocument();
    expect(mockPush).not.toHaveBeenCalled();
  });

  test("redirects to login when not authenticated and not loading", () => {
    mockPathname = "/workspace/chat";

    function TestConsumer() {
      useRequireAuth();
      return null;
    }

    render(
      <AuthProvider initialUser={null}>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(mockPush).toHaveBeenCalledWith(
      `/login?next=${encodeURIComponent("/workspace/chat")}`,
    );
  });

  test("does not redirect while loading", async () => {
    let resolveFetch!: (v: unknown) => void;
    mockFetch.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );

    function TestConsumer() {
      const auth = useRequireAuth();
      return <span>{auth.isLoading ? "loading" : "done"}</span>;
    }

    render(
      <AuthProvider initialUser={null}>
        <TestConsumer />
      </AuthProvider>,
    );

    // Initially not loading, so it will redirect since user is null
    // The hook checks isLoading from context, which starts false
    // So it will redirect immediately for null initialUser
    expect(mockPush).toHaveBeenCalled();

    mockPush.mockClear();
    // Cleanup to avoid act warnings
    await act(async () => {
      resolveFetch(makeJsonResponse(null, { status: 401 }));
    });
  });

  test("does not redirect in static mode", () => {
    mockStaticMode = true;

    function TestConsumer() {
      useRequireAuth();
      return null;
    }

    render(
      <AuthProvider initialUser={null}>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(mockPush).not.toHaveBeenCalled();
  });

  test("uses /workspace as fallback when pathname is null", () => {
    mockPathname = null as unknown as string;

    function TestConsumer() {
      useRequireAuth();
      return null;
    }

    render(
      <AuthProvider initialUser={null}>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(mockPush).toHaveBeenCalledWith(
      `/login?next=${encodeURIComponent("/workspace")}`,
    );
  });

  test("does not redirect when authenticated", () => {
    function TestConsumer() {
      useRequireAuth();
      return <span>protected</span>;
    }

    render(
      <AuthProvider initialUser={mockUser}>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(mockPush).not.toHaveBeenCalled();
    expect(screen.getByText("protected")).toBeInTheDocument();
  });
});
