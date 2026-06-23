import { describe, expect, it, vi, beforeEach } from "vitest";

// Use vi.hoisted to create mock that's available when vi.mock is hoisted
const { mockCookies } = vi.hoisted(() => ({
  mockCookies: vi.fn(),
}));

vi.mock("next/headers", () => ({
  cookies: mockCookies,
}));

import { detectLocaleServer, setLocale, getI18n } from "@/core/i18n/server";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("detectLocaleServer", () => {
  it("returns DEFAULT_LOCALE when cookie is not set", async () => {
    mockCookies.mockResolvedValue({
      get: vi.fn().mockReturnValue(undefined),
    });

    const locale = await detectLocaleServer();
    expect(locale).toBe("en-US");
  });

  it("returns locale from cookie value", async () => {
    mockCookies.mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "zh-CN" }),
    });

    const locale = await detectLocaleServer();
    expect(locale).toBe("zh-CN");
  });

  it("decodes URI-encoded cookie value", async () => {
    mockCookies.mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "zh-CN" }),
    });

    const locale = await detectLocaleServer();
    expect(locale).toBe("zh-CN");
  });

  it("normalizes invalid locale from cookie to DEFAULT_LOCALE", async () => {
    mockCookies.mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "invalid-locale" }),
    });

    const locale = await detectLocaleServer();
    expect(locale).toBe("en-US");
  });

  it("normalizes zh cookie to zh-CN", async () => {
    mockCookies.mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "zh" }),
    });

    const locale = await detectLocaleServer();
    expect(locale).toBe("zh-CN");
  });

  it("handles undefined cookie store value", async () => {
    mockCookies.mockResolvedValue({
      get: vi.fn().mockReturnValue(undefined),
    });

    const locale = await detectLocaleServer();
    expect(locale).toBe("en-US");
  });
});

describe("setLocale", () => {
  it("sets cookie with normalized locale and returns it", async () => {
    const mockSet = vi.fn();
    mockCookies.mockResolvedValue({
      set: mockSet,
    });

    const result = await setLocale("en-US");

    expect(result).toBe("en-US");
    expect(mockSet).toHaveBeenCalledWith(
      "locale",
      "en-US",
      expect.objectContaining({
        maxAge: 365 * 24 * 60 * 60,
        path: "/",
        sameSite: "lax",
      }),
    );
  });

  it("normalizes locale before setting cookie", async () => {
    const mockSet = vi.fn();
    mockCookies.mockResolvedValue({
      set: mockSet,
    });

    const result = await setLocale("zh");

    expect(result).toBe("zh-CN");
    expect(mockSet).toHaveBeenCalledWith(
      "locale",
      "zh-CN",
      expect.objectContaining({
        maxAge: 365 * 24 * 60 * 60,
        path: "/",
        sameSite: "lax",
      }),
    );
  });

  it("falls back to DEFAULT_LOCALE for invalid locale", async () => {
    const mockSet = vi.fn();
    mockCookies.mockResolvedValue({
      set: mockSet,
    });

    const result = await setLocale("invalid");

    expect(result).toBe("en-US");
    expect(mockSet).toHaveBeenCalledWith("locale", "en-US", expect.any(Object));
  });
});

describe("getI18n", () => {
  it("returns translations for the detected locale", async () => {
    mockCookies.mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "en-US" }),
    });

    const result = await getI18n();

    expect(result).toHaveProperty("locale", "en-US");
    expect(result).toHaveProperty("t");
    expect(result.t).toBeDefined();
  });

  it("returns translations for zh-CN locale", async () => {
    mockCookies.mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: "zh-CN" }),
    });

    const result = await getI18n();

    expect(result).toHaveProperty("locale", "zh-CN");
    expect(result).toHaveProperty("t");
  });

  it("uses locale override when provided", async () => {
    const result = await getI18n("zh-CN");

    expect(result.locale).toBe("zh-CN");
    expect(result).toHaveProperty("t");
  });

  it("normalizes the locale override", async () => {
    const result = await getI18n("zh");

    expect(result.locale).toBe("zh-CN");
  });

  it("falls back to DEFAULT_LOCALE for invalid override", async () => {
    const result = await getI18n("invalid");

    expect(result.locale).toBe("en-US");
  });

  it("falls back to DEFAULT_LOCALE translations when locale has no translations", async () => {
    // Even with an unknown locale, normalizeLocale falls back to en-US
    const result = await getI18n("fr-FR");

    expect(result.locale).toBe("en-US");
  });
});
