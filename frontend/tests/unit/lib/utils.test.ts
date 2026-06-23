import { describe, expect, test } from "vitest";

import {
  cn,
  externalLinkClass,
  externalLinkClassNoUnderline,
} from "@/lib/utils";

describe("cn", () => {
  test("merges single class", () => {
    expect(cn("foo")).toBe("foo");
  });

  test("merges multiple classes", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  test("deduplicates tailwind classes", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
  });

  test("handles conditional classes", () => {
    expect(cn("base", false && "hidden", "extra")).toBe("base extra");
  });

  test("handles undefined and null", () => {
    expect(cn("base", undefined, null)).toBe("base");
  });

  test("handles empty input", () => {
    expect(cn()).toBe("");
  });
});

describe("externalLinkClass", () => {
  test("is a non-empty string", () => {
    expect(typeof externalLinkClass).toBe("string");
    expect(externalLinkClass.length).toBeGreaterThan(0);
  });

  test("contains underline class", () => {
    expect(externalLinkClass).toContain("underline");
  });
});

describe("externalLinkClassNoUnderline", () => {
  test("is a non-empty string", () => {
    expect(typeof externalLinkClassNoUnderline).toBe("string");
    expect(externalLinkClassNoUnderline.length).toBeGreaterThan(0);
  });
});
