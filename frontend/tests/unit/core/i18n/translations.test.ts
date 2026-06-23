import { describe, expect, it } from "vitest";

import { SUPPORTED_LOCALES } from "@/core/i18n/locale";
import { enUS } from "@/core/i18n/locales/en-US";
import { zhCN } from "@/core/i18n/locales/zh-CN";
import { translations } from "@/core/i18n/translations";

describe("translations record", () => {
  it("exports an object", () => {
    expect(translations).toBeDefined();
    expect(typeof translations).toBe("object");
  });

  it("has a key for every supported locale", () => {
    for (const locale of SUPPORTED_LOCALES) {
      expect(translations).toHaveProperty(locale);
    }
  });

  it("en-US maps to the enUS locale object", () => {
    expect(translations["en-US"]).toBe(enUS);
  });

  it("zh-CN maps to the zhCN locale object", () => {
    expect(translations["zh-CN"]).toBe(zhCN);
  });

  it("has exactly as many entries as supported locales", () => {
    expect(Object.keys(translations)).toHaveLength(SUPPORTED_LOCALES.length);
  });

  it("every locale entry has the locale section", () => {
    for (const locale of SUPPORTED_LOCALES) {
      expect(translations[locale]).toHaveProperty("locale");
      expect(translations[locale].locale).toHaveProperty("localName");
      expect(typeof translations[locale].locale.localName).toBe("string");
    }
  });

  it("en-US has common.home key", () => {
    expect(translations["en-US"].common.home).toBe("Home");
  });

  it("zh-CN has common.home key", () => {
    expect(translations["zh-CN"].common.home).toBe("首页");
  });

  it("every locale has all top-level sections", () => {
    const expectedSections = [
      "locale",
      "common",
      "home",
      "welcome",
      "clipboard",
      "inputBox",
      "sidebar",
      "agents",
      "workflows",
      "breadcrumb",
      "workspace",
      "conversation",
      "chats",
      "pages",
      "toolCalls",
      "uploads",
      "subtasks",
      "tokenUsage",
      "shortcuts",
      "settings",
    ];
    for (const locale of SUPPORTED_LOCALES) {
      for (const section of expectedSections) {
        expect(translations[locale]).toHaveProperty(section);
      }
    }
  });

  describe("locale switching", () => {
    it("different locales have different common.home values", () => {
      const values = SUPPORTED_LOCALES.map((l) => translations[l].common.home);
      const unique = new Set(values);
      expect(unique.size).toBeGreaterThan(1);
    });

    it("different locales have different welcome.greeting values", () => {
      const values = SUPPORTED_LOCALES.map(
        (l) => translations[l].welcome.greeting,
      );
      const unique = new Set(values);
      expect(unique.size).toBeGreaterThan(1);
    });

    it("both locales share the same pages.appName", () => {
      const values = SUPPORTED_LOCALES.map(
        (l) => translations[l].pages.appName,
      );
      expect(values.every((v) => v === "iDeer")).toBe(true);
    });
  });

  describe("function properties across locales", () => {
    it("both locales have workflow deleteConfirm as function", () => {
      for (const locale of SUPPORTED_LOCALES) {
        expect(typeof translations[locale].workflows.deleteConfirm).toBe(
          "function",
        );
      }
    });

    it("both locales have workflow steps as function", () => {
      for (const locale of SUPPORTED_LOCALES) {
        expect(typeof translations[locale].workflows.steps).toBe("function");
      }
    });

    it("both locales have toolCalls moreSteps as function", () => {
      for (const locale of SUPPORTED_LOCALES) {
        expect(typeof translations[locale].toolCalls.moreSteps).toBe(
          "function",
        );
      }
    });

    it("both locales have subtasks executing as function", () => {
      for (const locale of SUPPORTED_LOCALES) {
        expect(typeof translations[locale].subtasks.executing).toBe("function");
      }
    });

    it("both locales have tokenUsage subagent as function", () => {
      for (const locale of SUPPORTED_LOCALES) {
        expect(typeof translations[locale].tokenUsage.subagent).toBe(
          "function",
        );
      }
    });
  });
});
