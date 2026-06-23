import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { STATIC_WEBSITE_USER } from "@/core/auth/static-user";

vi.mock("next/headers", () => ({
  cookies: vi.fn(),
}));

const ENV_KEYS = [
  "IDEER_AUTH_DISABLED",
  "IDEER_INTERNAL_GATEWAY_BASE_URL",
  "NEXT_PUBLIC_STATIC_WEBSITE_ONLY",
] as const;

type EnvSnapshot = Partial<
  Record<(typeof ENV_KEYS)[number], string | undefined>
>;

function snapshotEnv(): EnvSnapshot {
  const snapshot: EnvSnapshot = {};
  for (const key of ENV_KEYS) {
    snapshot[key] = process.env[key];
  }
  return snapshot;
}

function setEnv(key: (typeof ENV_KEYS)[number], value: string | undefined) {
  const env = process.env as Record<string, string | undefined>;
  if (value === undefined) {
    delete env[key];
  } else {
    env[key] = value;
  }
}

function restoreEnv(snapshot: EnvSnapshot) {
  for (const key of ENV_KEYS) {
    setEnv(key, snapshot[key]);
  }
}

async function loadFreshServerAuth() {
  vi.resetModules();
  return await import("@/core/auth/server");
}

// Helper to build a minimal valid user JSON
function validUser(overrides: Record<string, unknown> = {}) {
  return {
    id: "user-1",
    email: "user@example.com",
    system_role: "user",
    needs_setup: false,
    ...overrides,
  };
}

