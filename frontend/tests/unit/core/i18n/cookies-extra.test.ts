import { describe, expect, it, vi, afterEach } from "vitest";

import {
  getLocaleFromCookie,
  setLocaleInCookie,
  getLocaleFromCookieServer,
} from "@/core/i18n/cookies";

describe("getLocaleFromCookie - edge cases", () => {
  const originalDocument = globalThis.document;

  afterEach(() => {
    Object.defineProperty(globalThis, "document", {
      value: originalDocument,
      writable: true,
      configurable: true,
    });
  });

  it("handles locale cookie without = sign (malformed)", () => {
    Object.defineProperty(globalThis, "document", {
      value: { cookie: "locale-no-equals-sign; other=value" },
      writable: true,
      configurable: true,
    });
    // The cookie string "locale-no-equals-sign" splits into ["locale-no-equals-sign", undefined]
    // name would be "locale-no-equals-sign" which doesn't match "locale"
    expect(getLocaleFromCookie()).toBeNull();
  });

  it("handles single cookie with no semicolons", () => {
    Object.defineProperty(globalThis, "document", {
      value: { cookie: "locale=fr-FR" },
      writable: true,
      configurable: true,
    });
    expect(getLocaleFromCookie()).toBe("fr-FR");
  });

  it("handles cookies with spaces around semicolons", () => {
    Object.defineProperty(globalThis, "document", {
      value: { cookie: "  locale=ja-JP  ; other=val" },
      writable: true,
      configurable: true,
    });
    expect(getLocaleFromCookie()).toBe("ja-JP");
  });

  it("handles URI-encoded locale value", () => {
    Object.defineProperty(globalThis, "document", {
      value: { cookie: "locale=zh-CN" },
      writable: true,
      configurable: true,
    });
    expect(getLocaleFromCookie()).toBe("zh-CN");
  });

  it("returns null for empty cookie string", () => {
    Object.defineProperty(globalThis, "document", {
      value: { cookie: "" },
      writable: true,
      configurable: true,
    });
    expect(getLocaleFromCookie()).toBeNull();
  });
});

describe("setLocaleInCookie - edge cases", () => {
  const originalDocument = globalThis.document;

  afterEach(() => {
    Object.defineProperty(globalThis, "document", {
      value: originalDocument,
      writable: true,
      configurable: true,
    });
  });

  it("does not throw when called multiple times", () => {
    let cookieValue = "";
    Object.defineProperty(globalThis, "document", {
      value: {
        set cookie(v: string) {
          cookieValue = v;
        },
        get cookie() {
          return cookieValue;
        },
      },
      writable: true,
      configurable: true,
    });

    expect(() => {
      setLocaleInCookie("en-US");
      setLocaleInCookie("zh-CN");
      setLocaleInCookie("en-US");
    }).not.toThrow();

    // Last call wins
    expect(cookieValue).toContain("locale=en-US");
  });
});

describe("getLocaleFromCookieServer - success path", () => {
  it("returns locale value when next/headers is available", async () => {
    const mockCookies = {
      get: vi.fn().mockReturnValue({ value: "zh-CN" }),
    };

    vi.doMock("next/headers", () => ({
      cookies: vi.fn().mockResolvedValue(mockCookies),
    }));

    const { getLocaleFromCookieServer } = await import("@/core/i18n/cookies");
    const result = await getLocaleFromCookieServer();
    expect(result).toBe("zh-CN");
    expect(mockCookies.get).toHaveBeenCalledWith("locale");

    vi.doUnmock("next/headers");
  });

  it("returns null when locale cookie is not set in server", async () => {
    const mockCookies = {
      get: vi.fn().mockReturnValue(undefined),
    };

    vi.doMock("next/headers", () => ({
      cookies: vi.fn().mockResolvedValue(mockCookies),
    }));

    const { getLocaleFromCookieServer } = await import("@/core/i18n/cookies");
    const result = await getLocaleFromCookieServer();
    expect(result).toBeNull();

    vi.doUnmock("next/headers");
  });
});
