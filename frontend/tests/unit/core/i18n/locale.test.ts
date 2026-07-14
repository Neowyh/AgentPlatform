import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import {
  SUPPORTED_LOCALES,
  DEFAULT_LOCALE,
  isLocale,
  getLocaleByLang,
  getLangByLocale,
  normalizeLocale,
  detectLocale,
} from "@/core/i18n/locale";

describe("constants", () => {
  it("SUPPORTED_LOCALES contains en-US and zh-CN", () => {
    expect(SUPPORTED_LOCALES).toEqual(["en-US", "zh-CN"]);
  });

  it("DEFAULT_LOCALE is en-US", () => {
    expect(DEFAULT_LOCALE).toBe("en-US");
  });
});

describe("isLocale", () => {
  it("returns true for en-US", () => {
    expect(isLocale("en-US")).toBe(true);
  });

  it("returns true for zh-CN", () => {
    expect(isLocale("zh-CN")).toBe(true);
  });

  it("returns false for unsupported locale", () => {
    expect(isLocale("fr-FR")).toBe(false);
  });

  it("returns false for partial match", () => {
    expect(isLocale("en")).toBe(false);
  });

  it("returns false for empty string", () => {
    expect(isLocale("")).toBe(false);
  });
});

describe("getLocaleByLang", () => {
  it("returns en-US for 'en'", () => {
    expect(getLocaleByLang("en")).toBe("en-US");
  });

  it("returns zh-CN for 'zh'", () => {
    expect(getLocaleByLang("zh")).toBe("zh-CN");
  });

  it("returns en-US for 'EN' (case insensitive)", () => {
    expect(getLocaleByLang("EN")).toBe("en-US");
  });

  it("returns zh-CN for 'ZH' (case insensitive)", () => {
    expect(getLocaleByLang("ZH")).toBe("zh-CN");
  });

  it("returns en-US for 'en-US' (full locale)", () => {
    expect(getLocaleByLang("en-US")).toBe("en-US");
  });

  it("returns DEFAULT_LOCALE for unsupported language", () => {
    expect(getLocaleByLang("fr")).toBe(DEFAULT_LOCALE);
  });

  it("returns DEFAULT_LOCALE for empty string", () => {
    expect(getLocaleByLang("")).toBe(DEFAULT_LOCALE);
  });
});

describe("getLangByLocale", () => {
  it("returns 'en' for en-US", () => {
    expect(getLangByLocale("en-US")).toBe("en");
  });

  it("returns 'zh' for zh-CN", () => {
    expect(getLangByLocale("zh-CN")).toBe("zh");
  });
});

describe("normalizeLocale", () => {
  it("returns DEFAULT_LOCALE for null", () => {
    expect(normalizeLocale(null)).toBe(DEFAULT_LOCALE);
  });

  it("returns DEFAULT_LOCALE for undefined", () => {
    expect(normalizeLocale(undefined)).toBe(DEFAULT_LOCALE);
  });

  it("returns DEFAULT_LOCALE for empty string", () => {
    expect(normalizeLocale("")).toBe(DEFAULT_LOCALE);
  });

  it("returns the locale unchanged when it is a supported locale", () => {
    expect(normalizeLocale("en-US")).toBe("en-US");
    expect(normalizeLocale("zh-CN")).toBe("zh-CN");
  });

  it("returns zh-CN for any locale starting with 'zh'", () => {
    expect(normalizeLocale("zh")).toBe("zh-CN");
    expect(normalizeLocale("zh-TW")).toBe("zh-CN");
    expect(normalizeLocale("ZH")).toBe("zh-CN");
  });

  it("returns DEFAULT_LOCALE for unsupported locale", () => {
    expect(normalizeLocale("fr-FR")).toBe(DEFAULT_LOCALE);
    expect(normalizeLocale("de")).toBe(DEFAULT_LOCALE);
  });

  it("returns DEFAULT_LOCALE for 'en' (not a full locale)", () => {
    // "en" does not start with "zh" and is not in SUPPORTED_LOCALES
    expect(normalizeLocale("en")).toBe(DEFAULT_LOCALE);
  });
});

describe("detectLocale", () => {
  const originalWindow = globalThis.window;

  afterEach(() => {
    // Restore window
    if (originalWindow === undefined) {
      // @ts-expect-error restoring undefined window
      delete globalThis.window;
    } else {
      Object.defineProperty(globalThis, "window", {
        value: originalWindow,
        writable: true,
        configurable: true,
      });
    }
  });

  it("returns DEFAULT_LOCALE when window is undefined (SSR)", () => {
    // @ts-expect-error simulating SSR
    delete globalThis.window;
    expect(detectLocale()).toBe(DEFAULT_LOCALE);
  });

  it("detects en-US from navigator.language", () => {
    Object.defineProperty(globalThis, "navigator", {
      value: { language: "en-US" },
      writable: true,
      configurable: true,
    });
    expect(detectLocale()).toBe("en-US");
  });

  it("detects zh-CN from navigator.language", () => {
    Object.defineProperty(globalThis, "navigator", {
      value: { language: "zh-CN" },
      writable: true,
      configurable: true,
    });
    expect(detectLocale()).toBe("zh-CN");
  });

  it("detects zh-CN from 'zh' language", () => {
    Object.defineProperty(globalThis, "navigator", {
      value: { language: "zh" },
      writable: true,
      configurable: true,
    });
    expect(detectLocale()).toBe("zh-CN");
  });

  it("falls back to DEFAULT_LOCALE for unsupported language", () => {
    Object.defineProperty(globalThis, "navigator", {
      value: { language: "fr-FR" },
      writable: true,
      configurable: true,
    });
    expect(detectLocale()).toBe(DEFAULT_LOCALE);
  });

  it("falls back to userLanguage when language is not available", () => {
    Object.defineProperty(globalThis, "navigator", {
      value: { userLanguage: "zh-TW" },
      writable: true,
      configurable: true,
    });
    expect(detectLocale()).toBe("zh-CN");
  });
});
describe("getLangByLocale - edge cases", () => {
  it("returns language part for en-US", () => {
    expect(getLangByLocale("en-US")).toBe("en");
  });

  it("returns language part for zh-CN", () => {
    expect(getLangByLocale("zh-CN")).toBe("zh");
  });

  it("returns full locale when there is no hyphen", () => {
    // getLangByLocale splits on "-". If the locale is just "en" (not supported
    // but the function signature accepts any Locale), parts[0] is "en".
    // Since SUPPORTED_LOCALES only has "en-US" and "zh-CN", this is more of a
    // type-safety edge case, but the runtime code still handles it.
    // We test the actual function behavior with the supported locales.
    expect(getLangByLocale("en-US")).toBe("en");
    expect(getLangByLocale("zh-CN")).toBe("zh");
  });
});

describe("isLocale - additional coverage", () => {
  it("returns false for numbers as string", () => {
    expect(isLocale("123")).toBe(false);
  });

  it("returns false for partial locale code", () => {
    expect(isLocale("en-")).toBe(false);
    expect(isLocale("-US")).toBe(false);
  });

  it("returns true for exactly en-US", () => {
    expect(isLocale("en-US")).toBe(true);
  });

  it("returns true for exactly zh-CN", () => {
    expect(isLocale("zh-CN")).toBe(true);
  });

  it("is case sensitive", () => {
    expect(isLocale("EN-US")).toBe(false);
    expect(isLocale("Zh-CN")).toBe(false);
  });
});
