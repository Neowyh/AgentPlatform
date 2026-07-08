import { describe, expect, test } from "vitest";

import * as i18n from "@/core/i18n";

describe("i18n index", () => {
  test("module is importable", () => {
    expect(i18n).toBeDefined();
  });

  test("exports enUS", () => {
    expect(i18n).toHaveProperty("enUS");
  });

  test("enUS is an object", () => {
    expect(typeof i18n.enUS).toBe("object");
  });

  test("exports zhCN", () => {
    expect(i18n).toHaveProperty("zhCN");
  });

  test("zhCN is an object", () => {
    expect(typeof i18n.zhCN).toBe("object");
  });

  test("exports DEFAULT_LOCALE", () => {
    expect(i18n).toHaveProperty("DEFAULT_LOCALE");
  });

  test("DEFAULT_LOCALE is en-US", () => {
    expect(i18n.DEFAULT_LOCALE).toBe("en-US");
  });

  test("exports SUPPORTED_LOCALES", () => {
    expect(i18n).toHaveProperty("SUPPORTED_LOCALES");
  });

  test("SUPPORTED_LOCALES is an array with en-US and zh-CN", () => {
    expect(Array.isArray(i18n.SUPPORTED_LOCALES)).toBe(true);
    expect(i18n.SUPPORTED_LOCALES).toEqual(["en-US", "zh-CN"]);
  });

  test("exports detectLocale", () => {
    expect(i18n).toHaveProperty("detectLocale");
  });

  test("detectLocale is a function", () => {
    expect(typeof i18n.detectLocale).toBe("function");
  });

  test("exports isLocale", () => {
    expect(i18n).toHaveProperty("isLocale");
  });

  test("isLocale is a function", () => {
    expect(typeof i18n.isLocale).toBe("function");
  });

  test("exports normalizeLocale", () => {
    expect(i18n).toHaveProperty("normalizeLocale");
  });

  test("normalizeLocale is a function", () => {
    expect(typeof i18n.normalizeLocale).toBe("function");
  });
});
