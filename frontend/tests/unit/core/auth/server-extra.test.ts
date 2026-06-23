import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

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

describe("getServerSideUser - setup-status timeout/abort", () => {
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

  test("returns unauthenticated when setup-status fetch times out (AbortError)", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue(undefined),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    const abortError = new DOMException(
      "The operation was aborted.",
      "AbortError",
    );
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abortError));

    const { getServerSideUser } = await loadFreshServerAuth();
    const result = await getServerSideUser();

    // When setup-status times out, falls through to unauthenticated
    expect(result.tag).toBe("unauthenticated");
  });

  test("returns unauthenticated when setup-status returns non-JSON body", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue(undefined),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ some_other_field: true }),
      }),
    );

    const { getServerSideUser } = await loadFreshServerAuth();
    const result = await getServerSideUser();

    // needs_setup not present, falls through to unauthenticated
    expect(result.tag).toBe("unauthenticated");
  });

  test("returns unauthenticated when setup-status ok but body has needs_setup=undefined", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue(undefined),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ needs_setup: undefined }),
      }),
    );

    const { getServerSideUser } = await loadFreshServerAuth();
    const result = await getServerSideUser();

    expect(result.tag).toBe("unauthenticated");
  });
});

describe("getServerSideUser - /auth/me edge cases", () => {
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

  test("returns gateway_unavailable on non-401/403/ok status (e.g. 404)", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "tok_abc" }),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
      }),
    );

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { getServerSideUser } = await loadFreshServerAuth();
    const result = await getServerSideUser();

    expect(result.tag).toBe("gateway_unavailable");
    expect(consoleSpy).toHaveBeenCalledWith(
      "[SSR auth] /api/v1/auth/me responded 404",
    );
    consoleSpy.mockRestore();
  });

  test("returns gateway_unavailable on 429 status", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "tok_abc" }),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 429,
      }),
    );

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { getServerSideUser } = await loadFreshServerAuth();
    const result = await getServerSideUser();

    expect(result.tag).toBe("gateway_unavailable");
    consoleSpy.mockRestore();
  });

  test("returns authenticated when needs_setup is missing from user (defaults to false)", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "tok_abc" }),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    // Return a user without needs_setup — the zod schema defaults it to false
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            id: "user-1",
            email: "user@example.com",
            system_role: "user",
            // needs_setup is omitted — defaults to false
          }),
      }),
    );

    const { getServerSideUser } = await loadFreshServerAuth();
    const result = await getServerSideUser();

    expect(result.tag).toBe("authenticated");
    if (result.tag === "authenticated") {
      expect(result.user.needs_setup).toBe(false);
    }
  });

  test("returns gateway_unavailable when /auth/me throws with AbortError (timeout)", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "tok_abc" }),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    const abortError = new DOMException(
      "The operation was aborted.",
      "AbortError",
    );
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abortError));

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { getServerSideUser } = await loadFreshServerAuth();
    const result = await getServerSideUser();

    expect(result.tag).toBe("gateway_unavailable");
    expect(consoleSpy).toHaveBeenCalledWith(
      "[SSR auth] Failed to reach gateway:",
      abortError,
    );
    consoleSpy.mockRestore();
  });

  test("returns unauthenticated when access_token cookie has empty value", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "" }),
    } as unknown as Awaited<ReturnType<typeof cookies>>);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
      }),
    );

    const { getServerSideUser } = await loadFreshServerAuth();
    const result = await getServerSideUser();

    expect(result.tag).toBe("unauthenticated");
  });
});
