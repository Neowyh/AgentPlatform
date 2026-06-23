import type { ToolCall } from "@langchain/core/messages";
import type { AIMessage } from "@langchain/langgraph-sdk";
import { describe, expect, test } from "vitest";

import { explainLastToolCall, explainToolCall } from "@/core/tools/utils";

// ── Translation mock ─────────────────────────────────────────────────────

const t = {
  common: { thinking: "Thinking..." },
  toolCalls: {
    searchFor: (query: string) => `Searching for "${query}"`,
    viewWebPage: "Viewing web page",
    presentFiles: "Presenting files",
    writeTodos: "Writing todos",
    useTool: (name: string) => `Using ${name}`,
  },
} as Parameters<typeof explainToolCall>[1];

// ── Helpers ──────────────────────────────────────────────────────────────

function makeToolCall(
  name: string,
  args: Record<string, unknown> = {},
): ToolCall {
  return {
    id: `call_${name}_1`,
    name,
    args,
  };
}

function makeAIMessage(overrides: Partial<AIMessage> = {}): AIMessage {
  return {
    type: "ai",
    content: "",
    tool_calls: undefined,
    ...overrides,
  } as AIMessage;
}

// ── explainToolCall tests ────────────────────────────────────────────────

describe("explainToolCall", () => {
  test("explains web_search tool call", () => {
    const toolCall = makeToolCall("web_search", { query: "react hooks" });
    const result = explainToolCall(toolCall, t);
    expect(result).toBe('Searching for "react hooks"');
  });

  test("explains image_search tool call", () => {
    const toolCall = makeToolCall("image_search", { query: "cats" });
    const result = explainToolCall(toolCall, t);
    expect(result).toBe('Searching for "cats"');
  });

  test("explains web_fetch tool call", () => {
    const toolCall = makeToolCall("web_fetch", { url: "https://example.com" });
    const result = explainToolCall(toolCall, t);
    expect(result).toBe("Viewing web page");
  });

  test("explains present_files tool call", () => {
    const toolCall = makeToolCall("present_files", { filepaths: ["file.pdf"] });
    const result = explainToolCall(toolCall, t);
    expect(result).toBe("Presenting files");
  });

  test("explains write_todos tool call", () => {
    const toolCall = makeToolCall("write_todos", { todos: [] });
    const result = explainToolCall(toolCall, t);
    expect(result).toBe("Writing todos");
  });

  test("uses args.description when available for unknown tool", () => {
    const toolCall = makeToolCall("custom_tool", {
      description: "Doing something custom",
    });
    const result = explainToolCall(toolCall, t);
    expect(result).toBe("Doing something custom");
  });

  test("falls back to useTool for unknown tool without description", () => {
    const toolCall = makeToolCall("unknown_tool", {});
    const result = explainToolCall(toolCall, t);
    expect(result).toBe("Using unknown_tool");
  });

  test("falls back to useTool when description is empty string", () => {
    const toolCall = makeToolCall("some_tool", { description: "" });
    const result = explainToolCall(toolCall, t);
    expect(result).toBe("Using some_tool");
  });
});

// ── explainLastToolCall tests ────────────────────────────────────────────

describe("explainLastToolCall", () => {
  test("explains the last tool call when message has tool calls", () => {
    const message = makeAIMessage({
      tool_calls: [
        makeToolCall("web_search", { query: "first" }),
        makeToolCall("web_fetch", { url: "https://example.com" }),
      ],
    });
    const result = explainLastToolCall(message, t);
    expect(result).toBe("Viewing web page");
  });

  test("returns thinking message when message has no tool calls", () => {
    const message = makeAIMessage({ tool_calls: undefined });
    const result = explainLastToolCall(message, t);
    expect(result).toBe("Thinking...");
  });

  test("returns thinking message when tool_calls is empty array", () => {
    const message = makeAIMessage({ tool_calls: [] });
    const result = explainLastToolCall(message, t);
    expect(result).toBe("Thinking...");
  });

  test("explains single tool call", () => {
    const message = makeAIMessage({
      tool_calls: [makeToolCall("web_search", { query: "test" })],
    });
    const result = explainLastToolCall(message, t);
    expect(result).toBe('Searching for "test"');
  });
});
