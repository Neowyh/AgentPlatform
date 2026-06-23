import type { Message } from "@langchain/langgraph-sdk";
import { describe, expect, test, vi } from "vitest";

import {
  extractContentFromMessage,
  extractReasoningContentFromMessage,
  extractTextFromMessage,
  extractURLFromImageURLContent,
  hasContent,
  hasToolCalls,
  INTERNAL_MARKER_TAGS,
  isHiddenFromUIMessage,
  parseUploadedFiles,
  stripInternalMarkers,
  stripUploadedFilesTag,
} from "@/core/messages/utils";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function aiMessage(
  content: string | unknown[],
  overrides?: Partial<Message>,
): Message {
  return {
    id: "ai-1",
    type: "ai",
    content,
    ...overrides,
  } as Message;
}

function humanMessage(content: string, overrides?: Partial<Message>): Message {
  return {
    id: "human-1",
    type: "human",
    content,
    ...overrides,
  } as Message;
}

// ---------------------------------------------------------------------------
// hasContent - additional edge cases
// ---------------------------------------------------------------------------

describe("hasContent - extra edge cases", () => {
  test("returns true for AI message with content and inline think tags", () => {
    expect(hasContent(aiMessage("<think>thinking</think>actual content"))).toBe(
      true,
    );
  });

  test("returns false for AI message with only think tags and no content", () => {
    expect(hasContent(aiMessage("<think>just thinking</think>"))).toBe(false);
  });

  test("returns true for non-AI with numeric-like string content", () => {
    expect(hasContent(humanMessage("42"))).toBe(true);
  });

  test("returns false for non-string non-array content on AI message", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: 42,
    } as unknown as Message;
    expect(hasContent(msg)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// hasToolCalls - additional edge cases
// ---------------------------------------------------------------------------

describe("hasToolCalls - extra edge cases", () => {
  test("returns true with multiple tool calls", () => {
    const msg = aiMessage("", {
      tool_calls: [
        { id: "tc-1", name: "tool_a", args: {} },
        { id: "tc-2", name: "tool_b", args: {} },
      ],
    });
    expect(hasToolCalls(msg)).toBe(true);
  });

  test("returns false for tool type message (not ai)", () => {
    const msg = {
      id: "t-1",
      type: "tool",
      tool_calls: [{ id: "tc-1", name: "x", args: {} }],
    } as unknown as Message;
    expect(hasToolCalls(msg)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// isHiddenFromUIMessage - additional edge cases
// ---------------------------------------------------------------------------

describe("isHiddenFromUIMessage - extra edge cases", () => {
  test("returns true for name 'todo_reminder'", () => {
    const msg = humanMessage("remind", { name: "todo_reminder" });
    expect(isHiddenFromUIMessage(msg)).toBe(true);
  });

  test("returns true for name 'todo_completion_reminder'", () => {
    const msg = humanMessage("done", { name: "todo_completion_reminder" });
    expect(isHiddenFromUIMessage(msg)).toBe(true);
  });

  test("returns false for AI message without hidden flags", () => {
    const msg = aiMessage("visible");
    expect(isHiddenFromUIMessage(msg)).toBe(false);
  });

  test("returns true when both hide_from_ui and hidden name are set", () => {
    const msg = humanMessage("hidden", {
      additional_kwargs: { hide_from_ui: true },
      name: "summary",
    });
    expect(isHiddenFromUIMessage(msg)).toBe(true);
  });

  test("returns false for empty name string", () => {
    const msg = humanMessage("visible", { name: "" });
    expect(isHiddenFromUIMessage(msg)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// extractContentFromMessage - additional edge cases
// ---------------------------------------------------------------------------

describe("extractContentFromMessage - extra edge cases", () => {
  test("handles mixed text and image_url in array content", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: [
        { type: "text", text: "Look:" },
        { type: "image_url", image_url: { url: "http://img.png" } },
        { type: "text", text: "Nice!" },
      ],
    } as Message;
    expect(extractContentFromMessage(msg)).toBe(
      "Look:\n![image](http://img.png)\nNice!",
    );
  });

  test("strips multiple inline think tags from content", () => {
    const msg = aiMessage(
      "<think>first</think>answer <think>second thought</think>final",
    );
    expect(extractContentFromMessage(msg)).toBe("answer final");
  });

  test("handles empty string content on AI message", () => {
    expect(extractContentFromMessage(aiMessage(""))).toBe("");
  });

  test("handles image_url with string value in array", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: [{ type: "image_url", image_url: "http://example.com/pic.jpg" }],
    } as Message;
    expect(extractContentFromMessage(msg)).toBe(
      "![image](http://example.com/pic.jpg)",
    );
  });
});

// ---------------------------------------------------------------------------
// extractReasoningContentFromMessage - additional edge cases
// ---------------------------------------------------------------------------

describe("extractReasoningContentFromMessage - extra edge cases", () => {
  test("returns reasoning from nested additional_kwargs", () => {
    const msg = aiMessage("content", {
      additional_kwargs: { reasoning_content: "step-by-step reasoning" },
    });
    expect(extractReasoningContentFromMessage(msg)).toBe(
      "step-by-step reasoning",
    );
  });

  test("returns null when additional_kwargs.reasoning_content is null", () => {
    const msg = aiMessage("content", {
      additional_kwargs: { reasoning_content: null },
    });
    expect(extractReasoningContentFromMessage(msg)).toBeNull();
  });

  test("extracts reasoning from inline think tags with multiline content", () => {
    const msg = aiMessage("<think>line 1\nline 2\nline 3</think>answer here");
    expect(extractReasoningContentFromMessage(msg)).toBe(
      "line 1\nline 2\nline 3",
    );
  });

  test("returns null for tool type message", () => {
    const msg = {
      id: "t-1",
      type: "tool",
      content: "<think>reasoning</think>",
    } as unknown as Message;
    expect(extractReasoningContentFromMessage(msg)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// stripUploadedFilesTag - additional edge cases
// ---------------------------------------------------------------------------

describe("stripUploadedFilesTag - extra edge cases", () => {
  test("removes tag from beginning of content", () => {
    const content =
      "<uploaded_files>- f.txt (10)\n  Path: /f.txt\n</uploaded_files>Rest";
    expect(stripUploadedFilesTag(content)).toBe("Rest");
  });

  test("removes tag from end of content", () => {
    const content =
      "Start<uploaded_files>- f.txt (10)\n  Path: /f.txt\n</uploaded_files>";
    expect(stripUploadedFilesTag(content)).toBe("Start");
  });

  test("preserves text between two tags", () => {
    const content =
      "<uploaded_files>a</uploaded_files>middle text<uploaded_files>b</uploaded_files>";
    expect(stripUploadedFilesTag(content)).toBe("middle text");
  });

  test("handles content with only whitespace after stripping", () => {
    expect(
      stripUploadedFilesTag("  <uploaded_files>x</uploaded_files>  "),
    ).toBe("");
  });
});

// ---------------------------------------------------------------------------
// stripInternalMarkers - additional edge cases
// ---------------------------------------------------------------------------

describe("stripInternalMarkers - extra edge cases", () => {
  test("strips nested-like tags (system-reminder containing memory)", () => {
    const content =
      "before<system-reminder><memory>data</memory></system-reminder>after";
    expect(stripInternalMarkers(content)).toBe("beforeafter");
  });

  test("does not strip unknown tags", () => {
    const content = "before<unknown_tag>data</unknown_tag>after";
    expect(stripInternalMarkers(content)).toBe(
      "before<unknown_tag>data</unknown_tag>after",
    );
  });

  test("strips all four marker types in a single string", () => {
    const content =
      "<uploaded_files>u</uploaded_files><system-reminder>s</system-reminder><memory>m</memory><current_date>d</current_date>";
    expect(stripInternalMarkers(content)).toBe("");
  });

  test("handles content that is entirely a marker tag", () => {
    expect(stripInternalMarkers("<memory>remember me</memory>")).toBe("");
  });
});

// ---------------------------------------------------------------------------
// parseUploadedFiles - additional edge cases
// ---------------------------------------------------------------------------

describe("parseUploadedFiles - extra edge cases", () => {
  test("parses file with large size", () => {
    const content = `<uploaded_files>
- bigfile.zip (1073741824)
  Path: /uploads/bigfile.zip
</uploaded_files>`;
    const files = parseUploadedFiles(content);
    expect(files).toHaveLength(1);
    expect(files[0]!.size).toBe(1073741824);
    expect(files[0]!.filename).toBe("bigfile.zip");
  });

  test("parses file with spaces in filename", () => {
    const content = `<uploaded_files>
- my document file.pdf (2048)
  Path: /uploads/my document file.pdf
</uploaded_files>`;
    const files = parseUploadedFiles(content);
    expect(files).toHaveLength(1);
    expect(files[0]!.filename).toBe("my document file.pdf");
  });

  test("returns empty for non-matching uploaded_files content", () => {
    const content =
      "<uploaded_files>random text without format</uploaded_files>";
    expect(parseUploadedFiles(content)).toEqual([]);
  });

  test("handles multiple lines between file entries", () => {
    const content = `<uploaded_files>

- a.txt (10)
  Path: /a.txt

</uploaded_files>`;
    const files = parseUploadedFiles(content);
    expect(files).toHaveLength(1);
    expect(files[0]!.filename).toBe("a.txt");
  });
});

// ---------------------------------------------------------------------------
// extractTextFromMessage - additional edge cases
// ---------------------------------------------------------------------------

describe("extractTextFromMessage - extra edge cases", () => {
  test("extracts text from array with mixed types", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: [
        { type: "text", text: "hello" },
        { type: "image_url", image_url: { url: "x" } },
        { type: "text", text: "world" },
      ],
    } as Message;
    expect(extractTextFromMessage(msg)).toBe("hello\n\nworld");
  });

  test("handles AI message with think tags in string content", () => {
    expect(
      extractTextFromMessage(aiMessage("<think>analysis</think>Hello!")),
    ).toBe("Hello!");
  });

  test("returns empty string for array with no text entries", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: [{ type: "image_url", image_url: { url: "x" } }],
    } as Message;
    expect(extractTextFromMessage(msg)).toBe("");
  });
});

// ---------------------------------------------------------------------------
// extractURLFromImageURLContent - additional edge cases
// ---------------------------------------------------------------------------

describe("extractURLFromImageURLContent - extra edge cases", () => {
  test("handles empty string", () => {
    expect(extractURLFromImageURLContent("")).toBe("");
  });

  test("handles object with empty url", () => {
    expect(extractURLFromImageURLContent({ url: "" })).toBe("");
  });

  test("handles data URL", () => {
    const dataUrl = "data:image/png;base64,abc123";
    expect(extractURLFromImageURLContent(dataUrl)).toBe(dataUrl);
  });
});
