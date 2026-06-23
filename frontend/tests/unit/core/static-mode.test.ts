import { describe, expect, test, vi, afterEach } from "vitest";

describe("isStaticWebsiteOnly", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  test("returns true when env var is 'true'", async () => {
    vi.stubEnv("NEXT_PUBLIC_STATIC_WEBSITE_ONLY", "true");
    const { isStaticWebsiteOnly } = await import("@/core/static-mode");
    expect(isStaticWebsiteOnly()).toBe(true);
  });

  test("returns false when env var is 'false'", async () => {
    vi.stubEnv("NEXT_PUBLIC_STATIC_WEBSITE_ONLY", "false");
    const { isStaticWebsiteOnly } = await import("@/core/static-mode");
    expect(isStaticWebsiteOnly()).toBe(false);
  });

  test("returns false when env var is undefined", async () => {
    vi.stubEnv("NEXT_PUBLIC_STATIC_WEBSITE_ONLY", undefined);
    const { isStaticWebsiteOnly } = await import("@/core/static-mode");
    expect(isStaticWebsiteOnly()).toBe(false);
  });
});
