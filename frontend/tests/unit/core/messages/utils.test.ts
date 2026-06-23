import type { Message } from "@langchain/langgraph-sdk";
import { describe, expect, test, vi } from "vitest";

import {
  extractContentFromMessage,
  extractPresentFilesFromMessage,
  extractReasoningContentFromMessage,
  extractTextFromMessage,
  extractURLFromImageURLContent,
  findToolCallResult,
  getAssistantTurnCopyData,
  getAssistantTurnUsageMessages,
  getMessageGroups,
  getStreamingMessageLookup,
  groupMessages,
  hasContent,
  hasPresentFiles,
  hasReasoning,
  hasSubagent,
  hasToolCalls,
  INTERNAL_MARKER_TAGS,
  isAssistantMessageGroupStreaming,
  isClarificationToolMessage,
  isHiddenFromUIMessage,
  parseUploadedFiles,
  removeReasoningContentFromMessage,
  stripInternalMarkers,
  stripUploadedFilesTag,
} from "@/core/messages/utils";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function aiMessage(content: string, overrides?: Partial<Message>): Message {
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

function toolMessage(content: string, overrides?: Partial<Message>): Message {
  return {
    id: "tool-1",
    type: "tool",
    content,
    tool_call_id: "tc-1",
    ...overrides,
  } as Message;
}

// ---------------------------------------------------------------------------
// getMessageGroups
// ---------------------------------------------------------------------------

describe("getMessageGroups", () => {
  test("returns empty array for empty input", () => {
    expect(getMessageGroups([])).toEqual([]);
  });

  test("creates a human group for human messages", () => {
    const groups = getMessageGroups([humanMessage("hi")]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.type).toBe("human");
    expect(groups[0]!.messages).toHaveLength(1);
  });

  test("creates an assistant group for AI messages with content and no tool calls", () => {
    const groups = getMessageGroups([aiMessage("hello")]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.type).toBe("assistant");
  });

  test("creates an assistant:processing group for AI messages with tool calls", () => {
    const msg = aiMessage("", {
      tool_calls: [{ id: "tc-1", name: "search", args: {} }],
    });
    const groups = getMessageGroups([msg]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.type).toBe("assistant:processing");
  });

  test("accumulates consecutive intermediate AI messages into one processing group", () => {
    const msg1 = aiMessage("", {
      id: "ai-1",
      tool_calls: [{ id: "tc-1", name: "search", args: {} }],
    });
    const msg2 = aiMessage("", {
      id: "ai-2",
      tool_calls: [{ id: "tc-2", name: "fetch", args: {} }],
    });
    const groups = getMessageGroups([msg1, msg2]);
    const processing = groups.filter((g) => g.type === "assistant:processing");
    expect(processing).toHaveLength(1);
    expect(processing[0]!.messages).toHaveLength(2);
  });

  test("creates a new processing group when separated by a human message", () => {
    const msg1 = aiMessage("", {
      id: "ai-1",
      tool_calls: [{ id: "tc-1", name: "search", args: {} }],
    });
    const msg2 = humanMessage("follow up", { id: "h-2" });
    const msg3 = aiMessage("", {
      id: "ai-2",
      tool_calls: [{ id: "tc-2", name: "fetch", args: {} }],
    });
    const groups = getMessageGroups([msg1, msg2, msg3]);
    const processing = groups.filter((g) => g.type === "assistant:processing");
    expect(processing).toHaveLength(2);
  });

  test("appends tool messages to the last open group", () => {
    const ai = aiMessage("", {
      id: "ai-1",
      tool_calls: [{ id: "tc-1", name: "search", args: {} }],
    });
    const tool = toolMessage("result", {
      id: "t-1",
      tool_call_id: "tc-1",
    });
    const groups = getMessageGroups([ai, tool]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.type).toBe("assistant:processing");
    expect(groups[0]!.messages).toHaveLength(2);
  });

  test("logs error for tool message outside a processing group", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const tool = toolMessage("orphan", { id: "t-orphan" });
    const groups = getMessageGroups([tool]);
    expect(groups).toHaveLength(0);
    expect(spy).toHaveBeenCalledOnce();
    spy.mockRestore();
  });

  test("creates assistant:clarification group for ask_clarification tool messages", () => {
    const ai = aiMessage("", {
      id: "ai-1",
      tool_calls: [{ id: "tc-1", name: "ask_clarification", args: {} }],
    });
    const tool = toolMessage("what do you mean?", {
      id: "t-1",
      tool_call_id: "tc-1",
      name: "ask_clarification",
    });
    const groups = getMessageGroups([ai, tool]);
    const clarification = groups.filter(
      (g) => g.type === "assistant:clarification",
    );
    expect(clarification).toHaveLength(1);
    // The tool message is also added to the processing group
    const processing = groups.filter((g) => g.type === "assistant:processing");
    expect(processing).toHaveLength(1);
    expect(processing[0]!.messages).toHaveLength(2);
  });

  test("creates assistant:present-files group for present_files tool calls", () => {
    const msg = aiMessage("", {
      id: "ai-1",
      tool_calls: [
        {
          id: "tc-1",
          name: "present_files",
          args: { filepaths: ["a.ts"] },
        },
      ],
    });
    const groups = getMessageGroups([msg]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.type).toBe("assistant:present-files");
  });

  test("creates assistant:subagent group for task tool calls", () => {
    const msg = aiMessage("", {
      id: "ai-1",
      tool_calls: [{ id: "tc-1", name: "task", args: {} }],
    });
    const groups = getMessageGroups([msg]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.type).toBe("assistant:subagent");
  });

  test("hides messages with hide_from_ui additional_kwargs", () => {
    const messages = [
      humanMessage("visible", { id: "h-1" }),
      humanMessage("hidden", {
        id: "h-hidden",
        additional_kwargs: { hide_from_ui: true },
      }),
      aiMessage("reply", { id: "ai-1" }),
    ];
    const groups = getMessageGroups(messages);
    expect(groups.flatMap((g) => g.messages).map((m) => m.id)).toEqual([
      "h-1",
      "ai-1",
    ]);
  });

  test("hides messages with hidden control message names", () => {
    const messages = [
      humanMessage("visible", { id: "h-1" }),
      humanMessage("hidden", { id: "h-2", name: "summary" }),
      humanMessage("also hidden", { id: "h-3", name: "loop_warning" }),
      aiMessage("reply", { id: "ai-1" }),
    ];
    const groups = getMessageGroups(messages);
    expect(groups.flatMap((g) => g.messages).map((m) => m.id)).toEqual([
      "h-1",
      "ai-1",
    ]);
  });

  test("AI message with reasoning + content goes into both processing and assistant groups", () => {
    const msg = aiMessage("<think>reasoning</think>answer", { id: "ai-1" });
    const groups = getMessageGroups([msg]);
    expect(groups).toHaveLength(2);
    expect(groups[0]!.type).toBe("assistant:processing");
    expect(groups[1]!.type).toBe("assistant");
  });

  test("AI message with only reasoning (no content) goes into processing only", () => {
    const msg = aiMessage("<think>reasoning", { id: "ai-1" });
    const groups = getMessageGroups([msg]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.type).toBe("assistant:processing");
  });
});

