import { describe, expect, test } from "vitest";

import { extractTitleFromMarkdown } from "@/core/utils/markdown";

describe("extractTitleFromMarkdown", () => {
  test("extracts title from markdown starting with # ", () => {
    const result = extractTitleFromMarkdown("# Hello World\nSome content");
    expect(result).toBe("Hello World");
  });

  test("returns undefined for markdown not starting with # ", () => {
    const result = extractTitleFromMarkdown("No title here");
    expect(result).toBeUndefined();
  });

  test("returns undefined for empty string", () => {
    const result = extractTitleFromMarkdown("");
    expect(result).toBeUndefined();
  });

  test("extracts title with extra whitespace", () => {
    const result = extractTitleFromMarkdown("#   Spaced Title   \nContent");
    expect(result).toBe("Spaced Title");
  });

  test("handles title-only markdown (no newline)", () => {
    const result = extractTitleFromMarkdown("# Only Title");
    expect(result).toBe("Only Title");
  });

  test("returns undefined for ## not starting at position 0", () => {
    const result = extractTitleFromMarkdown("## Not at start");
    expect(result).toBeUndefined();
  });

  test("returns undefined for markdown that starts with text then has heading", () => {
    const result = extractTitleFromMarkdown(
      "Some preamble\n# Title\nMore content",
    );
    expect(result).toBeUndefined();
  });

  test("extracts title with special characters", () => {
    const result = extractTitleFromMarkdown("# Title with <tags> & symbols");
    expect(result).toBe("Title with <tags> & symbols");
  });

  test("handles markdown with only a heading line", () => {
    const result = extractTitleFromMarkdown("# Just a heading");
    expect(result).toBe("Just a heading");
  });
});
