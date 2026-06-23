import { describe, expect, test } from "vitest";

import { aboutMarkdown } from "@/components/workspace/settings/about-content";

describe("aboutMarkdown", () => {
  test("is a non-empty string", () => {
    expect(typeof aboutMarkdown).toBe("string");
    expect(aboutMarkdown.length).toBeGreaterThan(0);
  });

  test("contains the iDeer heading", () => {
    expect(aboutMarkdown).toContain("# About iDeer 2.0");
  });

  test("mentions the open source philosophy", () => {
    expect(aboutMarkdown).toContain("From Open Source, Back to Open Source");
  });

  test("lists core features", () => {
    expect(aboutMarkdown).toContain("Skills & Tools");
    expect(aboutMarkdown).toContain("Sub-Agents");
    expect(aboutMarkdown).toContain("Sandbox & File System");
    expect(aboutMarkdown).toContain("Long-Term Memory");
  });

  test("mentions MIT License", () => {
    expect(aboutMarkdown).toContain("MIT License");
  });

  test("contains acknowledgments section", () => {
    expect(aboutMarkdown).toContain("Acknowledgments");
    expect(aboutMarkdown).toContain("LangChain");
    expect(aboutMarkdown).toContain("LangGraph");
    expect(aboutMarkdown).toContain("Next.js");
  });
});