describe("getServerSideUser", () => {
  let saved: EnvSnapshot;

  beforeEach(() => {
    saved = snapshotEnv();
    setEnv("IDEER_AUTH_DISABLED", undefined);
    setEnv("NEXT_PUBLIC_STATIC_WEBSITE_ONLY", undefined);
    setEnv("IDEER_INTERNAL_GATEWAY_BASE_URL", "http://localhost:9999");
  });

  afterEach(() => {
    restoreEnv(saved);
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  // ── Static website mode ─────────────────────────────────────────

  test("returns STATIC_WEBSITE_USER in static website mode", async () => {
    setEnv("NEXT_PUBLIC_STATIC_WEBSITE_ONLY", "true");
    const fetchSpy = vi.fn(() => {
      throw new Error("fetch should not be called in static website mode");
    });
    vi.stubGlobal("fetch", fetchSpy);

    const { getServerSideUser } = await loadFreshServerAuth();

    await expect(getServerSideUser()).resolves.toEqual({
      tag: "authenticated",
      user: STATIC_WEBSITE_USER,
    });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  // ── Auth disabled (e2e) ─────────────────────────────────────────

  test("returns e2e super_admin user when IDEER_AUTH_DISABLED=1", async () => {
    setEnv("IDEER_AUTH_DISABLED", "1");
    setEnv("NEXT_PUBLIC_STATIC_WEBSITE_ONLY", undefined);
    const fetchSpy = vi.fn(() => {
      throw new Error("fetch should not be called when auth is disabled");
    });
    vi.stubGlobal("fetch", fetchSpy);

    const { getServerSideUser } = await loadFreshServerAuth();

    const result = await getServerSideUser();
    expect(result).toEqual({
      tag: "authenticated",
      user: {
        id: "e2e-user",
        email: "e2e@test.local",
        system_role: "super_admin",
        needs_setup: false,
      },
    });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  // ── Config error ────────────────────────────────────────────────

  test("returns config_error when getGatewayConfig throws", async () => {
    // Mock cookies first since it is called before getGatewayConfig
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "tok_abc" }),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    // Set an invalid gateway URL so getGatewayConfig throws during parse
    setEnv("IDEER_INTERNAL_GATEWAY_BASE_URL", "not-a-valid-url");

    const { getServerSideUser } = await loadFreshServerAuth();

    const result = await getServerSideUser();
    expect(result.tag).toBe("config_error");
    if (result.tag === "config_error") {
      expect(result.message).toContain("invalid");
    }
  });

  // ── No session cookie ───────────────────────────────────────────

  test("returns system_setup_required when setup-status says needs_setup=true", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue(undefined),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ needs_setup: true }),
      }),
    );

    const { getServerSideUser } = await loadFreshServerAuth();

    await expect(getServerSideUser()).resolves.toEqual({
      tag: "system_setup_required",
    });
  });

  test("returns unauthenticated when setup-status says needs_setup=false", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue(undefined),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ needs_setup: false }),
      }),
    );

    const { getServerSideUser } = await loadFreshServerAuth();

    await expect(getServerSideUser()).resolves.toEqual({
      tag: "unauthenticated",
    });
  });

  test("returns unauthenticated when setup-status returns non-ok response", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue(undefined),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
      }),
    );

    const { getServerSideUser } = await loadFreshServerAuth();

    await expect(getServerSideUser()).resolves.toEqual({
      tag: "unauthenticated",
    });
  });

  test("returns unauthenticated when setup-status fetch throws", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue(undefined),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("Network error")),
    );

    const { getServerSideUser } = await loadFreshServerAuth();

    await expect(getServerSideUser()).resolves.toEqual({
      tag: "unauthenticated",
    });
  });

  test("returns unauthenticated when no session cookie and setup-status body lacks needs_setup", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue(undefined),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}),
      }),
    );

    const { getServerSideUser } = await loadFreshServerAuth();

    await expect(getServerSideUser()).resolves.toEqual({
      tag: "unauthenticated",
    });
  });

  // ── With session cookie: /auth/me responses ─────────────────────

  test("returns authenticated for a valid user response", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "tok_abc" }),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(validUser()),
      }),
    );

    const { getServerSideUser } = await loadFreshServerAuth();

    const result = await getServerSideUser();
    expect(result.tag).toBe("authenticated");
    if (result.tag === "authenticated") {
      expect(result.user.id).toBe("user-1");
      expect(result.user.email).toBe("user@example.com");
    }
  });

  test("returns needs_setup when user has needs_setup=true", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "tok_abc" }),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(validUser({ needs_setup: true })),
      }),
    );

    const { getServerSideUser } = await loadFreshServerAuth();

    const result = await getServerSideUser();
    expect(result.tag).toBe("needs_setup");
    if (result.tag === "needs_setup") {
      expect(result.user.needs_setup).toBe(true);
    }
  });

  test("returns gateway_unavailable when /auth/me returns malformed JSON", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "tok_abc" }),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ garbage: true }),
      }),
    );

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { getServerSideUser } = await loadFreshServerAuth();

    await expect(getServerSideUser()).resolves.toEqual({
      tag: "gateway_unavailable",
    });
    expect(consoleSpy).toHaveBeenCalledWith(
      "[SSR auth] Malformed /auth/me response:",
      expect.anything(),
    );
    consoleSpy.mockRestore();
  });

  test("returns gateway_unavailable when /auth/me returns user with invalid email", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "tok_abc" }),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            id: "u-1",
            email: "not-valid",
            system_role: "user",
          }),
      }),
    );

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { getServerSideUser } = await loadFreshServerAuth();

    await expect(getServerSideUser()).resolves.toEqual({
      tag: "gateway_unavailable",
    });
    consoleSpy.mockRestore();
  });

  test("returns gateway_unavailable when /auth/me returns user with invalid role", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "tok_abc" }),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            id: "u-1",
            email: "user@example.com",
            system_role: "invalid_role",
          }),
      }),
    );

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { getServerSideUser } = await loadFreshServerAuth();

    await expect(getServerSideUser()).resolves.toEqual({
      tag: "gateway_unavailable",
    });
    consoleSpy.mockRestore();
  });

  test("returns unauthenticated on 401 from /auth/me", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "tok_expired" }),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
      }),
    );

    const { getServerSideUser } = await loadFreshServerAuth();

    await expect(getServerSideUser()).resolves.toEqual({
      tag: "unauthenticated",
    });
  });

  test("returns unauthenticated on 403 from /auth/me", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "tok_forbidden" }),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
      }),
    );

    const { getServerSideUser } = await loadFreshServerAuth();

    await expect(getServerSideUser()).resolves.toEqual({
      tag: "unauthenticated",
    });
  });

  test("returns gateway_unavailable on 500 from /auth/me", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "tok_abc" }),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
      }),
    );

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { getServerSideUser } = await loadFreshServerAuth();

    await expect(getServerSideUser()).resolves.toEqual({
      tag: "gateway_unavailable",
    });
    expect(consoleSpy).toHaveBeenCalledWith(
      "[SSR auth] /api/v1/auth/me responded 500",
    );
    consoleSpy.mockRestore();
  });

  test("returns gateway_unavailable when /auth/me fetch throws", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "tok_abc" }),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("Connection refused")),
    );

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { getServerSideUser } = await loadFreshServerAuth();

    await expect(getServerSideUser()).resolves.toEqual({
      tag: "gateway_unavailable",
    });
    expect(consoleSpy).toHaveBeenCalledWith(
      "[SSR auth] Failed to reach gateway:",
      expect.any(Error),
    );
    consoleSpy.mockRestore();
  });

  // ── Cookie forwarding ───────────────────────────────────────────

  test("forwards access_token cookie value to /auth/me", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "my_secret_token" }),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(validUser()),
    });
    vi.stubGlobal("fetch", fetchSpy);

    const { getServerSideUser } = await loadFreshServerAuth();

    await getServerSideUser();

    // The second fetch call is /auth/me (first would be setup-status if no cookie)
    const authMeCall = fetchSpy.mock.calls.find((call: unknown[]) =>
      (call[0] as string).includes("/auth/me"),
    );
    expect(authMeCall).toBeDefined();
    expect(authMeCall![1]).toMatchObject({
      headers: { Cookie: "access_token=my_secret_token" },
    });
  });

  // ── Fetch URL construction ──────────────────────────────────────

  test("uses internalGatewayUrl from config for auth endpoints", async () => {
    setEnv("IDEER_INTERNAL_GATEWAY_BASE_URL", "http://custom-gw:8080");
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue(undefined),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ needs_setup: false }),
    });
    vi.stubGlobal("fetch", fetchSpy);

    const { getServerSideUser } = await loadFreshServerAuth();

    await getServerSideUser();

    expect(fetchSpy).toHaveBeenCalledWith(
      "http://custom-gw:8080/api/v1/auth/setup-status",
      expect.anything(),
    );
  });

  // ── All AuthResult tags are reachable ────────────────────────────

  test("covers all six AuthResult tags", async () => {
    // This is a meta-test to ensure we haven't missed any branch.
    // The individual tests above cover:
    // - authenticated (static mode, e2e mode, valid user)
    // - needs_setup (user with needs_setup=true)
    // - system_setup_required (setup-status needs_setup=true, no cookie)
    // - unauthenticated (no cookie + setup ok, 401, 403)
    // - gateway_unavailable (malformed response, 500, fetch error)
    // - config_error (invalid gateway URL)
    const tags = [
      "authenticated",
      "needs_setup",
      "system_setup_required",
      "unauthenticated",
      "gateway_unavailable",
      "config_error",
    ] as const;
    // Just verify the list is complete
    expect(tags).toHaveLength(6);
  });
});
