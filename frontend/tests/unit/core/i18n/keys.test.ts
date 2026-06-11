import { describe, expect, it } from "vitest";

import { enUS } from "@/core/i18n/locales/en-US";
import { zhCN } from "@/core/i18n/locales/zh-CN";

describe("i18n translation keys", () => {
  describe("admin-related keys", () => {
    it("en-US has admin-related workspace keys", () => {
      expect(enUS.workspace).toHaveProperty("adminPanel");
      expect(enUS.workspace).toHaveProperty("userManagement");
      expect(enUS.workspace).toHaveProperty("departmentManagement");
      expect(enUS.workspace).toHaveProperty("toolManagement");
    });

    it("zh-CN has admin-related workspace keys", () => {
      expect(zhCN.workspace).toHaveProperty("adminPanel");
      expect(zhCN.workspace).toHaveProperty("userManagement");
      expect(zhCN.workspace).toHaveProperty("departmentManagement");
      expect(zhCN.workspace).toHaveProperty("toolManagement");
    });
  });

  describe("workflow-related keys", () => {
    it("en-US has workflows sidebar key", () => {
      expect(enUS.sidebar).toHaveProperty("workflows");
    });

    it("zh-CN has workflows sidebar key", () => {
      expect(zhCN.sidebar).toHaveProperty("workflows");
    });
  });

  describe("brand keys", () => {
    it("en-US uses iDeer brand in app name", () => {
      expect(enUS.pages.appName).toBe("iDeer");
    });

    it("zh-CN uses iDeer brand in app name", () => {
      expect(zhCN.pages.appName).toBe("iDeer");
    });
  });

  describe("key parity", () => {
    it("en-US and zh-CN have same top-level keys", () => {
      const enKeys = Object.keys(enUS).sort();
      const zhKeys = Object.keys(zhCN).sort();
      expect(enKeys).toEqual(zhKeys);
    });

    it("en-US and zh-CN workspace keys match", () => {
      const enKeys = Object.keys(enUS.workspace).sort();
      const zhKeys = Object.keys(zhCN.workspace).sort();
      expect(enKeys).toEqual(zhKeys);
    });

    it("en-US and zh-CN sidebar keys match", () => {
      const enKeys = Object.keys(enUS.sidebar).sort();
      const zhKeys = Object.keys(zhCN.sidebar).sort();
      expect(enKeys).toEqual(zhKeys);
    });
  });
});