// ---------------------------------------------------------------------------
// groupMessages
// ---------------------------------------------------------------------------

describe("groupMessages", () => {
  test("maps message groups through a mapper function", () => {
    const messages = [
      humanMessage("hi", { id: "h-1" }),
      aiMessage("hello", { id: "ai-1" }),
    ];
    const result = groupMessages(messages, (group) => group.type);
    expect(result).toEqual(["human", "assistant"]);
  });

  test("filters out undefined results from the mapper", () => {
    const messages = [
      humanMessage("hi", { id: "h-1" }),
      aiMessage("hello", { id: "ai-1" }),
    ];
    const result = groupMessages(messages, (group) =>
      group.type === "human" ? "found" : undefined,
    );
    expect(result).toEqual(["found"]);
  });

  test("filters out null results from the mapper", () => {
    const messages = [humanMessage("hi", { id: "h-1" })];
    const result = groupMessages(messages, () => null);
    expect(result).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// getAssistantTurnUsageMessages
// ---------------------------------------------------------------------------

describe("getAssistantTurnUsageMessages", () => {
  test("returns all nulls when there are no groups", () => {
    expect(getAssistantTurnUsageMessages([])).toEqual([]);
  });

  test("resets turn start on human group", () => {
    const groups = getMessageGroups([
      humanMessage("a", { id: "h-1" }),
      humanMessage("b", { id: "h-2" }),
    ]);
    const result = getAssistantTurnUsageMessages(groups);
    expect(result.every((v) => v === null)).toBe(true);
  });

  test("collects AI messages at turn end (last group)", () => {
    const groups = getMessageGroups([
      humanMessage("hi", { id: "h-1" }),
      aiMessage("answer", { id: "ai-1" }),
    ]);
    const result = getAssistantTurnUsageMessages(groups);
    const lastNonNull = result.filter(Boolean).flat();
    expect(lastNonNull.map((m) => m!.id)).toContain("ai-1");
  });

  test("continues past non-human groups that are not turn ends", () => {
    // human -> processing -> assistant -> human
    // The processing group has isTurnEnd=false (next is assistant, not human)
    // so it hits the `continue` branch (line 159)
    const messages = [
      humanMessage("hi", { id: "h-1" }),
      aiMessage("", {
        id: "ai-1",
        tool_calls: [{ id: "tc-1", name: "search", args: {} }],
      }),
      toolMessage("result", { id: "t-1", tool_call_id: "tc-1" }),
      aiMessage("answer", { id: "ai-2" }),
      humanMessage("follow up", { id: "h-2" }),
      aiMessage("reply", { id: "ai-3" }),
    ];
    const groups = getMessageGroups(messages);
    const result = getAssistantTurnUsageMessages(groups);
    // The processing group (index 1) should have null since it's not a turn end
    // The assistant group (index 2) ends the turn (next is human), so it gets usage
    expect(result).toHaveLength(groups.length);
    // Find the index of the "assistant" group that follows processing
    const assistantIdx = groups.findIndex((g) => g.type === "assistant");
    expect(result[assistantIdx]).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// getStreamingMessageLookup
// ---------------------------------------------------------------------------

describe("getStreamingMessageLookup", () => {
  test("returns empty sets when not streaming", () => {
    const lookup = getStreamingMessageLookup([], false);
    expect(lookup.ids.size).toBe(0);
    expect(lookup.messages.size).toBe(0);
  });

  test("returns empty sets when streaming but no metadata", () => {
    const msg = aiMessage("test", { id: "ai-1" });
    const lookup = getStreamingMessageLookup([msg], true, () => undefined);
    expect(lookup.ids.size).toBe(0);
    expect(lookup.messages.size).toBe(0);
  });

  test("returns empty sets when getMessagesMetadata is not provided", () => {
    const msg = aiMessage("test", { id: "ai-1" });
    const lookup = getStreamingMessageLookup([msg], true);
    expect(lookup.ids.size).toBe(0);
    expect(lookup.messages.size).toBe(0);
  });

  test("populates ids and messages when stream metadata exists", () => {
    const msg = aiMessage("test", { id: "ai-1" });
    const lookup = getStreamingMessageLookup([msg], true, () => ({
      streamMetadata: { langgraph_node: "agent" },
    }));
    expect(lookup.ids.has("ai-1")).toBe(true);
    expect(lookup.messages.has(msg)).toBe(true);
  });

  test("skips messages with empty string id", () => {
    const msg = aiMessage("test", { id: "" });
    const lookup = getStreamingMessageLookup([msg], true, () => ({
      streamMetadata: {},
    }));
    expect(lookup.ids.size).toBe(0);
    expect(lookup.messages.has(msg)).toBe(true);
  });

  test("skips messages with non-string id", () => {
    const msg = aiMessage("test", { id: undefined as unknown as string });
    const lookup = getStreamingMessageLookup([msg], true, () => ({
      streamMetadata: {},
    }));
    expect(lookup.ids.size).toBe(0);
    expect(lookup.messages.has(msg)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// isAssistantMessageGroupStreaming
// ---------------------------------------------------------------------------

describe("isAssistantMessageGroupStreaming", () => {
  test("returns false for non-AI messages", () => {
    const msg = humanMessage("hi");
    const lookup: ReturnType<typeof getStreamingMessageLookup> = {
      ids: new Set(["ai-1"]),
      messages: new Set(),
    };
    expect(isAssistantMessageGroupStreaming([msg], lookup)).toBe(false);
  });

  test("returns true when message id is in streaming ids", () => {
    const msg = aiMessage("test", { id: "ai-1" });
    const lookup: ReturnType<typeof getStreamingMessageLookup> = {
      ids: new Set(["ai-1"]),
      messages: new Set(),
    };
    expect(isAssistantMessageGroupStreaming([msg], lookup)).toBe(true);
  });

  test("returns true when message object is in streaming messages set", () => {
    const msg = aiMessage("test", { id: "ai-1" });
    const lookup: ReturnType<typeof getStreamingMessageLookup> = {
      ids: new Set(),
      messages: new Set([msg]),
    };
    expect(isAssistantMessageGroupStreaming([msg], lookup)).toBe(true);
  });

  test("returns false when message is not in either set", () => {
    const msg = aiMessage("test", { id: "ai-1" });
    const lookup: ReturnType<typeof getStreamingMessageLookup> = {
      ids: new Set(),
      messages: new Set(),
    };
    expect(isAssistantMessageGroupStreaming([msg], lookup)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// getAssistantTurnCopyData
// ---------------------------------------------------------------------------

describe("getAssistantTurnCopyData", () => {
  test("returns null when streaming", () => {
    const messages = [aiMessage("answer")];
    expect(
      getAssistantTurnCopyData(messages, { isStreaming: true }),
    ).toBeNull();
  });

  test("returns the last AI message content (reversed)", () => {
    const messages = [
      aiMessage("first", { id: "ai-1" }),
      aiMessage("second", { id: "ai-2" }),
    ];
    expect(getAssistantTurnCopyData(messages)).toBe("second");
  });

  test("returns null when only reasoning content exists (empty visible content)", () => {
    const messages = [aiMessage("<think>deep thought</think>", { id: "ai-1" })];
    // After think stripping, content is empty string "" which is not nullish,
    // so ?? does not fall through to reasoning. The find skips it since length is 0.
    expect(getAssistantTurnCopyData(messages)).toBeNull();
  });

  test("returns null when no AI messages have content", () => {
    const messages = [
      humanMessage("hi"),
      { id: "ai-1", type: "ai", content: "" } as Message,
    ];
    expect(getAssistantTurnCopyData(messages)).toBeNull();
  });

  test("skips non-AI messages and finds the last AI content", () => {
    const messages = [
      humanMessage("hi"),
      toolMessage("tool result"),
      aiMessage("answer", { id: "ai-1" }),
    ];
    expect(getAssistantTurnCopyData(messages)).toBe("answer");
  });
});

// ---------------------------------------------------------------------------
// extractTextFromMessage
// ---------------------------------------------------------------------------

describe("extractTextFromMessage", () => {
  test("extracts plain string content", () => {
    expect(extractTextFromMessage(aiMessage("hello"))).toBe("hello");
  });

  test("strips inline reasoning from AI string content", () => {
    expect(
      extractTextFromMessage(aiMessage("<think>reasoning</think>answer")),
    ).toBe("answer");
  });

  test("extracts text from array content", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: [
        { type: "text", text: "line 1" },
        { type: "text", text: "line 2" },
      ],
    } as Message;
    expect(extractTextFromMessage(msg)).toBe("line 1\nline 2");
  });

  test("skips non-text entries in array content", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: [
        { type: "text", text: "hello" },
        { type: "image_url", image_url: { url: "http://img.png" } },
      ],
    } as Message;
    expect(extractTextFromMessage(msg)).toBe("hello");
  });

  test("returns empty string for non-string non-array content", () => {
    const msg = { id: "ai-1", type: "ai", content: null } as unknown as Message;
    expect(extractTextFromMessage(msg)).toBe("");
  });

  test("trims whitespace from string content", () => {
    expect(extractTextFromMessage(aiMessage("  hello  "))).toBe("hello");
  });

  test("returns empty string for empty array content", () => {
    const msg = { id: "ai-1", type: "ai", content: [] } as Message;
    expect(extractTextFromMessage(msg)).toBe("");
  });
});

// ---------------------------------------------------------------------------
// extractContentFromMessage
// ---------------------------------------------------------------------------

describe("extractContentFromMessage", () => {
  test("extracts plain string content", () => {
    expect(extractContentFromMessage(aiMessage("hello"))).toBe("hello");
  });

  test("strips inline reasoning from AI string content", () => {
    expect(
      extractContentFromMessage(aiMessage("<think>reasoning</think>answer")),
    ).toBe("answer");
  });

  test("extracts text entries from array content", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: [
        { type: "text", text: "hello" },
        { type: "text", text: "world" },
      ],
    } as Message;
    expect(extractContentFromMessage(msg)).toBe("hello\nworld");
  });

  test("formats image_url entries as markdown images", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: [
        { type: "text", text: "see this:" },
        { type: "image_url", image_url: { url: "http://example.com/img.png" } },
      ],
    } as Message;
    expect(extractContentFromMessage(msg)).toBe(
      "see this:\n![image](http://example.com/img.png)",
    );
  });

  test("formats image_url entries with string content", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: [{ type: "image_url", image_url: "http://example.com/img.png" }],
    } as Message;
    expect(extractContentFromMessage(msg)).toBe(
      "![image](http://example.com/img.png)",
    );
  });

  test("returns empty string for unknown content type in array", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: [{ type: "unknown", data: "something" }],
    } as unknown as Message;
    expect(extractContentFromMessage(msg)).toBe("");
  });

  test("returns empty string for non-string non-array content", () => {
    const msg = { id: "ai-1", type: "ai", content: null } as unknown as Message;
    expect(extractContentFromMessage(msg)).toBe("");
  });

  test("trims whitespace from string content", () => {
    expect(extractContentFromMessage(aiMessage("  hello  "))).toBe("hello");
  });

  test("falls back to content.trim() for non-AI message with string content", () => {
    // splitInlineReasoningFromAIMessage returns null for non-AI, so ?.content
    // is undefined and ?? falls through to message.content.trim()
    const msg = humanMessage("  hello world  ");
    expect(extractContentFromMessage(msg)).toBe("hello world");
  });

  test("a closed think tag with only whitespace content produces no reasoning", () => {
    // Build the string programmatically to avoid the closing tag being interpreted
    const thinkClose = String.fromCharCode(60, 47, 116, 104, 105, 110, 107, 62); // </think>
    const content = "<think>   " + thinkClose + "answer";
    const message = aiMessage(content);
    // The regex captures whitespace-only body, .trim() makes it empty,
    // so normalized is falsy and reasoningParts doesn't get pushed.
    expect(extractContentFromMessage(message)).toBe("answer");
    expect(extractReasoningContentFromMessage(message)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// extractReasoningContentFromMessage
// ---------------------------------------------------------------------------

describe("extractReasoningContentFromMessage", () => {
  test("returns null for non-AI messages", () => {
    expect(extractReasoningContentFromMessage(humanMessage("hi"))).toBeNull();
  });

  test("returns reasoning_content from additional_kwargs", () => {
    const msg = aiMessage("content", {
      additional_kwargs: { reasoning_content: "deep thought" },
    });
    expect(extractReasoningContentFromMessage(msg)).toBe("deep thought");
  });

  test("returns null when additional_kwargs.reasoning_content is absent", () => {
    const msg = aiMessage("content", { additional_kwargs: {} });
    expect(extractReasoningContentFromMessage(msg)).toBeNull();
  });

  test("extracts thinking from array content with thinking part", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: [{ type: "thinking", thinking: "reasoning here" }],
    } as unknown as Message;
    expect(extractReasoningContentFromMessage(msg)).toBe("reasoning here");
  });

  test("returns reasoning from inline think tags in string content", () => {
    const msg = aiMessage("<think>inline reasoning</think>answer");
    expect(extractReasoningContentFromMessage(msg)).toBe("inline reasoning");
  });

  test("returns null for plain string content without reasoning", () => {
    expect(
      extractReasoningContentFromMessage(aiMessage("just text")),
    ).toBeNull();
  });

  test("returns null when content is null", () => {
    const msg = { id: "ai-1", type: "ai", content: null } as unknown as Message;
    expect(extractReasoningContentFromMessage(msg)).toBeNull();
  });

  test("returns null for array content without thinking part", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: [{ type: "text", text: "hello" }],
    } as Message;
    expect(extractReasoningContentFromMessage(msg)).toBeNull();
  });

  test("returns null for array content with first element that is not an object", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: ["just a string"],
    } as unknown as Message;
    expect(extractReasoningContentFromMessage(msg)).toBeNull();
  });

  test("returns null for array content with first element that is null", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: [null],
    } as unknown as Message;
    expect(extractReasoningContentFromMessage(msg)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// removeReasoningContentFromMessage
// ---------------------------------------------------------------------------

describe("removeReasoningContentFromMessage", () => {
  test("deletes reasoning_content from additional_kwargs", () => {
    const msg = aiMessage("content", {
      additional_kwargs: { reasoning_content: "thought" },
    });
    removeReasoningContentFromMessage(msg);
    expect(msg.additional_kwargs).not.toHaveProperty("reasoning_content");
  });

  test("does nothing for non-AI messages", () => {
    const msg = humanMessage("hi", {
      additional_kwargs: { reasoning_content: "thought" },
    });
    removeReasoningContentFromMessage(msg);
    // Additional kwargs should still have the property since we didn't process it
    expect(msg.additional_kwargs?.reasoning_content).toBe("thought");
  });

  test("does nothing when additional_kwargs is undefined", () => {
    const msg = aiMessage("content");
    delete msg.additional_kwargs;
    expect(() => removeReasoningContentFromMessage(msg)).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// extractURLFromImageURLContent
// ---------------------------------------------------------------------------

describe("extractURLFromImageURLContent", () => {
  test("returns string content directly", () => {
    expect(extractURLFromImageURLContent("http://example.com/img.png")).toBe(
      "http://example.com/img.png",
    );
  });

  test("extracts url from object content", () => {
    expect(
      extractURLFromImageURLContent({ url: "http://example.com/img.png" }),
    ).toBe("http://example.com/img.png");
  });
});

// ---------------------------------------------------------------------------
// hasContent
// ---------------------------------------------------------------------------

describe("hasContent", () => {
  test("returns true for non-empty string content", () => {
    expect(hasContent(aiMessage("hello"))).toBe(true);
  });

  test("returns false for empty string content", () => {
    expect(hasContent(aiMessage(""))).toBe(false);
  });

  test("returns false for whitespace-only string content", () => {
    expect(hasContent(aiMessage("   "))).toBe(false);
  });

  test("returns true for non-empty array content", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: [{ type: "text", text: "hello" }],
    } as Message;
    expect(hasContent(msg)).toBe(true);
  });

  test("returns false for empty array content", () => {
    const msg = { id: "ai-1", type: "ai", content: [] } as Message;
    expect(hasContent(msg)).toBe(false);
  });

  test("returns false for non-string non-array content", () => {
    const msg = { id: "ai-1", type: "ai", content: null } as unknown as Message;
    expect(hasContent(msg)).toBe(false);
  });

  test("returns false for undefined content", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: undefined,
    } as unknown as Message;
    expect(hasContent(msg)).toBe(false);
  });

  test("returns true for non-AI message with string content", () => {
    // splitInlineReasoningFromAIMessage returns null for non-AI,
    // so ?.content is undefined, ?? falls through to message.content.trim()
    expect(hasContent(humanMessage("hello"))).toBe(true);
  });

  test("returns false for non-AI message with empty string content", () => {
    expect(hasContent(humanMessage(""))).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// hasReasoning
// ---------------------------------------------------------------------------

describe("hasReasoning", () => {
  test("returns false for non-AI messages", () => {
    expect(hasReasoning(humanMessage("hi"))).toBe(false);
  });

  test("returns true when additional_kwargs has reasoning_content", () => {
    const msg = aiMessage("content", {
      additional_kwargs: { reasoning_content: "thought" },
    });
    expect(hasReasoning(msg)).toBe(true);
  });

  test("returns true when array content has thinking part", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: [{ type: "thinking", thinking: "reasoning" }],
    } as unknown as Message;
    expect(hasReasoning(msg)).toBe(true);
  });

  test("returns true when string content has inline think tags", () => {
    expect(hasReasoning(aiMessage("<think>reasoning</think>answer"))).toBe(
      true,
    );
  });

  test("returns false for plain string content", () => {
    expect(hasReasoning(aiMessage("just text"))).toBe(false);
  });

  test("returns false for empty array content", () => {
    const msg = { id: "ai-1", type: "ai", content: [] } as Message;
    expect(hasReasoning(msg)).toBe(false);
  });

  test("returns false for null content on AI message", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: null,
    } as unknown as Message;
    expect(hasReasoning(msg)).toBe(false);
  });

  test("returns false for undefined content on AI message", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: undefined,
    } as unknown as Message;
    expect(hasReasoning(msg)).toBe(false);
  });

  test("returns false for numeric content on AI message", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: 42,
    } as unknown as Message;
    expect(hasReasoning(msg)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// hasToolCalls
// ---------------------------------------------------------------------------

describe("hasToolCalls", () => {
  test("returns false for non-AI messages", () => {
    const msg = humanMessage("hi");
    expect(hasToolCalls(msg)).toBe(false);
  });

  test("returns true when AI message has tool calls", () => {
    const msg = aiMessage("", {
      tool_calls: [{ id: "tc-1", name: "search", args: {} }],
    });
    expect(hasToolCalls(msg)).toBe(true);
  });

  test("returns false when AI message has empty tool_calls array", () => {
    const msg = aiMessage("content", { tool_calls: [] });
    expect(hasToolCalls(msg)).toBe(false);
  });

  test("returns falsy when AI message has no tool_calls property", () => {
    // tool_calls is undefined, so `undefined && ...` evaluates to undefined (falsy)
    expect(hasToolCalls(aiMessage("content"))).toBeFalsy();
  });
});

// ---------------------------------------------------------------------------
// hasPresentFiles
// ---------------------------------------------------------------------------

describe("hasPresentFiles", () => {
  test("returns false for non-AI messages", () => {
    expect(hasPresentFiles(humanMessage("hi"))).toBe(false);
  });

  test("returns true when AI message has present_files tool call", () => {
    const msg = aiMessage("", {
      tool_calls: [
        { id: "tc-1", name: "present_files", args: { filepaths: ["a.ts"] } },
      ],
    });
    expect(hasPresentFiles(msg)).toBe(true);
  });

  test("returns false when AI message has no present_files tool call", () => {
    const msg = aiMessage("", {
      tool_calls: [{ id: "tc-1", name: "search", args: {} }],
    });
    expect(hasPresentFiles(msg)).toBe(false);
  });

  test("returns falsy when tool_calls is undefined", () => {
    // tool_calls is undefined, optional chaining returns undefined (falsy)
    expect(hasPresentFiles(aiMessage("content"))).toBeFalsy();
  });
});

// ---------------------------------------------------------------------------
// isClarificationToolMessage
// ---------------------------------------------------------------------------

describe("isClarificationToolMessage", () => {
  test("returns true for tool messages with name ask_clarification", () => {
    const msg = toolMessage("what?", { name: "ask_clarification" });
    expect(isClarificationToolMessage(msg)).toBe(true);
  });

  test("returns false for tool messages with other names", () => {
    const msg = toolMessage("result", { name: "search" });
    expect(isClarificationToolMessage(msg)).toBe(false);
  });

  test("returns false for non-tool messages", () => {
    expect(isClarificationToolMessage(humanMessage("hi"))).toBe(false);
    expect(isClarificationToolMessage(aiMessage("hi"))).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// extractPresentFilesFromMessage
// ---------------------------------------------------------------------------

describe("extractPresentFilesFromMessage", () => {
  test("returns empty array for non-AI messages", () => {
    expect(extractPresentFilesFromMessage(humanMessage("hi"))).toEqual([]);
  });

  test("returns empty array when no present_files tool call", () => {
    expect(extractPresentFilesFromMessage(aiMessage("content"))).toEqual([]);
  });

  test("extracts filepaths from present_files tool calls", () => {
    const msg = aiMessage("", {
      tool_calls: [
        {
          id: "tc-1",
          name: "present_files",
          args: { filepaths: ["a.ts", "b.ts"] },
        },
      ],
    });
    expect(extractPresentFilesFromMessage(msg)).toEqual(["a.ts", "b.ts"]);
  });

  test("handles multiple present_files tool calls", () => {
    const msg = aiMessage("", {
      tool_calls: [
        {
          id: "tc-1",
          name: "present_files",
          args: { filepaths: ["a.ts"] },
        },
        {
          id: "tc-2",
          name: "present_files",
          args: { filepaths: ["b.ts"] },
        },
      ],
    });
    expect(extractPresentFilesFromMessage(msg)).toEqual(["a.ts", "b.ts"]);
  });

  test("skips present_files tool calls without filepaths array", () => {
    const msg = aiMessage("", {
      tool_calls: [
        { id: "tc-1", name: "present_files", args: {} },
        {
          id: "tc-2",
          name: "present_files",
          args: { filepaths: ["a.ts"] },
        },
      ],
    });
    expect(extractPresentFilesFromMessage(msg)).toEqual(["a.ts"]);
  });

  test("handles undefined tool_calls", () => {
    const msg = { id: "ai-1", type: "ai", content: "" } as Message;
    expect(extractPresentFilesFromMessage(msg)).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// hasSubagent
// ---------------------------------------------------------------------------

describe("hasSubagent", () => {
  test("returns true when message has a task tool call", () => {
    const msg = aiMessage("", {
      tool_calls: [{ id: "tc-1", name: "task", args: {} }],
    }) as import("@langchain/langgraph-sdk").AIMessage;
    expect(hasSubagent(msg)).toBe(true);
  });

  test("returns false when message has no task tool call", () => {
    const msg = aiMessage("", {
      tool_calls: [{ id: "tc-1", name: "search", args: {} }],
    }) as import("@langchain/langgraph-sdk").AIMessage;
    expect(hasSubagent(msg)).toBe(false);
  });

  test("returns false when tool_calls is undefined", () => {
    const msg = aiMessage(
      "content",
    ) as import("@langchain/langgraph-sdk").AIMessage;
    expect(hasSubagent(msg)).toBe(false);
  });

  test("returns false when tool_calls is empty", () => {
    const msg = aiMessage("", {
      tool_calls: [],
    }) as import("@langchain/langgraph-sdk").AIMessage;
    expect(hasSubagent(msg)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// findToolCallResult
// ---------------------------------------------------------------------------

describe("findToolCallResult", () => {
  test("finds tool message matching the given tool call id", () => {
    const messages = [
      humanMessage("hi"),
      aiMessage("", {
        tool_calls: [{ id: "tc-1", name: "search", args: {} }],
      }),
      toolMessage("search result", { tool_call_id: "tc-1" }),
    ];
    expect(findToolCallResult("tc-1", messages)).toBe("search result");
  });

  test("returns undefined when no matching tool message exists", () => {
    const messages = [humanMessage("hi"), aiMessage("answer")];
    expect(findToolCallResult("tc-missing", messages)).toBeUndefined();
  });

  test("skips tool messages with empty content", () => {
    const messages = [
      toolMessage("", { tool_call_id: "tc-1" }),
      toolMessage("actual result", { tool_call_id: "tc-2" }),
    ];
    expect(findToolCallResult("tc-1", messages)).toBeUndefined();
  });

  test("returns the first matching tool message with content", () => {
    const messages = [
      toolMessage("", { tool_call_id: "tc-1" }),
      toolMessage("first result", { tool_call_id: "tc-1" }),
    ];
    expect(findToolCallResult("tc-1", messages)).toBe("first result");
  });
});

// ---------------------------------------------------------------------------
// isHiddenFromUIMessage
// ---------------------------------------------------------------------------

describe("isHiddenFromUIMessage", () => {
  test("returns true when hide_from_ui is true", () => {
    const msg = humanMessage("hidden", {
      additional_kwargs: { hide_from_ui: true },
    });
    expect(isHiddenFromUIMessage(msg)).toBe(true);
  });

  test("returns false when hide_from_ui is false", () => {
    const msg = humanMessage("visible", {
      additional_kwargs: { hide_from_ui: false },
    });
    expect(isHiddenFromUIMessage(msg)).toBe(false);
  });

  test("returns true for messages with name 'summary'", () => {
    const msg = humanMessage("hidden", { name: "summary" });
    expect(isHiddenFromUIMessage(msg)).toBe(true);
  });

  test("returns true for messages with name 'loop_warning'", () => {
    const msg = humanMessage("hidden", { name: "loop_warning" });
    expect(isHiddenFromUIMessage(msg)).toBe(true);
  });

  test("returns true for messages with name 'todo_reminder'", () => {
    const msg = humanMessage("hidden", { name: "todo_reminder" });
    expect(isHiddenFromUIMessage(msg)).toBe(true);
  });

  test("returns true for messages with name 'todo_completion_reminder'", () => {
    const msg = humanMessage("hidden", { name: "todo_completion_reminder" });
    expect(isHiddenFromUIMessage(msg)).toBe(true);
  });

  test("returns false for messages with other names", () => {
    const msg = humanMessage("visible", { name: "some_other_name" });
    expect(isHiddenFromUIMessage(msg)).toBe(false);
  });

  test("returns false for messages without additional_kwargs or special name", () => {
    expect(isHiddenFromUIMessage(humanMessage("visible"))).toBe(false);
  });

  test("returns false for messages with undefined name", () => {
    expect(
      isHiddenFromUIMessage(humanMessage("visible", { name: undefined })),
    ).toBe(false);
  });

  test("returns false for messages with numeric name", () => {
    expect(
      isHiddenFromUIMessage(
        humanMessage("visible", { name: 123 as unknown as string }),
      ),
    ).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// stripUploadedFilesTag
// ---------------------------------------------------------------------------

describe("stripUploadedFilesTag", () => {
  test("removes uploaded_files tag from content", () => {
    const content =
      "Before<uploaded_files>\n- file.txt (100)\n  Path: /a/file.txt\n</uploaded_files>After";
    expect(stripUploadedFilesTag(content)).toBe("BeforeAfter");
  });

  test("returns content unchanged when no tag is present", () => {
    expect(stripUploadedFilesTag("no tags here")).toBe("no tags here");
  });

  test("handles multiple uploaded_files tags", () => {
    const content =
      "<uploaded_files>tag1</uploaded_files>middle<uploaded_files>tag2</uploaded_files>";
    expect(stripUploadedFilesTag(content)).toBe("middle");
  });

  test("trims resulting whitespace", () => {
    expect(
      stripUploadedFilesTag("  <uploaded_files>content</uploaded_files>  "),
    ).toBe("");
  });

  test("handles empty content", () => {
    expect(stripUploadedFilesTag("")).toBe("");
  });
});

// ---------------------------------------------------------------------------
// INTERNAL_MARKER_TAGS
// ---------------------------------------------------------------------------

describe("INTERNAL_MARKER_TAGS", () => {
  test("contains expected tag names", () => {
    expect(INTERNAL_MARKER_TAGS).toEqual([
      "uploaded_files",
      "system-reminder",
      "memory",
      "current_date",
    ]);
  });
});

// ---------------------------------------------------------------------------
// stripInternalMarkers
// ---------------------------------------------------------------------------

describe("stripInternalMarkers", () => {
  test("removes uploaded_files tag", () => {
    const content = "before<uploaded_files>data</uploaded_files>after";
    expect(stripInternalMarkers(content)).toBe("beforeafter");
  });

  test("removes system-reminder tag", () => {
    const content =
      "before<system-reminder>reminder data</system-reminder>after";
    expect(stripInternalMarkers(content)).toBe("beforeafter");
  });

  test("removes memory tag", () => {
    const content = "before<memory>memory data</memory>after";
    expect(stripInternalMarkers(content)).toBe("beforeafter");
  });

  test("removes current_date tag", () => {
    const content = "before<current_date>2024-01-01</current_date>after";
    expect(stripInternalMarkers(content)).toBe("beforeafter");
  });

  test("removes multiple different tags", () => {
    const content = "<uploaded_files>f</uploaded_files>mid<memory>m</memory>";
    expect(stripInternalMarkers(content)).toBe("mid");
  });

  test("handles multiline tag content", () => {
    const content = "<system-reminder>\nline1\nline2\n</system-reminder>after";
    expect(stripInternalMarkers(content)).toBe("after");
  });

  test("returns content unchanged when no markers present", () => {
    expect(stripInternalMarkers("clean content")).toBe("clean content");
  });

  test("trims resulting whitespace", () => {
    expect(stripInternalMarkers("  <memory>x</memory>  ")).toBe("");
  });

  test("handles empty content", () => {
    expect(stripInternalMarkers("")).toBe("");
  });
});

// ---------------------------------------------------------------------------
// parseUploadedFiles
// ---------------------------------------------------------------------------

describe("parseUploadedFiles", () => {
  test("returns empty array when no uploaded_files tag", () => {
    expect(parseUploadedFiles("no tag here")).toEqual([]);
  });

  test("returns empty array for 'No files have been uploaded yet.'", () => {
    const content =
      "<uploaded_files>No files have been uploaded yet.</uploaded_files>";
    expect(parseUploadedFiles(content)).toEqual([]);
  });

  test("returns empty array for '(empty)' content", () => {
    const content = "<uploaded_files>(empty)</uploaded_files>";
    expect(parseUploadedFiles(content)).toEqual([]);
  });

  test("parses a single file entry", () => {
    const content = `<uploaded_files>
- document.pdf (1024)
  Path: /uploads/document.pdf
</uploaded_files>`;
    const files = parseUploadedFiles(content);
    expect(files).toHaveLength(1);
    expect(files[0]).toEqual({
      filename: "document.pdf",
      size: 1024,
      path: "/uploads/document.pdf",
    });
  });

  test("parses multiple file entries", () => {
    const content = `<uploaded_files>
- file1.txt (512)
  Path: /uploads/file1.txt
- file2.pdf (2048)
  Path: /uploads/file2.pdf
</uploaded_files>`;
    const files = parseUploadedFiles(content);
    expect(files).toHaveLength(2);
    expect(files[0]!.filename).toBe("file1.txt");
    expect(files[0]!.size).toBe(512);
    expect(files[0]!.path).toBe("/uploads/file1.txt");
    expect(files[1]!.filename).toBe("file2.pdf");
    expect(files[1]!.size).toBe(2048);
    expect(files[1]!.path).toBe("/uploads/file2.pdf");
  });

  test("returns empty array for empty uploaded_files tag", () => {
    const content = "<uploaded_files></uploaded_files>";
    expect(parseUploadedFiles(content)).toEqual([]);
  });

  test("trims filenames and paths", () => {
    const content = `<uploaded_files>
-  spaced file.txt  (100)
  Path:  /some/path/  </uploaded_files>`;
    const files = parseUploadedFiles(content);
    expect(files).toHaveLength(1);
    expect(files[0]!.filename).toBe("spaced file.txt");
    expect(files[0]!.path).toBe("/some/path/");
  });
});

// ---------------------------------------------------------------------------
// Additional getMessageGroups edge cases for full coverage
// ---------------------------------------------------------------------------

describe("getMessageGroups - additional edge cases", () => {
  test("ignores messages with unknown type (not human, tool, or ai)", () => {
    const messages = [
      humanMessage("hi", { id: "h-1" }),
      {
        id: "sys-1",
        type: "system",
        content: "system message",
      } as unknown as Message,
      aiMessage("reply", { id: "ai-1" }),
    ];
    const groups = getMessageGroups(messages);
    expect(groups).toHaveLength(2);
    expect(groups[0]!.type).toBe("human");
    expect(groups[1]!.type).toBe("assistant");
  });

  test("AI message with reasoning content in additional_kwargs creates processing group", () => {
    const msg = aiMessage("answer", {
      additional_kwargs: { reasoning_content: "thought" },
    });
    const groups = getMessageGroups([msg]);
    // Has reasoning -> processing, has content -> assistant
    expect(groups).toHaveLength(2);
    expect(groups[0]!.type).toBe("assistant:processing");
    expect(groups[1]!.type).toBe("assistant");
  });

  test("AI message with only tool calls (no reasoning, no content) creates processing group only", () => {
    const msg = aiMessage("", {
      tool_calls: [{ id: "tc-1", name: "search", args: {} }],
    });
    const groups = getMessageGroups([msg]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.type).toBe("assistant:processing");
  });

  test("AI message with tool calls and content but not present_files or task", () => {
    const msg = aiMessage("", {
      tool_calls: [{ id: "tc-1", name: "search", args: {} }],
    });
    const groups = getMessageGroups([msg]);
    expect(groups[0]!.type).toBe("assistant:processing");
  });

  test("tool message with no open group logs error", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const tool = toolMessage("result");
    getMessageGroups([tool]);
    expect(spy).toHaveBeenCalledOnce();
    spy.mockRestore();
  });

  test("clarification tool message without open processing group still creates clarification group", () => {
    const tool = toolMessage("what?", {
      id: "t-1",
      name: "ask_clarification",
      tool_call_id: "tc-1",
    });
    const groups = getMessageGroups([tool]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.type).toBe("assistant:clarification");
  });

  test("present_files takes priority over subagent check", () => {
    // A message could theoretically have both present_files and task tool calls
    // present_files is checked first
    const msg = aiMessage("", {
      tool_calls: [
        {
          id: "tc-1",
          name: "present_files",
          args: { filepaths: ["a.ts"] },
        },
        { id: "tc-2", name: "task", args: {} },
      ],
    });
    const groups = getMessageGroups([msg]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.type).toBe("assistant:present-files");
  });

  test("subagent takes priority over processing when no present_files", () => {
    const msg = aiMessage("", {
      tool_calls: [{ id: "tc-1", name: "task", args: {} }],
    });
    const groups = getMessageGroups([msg]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.type).toBe("assistant:subagent");
  });

  test("empty assistant group with content string '' does not create assistant group", () => {
    const msg = aiMessage("");
    const groups = getMessageGroups([msg]);
    expect(groups).toHaveLength(0);
  });

  test("AI message with array content creates assistant group", () => {
    const msg = {
      id: "ai-1",
      type: "ai",
      content: [{ type: "text", text: "hello" }],
    } as Message;
    const groups = getMessageGroups([msg]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.type).toBe("assistant");
  });

  test("lastOpenGroup returns null for assistant:clarification type", () => {
    // Create a clarification group, then add a tool message
    // The tool message should not be added to the clarification group
    const clarificationTool = toolMessage("clarify?", {
      id: "t-1",
      name: "ask_clarification",
      tool_call_id: "tc-1",
    });
    const regularTool = toolMessage("result", {
      id: "t-2",
      tool_call_id: "tc-2",
    });
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const groups = getMessageGroups([clarificationTool, regularTool]);
    // The clarification group is not open, so the regular tool logs an error
    expect(spy).toHaveBeenCalledOnce();
    spy.mockRestore();
  });
});
