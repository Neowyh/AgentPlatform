import { describe, test, expect, vi } from "vitest";

vi.mock("nextra-theme-docs", () => ({
  useMDXComponents: vi.fn(() => ({
    h1: "mock-h1",
    h2: "mock-h2",
    p: "mock-p",
  })),
}));

import { useMDXComponents } from "@/mdx-components";

describe("mdx-components", () => {
  test("useMDXComponents returns an object", () => {
    const result = useMDXComponents();
    expect(typeof result).toBe("object");
    expect(result).not.toBeNull();
  });

  test("useMDXComponents includes theme components", () => {
    const result = useMDXComponents();
    expect(result).toHaveProperty("h1");
    expect(result).toHaveProperty("h2");
    expect(result).toHaveProperty("p");
  });
});
