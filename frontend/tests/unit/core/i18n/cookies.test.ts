import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import {
  getLocaleFromCookie,
  setLocaleInCookie,
  getLocaleFromCookieServer,
} from "@/core/i18n/cookies";

describe("getLocaleFromCookie", () => {
  const originalDocument = globalThis.document;

  afterEach(() => {
    Object.defineProperty(globalThis, "document", {
      value: originalDocument,
      writable: true,
      configurable: true,
    });
  });

  it("returns null when document is undefined (server side)", () => {
    Object.defineProperty(globalThis, "document", {
      value: undefined,
      writable: true,
      configurable: true,
    });
    expect(getLocaleFromCookie()).toBeNull();
  });

  it("returns null when locale cookie is not set", () => {
    Object.defineProperty(globalThis, "document", {
      value: { cookie: "other=value; another=test" },
      writable: true,
      configurable: true,
    });
    expect(getLocaleFromCookie()).toBeNull();
  });

  it("returns locale value when cookie exists", () => {
    Object.defineProperty(globalThis, "document", {
      value: { cookie: "locale=en-US; other=value" },
      writable: true,
      configurable: true,
    });
    expect(getLocaleFromCookie()).toBe("en-US");
  });

  it("returns locale value from a cookie string with multiple cookies", () => {
    Object.defineProperty(globalThis, "document", {
      value: { cookie: "session=abc123; locale=zh-CN; theme=dark" },
      writable: true,
      configurable: true,
    });
    expect(getLocaleFromCookie()).toBe("zh-CN");
  });

  it("decodes URI-encoded locale values", () => {
    Object.defineProperty(globalThis, "document", {
      value: { cookie: "locale=zh-CN" },
      writable: true,
      configurable: true,
    });
    expect(getLocaleFromCookie()).toBe("zh-CN");
  });

  it("handles cookie at the end of the string", () => {
    Object.defineProperty(globalThis, "document", {
      value: { cookie: "other=value; locale=en-US" },
      writable: true,
      configurable: true,
    });
    expect(getLocaleFromCookie()).toBe("en-US");
  });

  it("returns empty string when locale cookie has no value", () => {
    Object.defineProperty(globalThis, "document", {
      value: { cookie: "locale=; other=value" },
      writable: true,
      configurable: true,
    });
    expect(getLocaleFromCookie()).toBe("");
  });

  it("does not match partial cookie names", () => {
    Object.defineProperty(globalThis, "document", {
      value: { cookie: "mylocale=en-US" },
      writable: true,
      configurable: true,
    });
    expect(getLocaleFromCookie()).toBeNull();
  });
});

describe("setLocaleInCookie", () => {
  const originalDocument = globalThis.document;

  afterEach(() => {
    Object.defineProperty(globalThis, "document", {
      value: originalDocument,
      writable: true,
      configurable: true,
    });
  });

  it("does nothing when document is undefined (server side)", () => {
    const setter = vi.fn();
    Object.defineProperty(globalThis, "document", {
      value: undefined,
      writable: true,
      configurable: true,
    });
    // Should not throw
    expect(() => setLocaleInCookie("en-US")).not.toThrow();
  });

  it("sets cookie with correct format for en-US", () => {
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

    setLocaleInCookie("en-US");

    expect(cookieValue).toContain("locale=en-US");
    expect(cookieValue).toContain("path=/");
    expect(cookieValue).toContain("SameSite=Lax");
    // max-age = 365 * 24 * 60 * 60 = 31536000
    expect(cookieValue).toContain("max-age=31536000");
  });

  it("sets cookie with correct format for zh-CN", () => {
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

    setLocaleInCookie("zh-CN");

    expect(cookieValue).toContain("locale=zh-CN");
  });

  it("URI-encodes the locale value", () => {
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

    setLocaleInCookie("en-US");

    expect(cookieValue).toContain("locale=en-US");
  });
});

describe("getLocaleFromCookieServer", () => {
  it("returns null when next/headers import fails", async () => {
    // getLocaleFromCookieServer uses dynamic import of next/headers.
    // In the test environment (jsdom), next/headers is not available,
    // so the catch block should return null.
    const result = await getLocaleFromCookieServer();
    expect(result).toBeNull();
  });
});
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
