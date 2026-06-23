import { renderHook, act } from "@testing-library/react";
import { type ReactNode } from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { I18nProvider } from "@/core/i18n/context";
import { useI18n } from "@/core/i18n/hooks";
import { DEFAULT_LOCALE } from "@/core/i18n/locale";
import { translations } from "@/core/i18n/translations";

// Mock cookies module
vi.mock("@/core/i18n/cookies", () => ({
  getLocaleFromCookie: vi.fn(),
  setLocaleInCookie: vi.fn(),
}));

import { getLocaleFromCookie, setLocaleInCookie } from "@/core/i18n/cookies";

const mockGetLocaleFromCookie = vi.mocked(getLocaleFromCookie);
const mockSetLocaleInCookie = vi.mocked(setLocaleInCookie);

function createWrapper(initialLocale: "en-US" | "zh-CN" = "en-US") {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <I18nProvider initialLocale={initialLocale}>{children}</I18nProvider>
    );
  };
}

describe("useI18n", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: return null so useEffect falls through to detectLocale
    mockGetLocaleFromCookie.mockReturnValue(null);
  });

  it("returns locale, t, and changeLocale", () => {
    const { result } = renderHook(() => useI18n(), {
      wrapper: createWrapper(),
    });

    expect(result.current).toHaveProperty("locale");
    expect(result.current).toHaveProperty("t");
    expect(result.current).toHaveProperty("changeLocale");
  });

  it("returns the initial locale from provider", () => {
    const { result } = renderHook(() => useI18n(), {
      wrapper: createWrapper("en-US"),
    });

    // In jsdom, detectLocale() returns "en-US" which matches the initial
    expect(result.current.locale).toBe("en-US");
  });

  it("returns translations for the current locale", () => {
    const { result } = renderHook(() => useI18n(), {
      wrapper: createWrapper("en-US"),
    });

    // After useEffect, locale is set by detectLocale which returns "en-US" in jsdom
    expect(result.current.t).toBe(translations["en-US"]);
  });

  it("returns zh-CN translations when cookie has zh-CN", () => {
    // Mock getLocaleFromCookie to return zh-CN so useEffect doesn't override
    mockGetLocaleFromCookie.mockReturnValue("zh-CN");

    const { result } = renderHook(() => useI18n(), {
      wrapper: createWrapper("zh-CN"),
    });

    expect(result.current.locale).toBe("zh-CN");
    expect(result.current.t).toBe(translations["zh-CN"]);
  });

  it("changeLocale calls setLocaleInCookie", () => {
    // Mock cookie to return "en-US" so useEffect stabilizes the locale
    mockGetLocaleFromCookie.mockReturnValue("en-US");

    const { result } = renderHook(() => useI18n(), {
      wrapper: createWrapper("en-US"),
    });

    // Wait for useEffect to settle
    expect(result.current.locale).toBe("en-US");

    act(() => {
      result.current.changeLocale("zh-CN");
    });

    // changeLocale should call setLocaleInCookie
    expect(mockSetLocaleInCookie).toHaveBeenCalledWith("zh-CN");
  });

  it("changeLocale from zh-CN to en-US calls setLocaleInCookie", () => {
    mockGetLocaleFromCookie.mockReturnValue("zh-CN");

    const { result } = renderHook(() => useI18n(), {
      wrapper: createWrapper("zh-CN"),
    });

    expect(result.current.locale).toBe("zh-CN");

    act(() => {
      result.current.changeLocale("en-US");
    });

    expect(mockSetLocaleInCookie).toHaveBeenCalledWith("en-US");
  });

  describe("useEffect initialization", () => {
    it("uses saved locale from cookie when available", () => {
      mockGetLocaleFromCookie.mockReturnValue("zh-CN");

      const { result } = renderHook(() => useI18n(), {
        wrapper: createWrapper("en-US"),
      });

      // After useEffect runs, the locale should be updated from cookie
      expect(result.current.locale).toBe("zh-CN");
    });

    it("normalizes saved locale from cookie", () => {
      mockGetLocaleFromCookie.mockReturnValue("zh");

      const { result } = renderHook(() => useI18n(), {
        wrapper: createWrapper("en-US"),
      });

      expect(result.current.locale).toBe("zh-CN");
    });

    it("updates cookie when saved locale needs normalization", () => {
      mockGetLocaleFromCookie.mockReturnValue("zh");

      renderHook(() => useI18n(), {
        wrapper: createWrapper("en-US"),
      });

      // "zh" was normalized to "zh-CN", so cookie should be updated
      expect(mockSetLocaleInCookie).toHaveBeenCalledWith("zh-CN");
    });

    it("detects locale from browser when no cookie exists", () => {
      mockGetLocaleFromCookie.mockReturnValue(null);

      renderHook(() => useI18n(), {
        wrapper: createWrapper("en-US"),
      });

      // detectLocale() is called, and the result is set in cookie
      // In jsdom, navigator.language defaults to "en-US"
      expect(mockSetLocaleInCookie).toHaveBeenCalled();
    });

    it("does not update cookie when saved locale matches normalized", () => {
      mockGetLocaleFromCookie.mockReturnValue("en-US");

      renderHook(() => useI18n(), {
        wrapper: createWrapper("en-US"),
      });

      // "en-US" is already normalized, so no normalization update needed
      // Since cookie exists, detectLocale path is skipped entirely
      expect(mockGetLocaleFromCookie).toHaveBeenCalled();
      // setLocaleInCookie should NOT have been called because saved === normalized
      expect(mockSetLocaleInCookie).not.toHaveBeenCalled();
    });
  });
});
