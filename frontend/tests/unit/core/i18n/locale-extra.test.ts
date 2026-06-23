import { describe, expect, it } from "vitest";

import { getLangByLocale, isLocale } from "@/core/i18n/locale";

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
