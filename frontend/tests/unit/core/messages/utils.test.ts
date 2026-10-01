import type { Message } from "@langchain/langgraph-sdk";
import { describe, expect, test, vi } from "vitest";

import {
  areStreamMetadataSnapshotsEqual,
  extractContentFromMessage,
  extractPresentFilesFromMessage,
  extractReasoningContentFromMessage,
  extractTextFromMessage,
  extractURLFromImageURLContent,
  findToolCallResult,
  getAssistantTurnCopyData,
  getAssistantTurnUsageMessages,
  getMessageCopyData,
  getMessageGroups,
  getStreamingMessageLookup,
  getStreamMetadataSnapshot,
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

  test("keeps an orphan tool message visible in a processing group", () => {
    // Post-#4399 behavior: a tool message with no open processing group
    // (out-of-order replay, history pagination starting mid-turn) is no longer
    // dropped with console.error — it opens a processing group so the result
    // stays visible.
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const tool = toolMessage("orphan", { id: "t-orphan" });
    const groups = getMessageGroups([tool]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.type).toBe("assistant:processing");
    expect(groups[0]!.messages.map((m) => m.id)).toEqual(["t-orphan"]);
    expect(spy).not.toHaveBeenCalled();
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

  test("AI message with reasoning + content becomes a single assistant bubble", () => {
    // Post-#3868 behavior: a message with answer content and no tool calls
    // becomes only an assistant bubble — the bubble renders the reasoning in
    // its own collapsible, so also feeding a processing group would paint the
    // identical reasoning twice in the ChainOfThought panel.
    const msg = aiMessage("<think>reasoning</think>answer", { id: "ai-1" });
    const groups = getMessageGroups([msg]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.type).toBe("assistant");
    expect(groups[0]!.messages.map((m) => m.id)).toEqual(["ai-1"]);
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

  test("falls back to reasoning content when only reasoning exists", () => {
    const messages = [aiMessage("<think>deep thought</think>", { id: "ai-1" })];
    // After think stripping the visible content is empty; the copy data falls
    // back to the reasoning text so a reasoning-only turn keeps its copy
    // button instead of losing it entirely.
    expect(getAssistantTurnCopyData(messages)).toBe("deep thought");
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
      "current_uploads",
      "uploaded_files",
      "slash_skill_activation",
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
    // Backend _format_file_entry emits human-readable sizes ("<n> KB"/"<n> MB");
    // parseUploadedFiles converts them back to bytes.
    const content = `<uploaded_files>
- document.pdf (1.0 KB)
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
- file1.txt (0.5 KB)
  Path: /uploads/file1.txt
- file2.pdf (2.0 KB)
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
-  spaced file.txt  (100 B)
  Path:  /some/path/  </uploaded_files>`;
    const files = parseUploadedFiles(content);
    expect(files).toHaveLength(1);
    expect(files[0]!.filename).toBe("spaced file.txt");
    expect(files[0]!.size).toBe(100);
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

  test("AI message with reasoning content in additional_kwargs becomes a single assistant bubble", () => {
    const msg = aiMessage("answer", {
      additional_kwargs: { reasoning_content: "thought" },
    });
    const groups = getMessageGroups([msg]);
    // Post-#3868 behavior: the assistant bubble renders reasoning_content in
    // its own collapsible, so no separate processing group is created.
    expect(groups).toHaveLength(1);
    expect(groups[0]!.type).toBe("assistant");
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

  test("tool message with no open group stays visible in a new processing group", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const tool = toolMessage("result");
    const groups = getMessageGroups([tool]);
    // Post-#4399: no dropped message, no console.error — a processing group
    // keeps the result visible.
    expect(groups).toHaveLength(1);
    expect(groups[0]!.type).toBe("assistant:processing");
    expect(spy).not.toHaveBeenCalled();
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
    // Create a clarification group, then add a tool message.
    // The clarification group is terminal (lastOpenGroup returns null), so the
    // regular tool message falls into the orphan fallback instead of an open
    // processing group — post-#4399 it attaches to the most recent group and
    // no console.error fires.
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
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
    expect(groups).toHaveLength(1);
    expect(groups[0]!.type).toBe("assistant:clarification");
    expect(groups[0]!.messages.map((m) => m.id)).toEqual(["t-1", "t-2"]);
  });
});
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
- bigfile.zip (1.0 GB)
  Path: /uploads/bigfile.zip
</uploaded_files>`;
    const files = parseUploadedFiles(content);
    expect(files).toHaveLength(1);
    expect(files[0]!.size).toBe(1073741824);
    expect(files[0]!.filename).toBe("bigfile.zip");
  });

  test("parses file with spaces in filename", () => {
    const content = `<uploaded_files>
- my document file.pdf (2.0 KB)
  Path: /uploads/my document file.pdf
</uploaded_files>`;
    const files = parseUploadedFiles(content);
    expect(files).toHaveLength(1);
    expect(files[0]!.filename).toBe("my document file.pdf");
    expect(files[0]!.size).toBe(2048);
  });

  test("returns empty for non-matching uploaded_files content", () => {
    const content =
      "<uploaded_files>random text without format</uploaded_files>";
    expect(parseUploadedFiles(content)).toEqual([]);
  });

  test("handles multiple lines between file entries", () => {
    const content = `<uploaded_files>

- a.txt (10 B)
  Path: /a.txt

</uploaded_files>`;
    const files = parseUploadedFiles(content);
    expect(files).toHaveLength(1);
    expect(files[0]!.filename).toBe("a.txt");
    expect(files[0]!.size).toBe(10);
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

describe("human message internal context stripping", () => {
  test("strips legacy uploaded_files context from copy data", () => {
    // Display-only backward compatibility (#4212): pre-#4174 history still
    // carries <uploaded_files> blocks, which copy data must strip rather
    // than leak as raw XML with server-side paths.
    const message = {
      id: "human-with-legacy-upload",
      type: "human",
      content:
        "<uploaded_files>\nThe following files were uploaded in this message:\n\n- paper.pdf (1.0 MB)\n  Path: /mnt/user-data/uploads/paper.pdf\n</uploaded_files>\n\nSummarize this paper",
    } as Message;

    expect(getMessageCopyData(message)).toBe("Summarize this paper");
  });

  test("strips current_uploads context from copy data", () => {
    // Mirrors the block UploadsMiddleware emits since #4174, including the
    // trailing usage-guidance lines.
    const message = {
      id: "human-with-current-uploads",
      type: "human",
      content:
        "<current_uploads>\nThe following files were uploaded in this message:\n\n- paper.docx (177.6 KB)\n  Path: /mnt/user-data/uploads/paper.docx\n\nTo work with these files:\n- Use `grep` to search for keywords\n  (e.g. `grep(pattern='revenue', path='/mnt/user-data/uploads/')`).\n</current_uploads>\n\nMake a slide deck from this",
    } as Message;

    expect(getMessageCopyData(message)).toBe("Make a slide deck from this");
  });

  test("parses uploaded files from a current_uploads block", () => {
    const content =
      "<current_uploads>\nThe following files were uploaded in this message:\n\n- paper.docx (177.6 KB)\n  Path: /mnt/user-data/uploads/paper.docx\n  Document outline (use `read_file` with line ranges to read sections):\n    L1: Introduction\n- data.xlsx (12.0 KB)\n  Path: /mnt/user-data/uploads/data.xlsx\n</current_uploads>\n\nSummarize";

    // size is bytes (FileInMessage contract): the block's "177.6 KB" /
    // "12.0 KB" are converted back from the human-readable form the backend
    // emits, so formatBytes re-renders them at the original magnitude.
    expect(parseUploadedFiles(content)).toEqual([
      {
        filename: "paper.docx",
        size: Math.round(177.6 * 1024), // 181862
        path: "/mnt/user-data/uploads/paper.docx",
      },
      {
        filename: "data.xlsx",
        size: 12 * 1024, // 12288
        path: "/mnt/user-data/uploads/data.xlsx",
      },
    ]);
  });

  test("parses uploaded filenames that contain parentheses", () => {
    // Browsers name duplicate downloads "photo (1).png"; the backend emits the
    // filename verbatim, so the parser must not stop the name at the first "(".
    const content =
      "<current_uploads>\nThe following files were uploaded in this message:\n\n- photo (1).png (12.3 KB)\n  Path: /mnt/user-data/uploads/photo (1).png\n- report (final) (2).docx (1.5 MB)\n  Path: /mnt/user-data/uploads/report (final) (2).docx\n- normal.pdf (3.0 KB)\n  Path: /mnt/user-data/uploads/normal.pdf\n</current_uploads>\n\nSummarize";

    expect(parseUploadedFiles(content)).toEqual([
      {
        filename: "photo (1).png",
        size: Math.round(12.3 * 1024),
        path: "/mnt/user-data/uploads/photo (1).png",
      },
      {
        filename: "report (final) (2).docx",
        size: Math.round(1.5 * 1024 * 1024),
        path: "/mnt/user-data/uploads/report (final) (2).docx",
      },
      {
        filename: "normal.pdf",
        size: 3 * 1024,
        path: "/mnt/user-data/uploads/normal.pdf",
      },
    ]);
  });

  test("stripInternalMarkers removes current_uploads blocks on export", () => {
    const content =
      "<current_uploads>\n- paper.docx (177.6 KB)\n  Path: /mnt/user-data/uploads/paper.docx\n</current_uploads>\n\nExport me";

    expect(stripInternalMarkers(content)).toBe("Export me");
  });

  test("stripInternalMarkers removes attributed project context blocks on export", () => {
    const content =
      '<project name="Roadmap">\nsecret instructions\n</project>\n\nExport me';

    expect(stripInternalMarkers(content)).toBe("Export me");
  });

  test("stripInternalMarkers removes documents blocks on export", () => {
    const content =
      '<documents count="2" shown="2">\n- id=abc | q3.pdf (2.1 MB, modified 2026-09-10)\n</documents>\n\nExport me';

    expect(stripInternalMarkers(content)).toBe("Export me");
  });

  test("stripInternalMarkers preserves fenced code that uses marker tag names", () => {
    const content = [
      "Here is my pom:",
      "```xml",
      "<project>",
      "  <artifactId>demo</artifactId>",
      "</project>",
      "```",
      "Export me",
    ].join("\n");

    expect(stripInternalMarkers(content)).toBe(content);
  });

  test("stripInternalMarkers preserves tilde-fenced and indented code spans", () => {
    const tilde = ["~~~", '<documents count="1">', "</documents>", "~~~"].join(
      "\n",
    );
    expect(stripInternalMarkers(tilde)).toBe(tilde);

    // The leading text keeps ``trim()`` from eating the code's indentation.
    const indented = [
      "Pasted snippet:",
      "",
      "    <project>",
      "    </project>",
    ].join("\n");
    expect(stripInternalMarkers(indented)).toBe(indented);
  });

  test("stripInternalMarkers still removes an injected block whose content contains a fence", () => {
    const content = [
      "<memory>",
      "```",
      "not a real fence owner",
      "```",
      "</memory>",
      "Export me",
    ].join("\n");

    expect(stripInternalMarkers(content)).toBe("Export me");
  });

  test("strips slash skill activation context from display content", () => {
    const content =
      "<slash_skill_activation>\n<skill_content># Secret SKILL.md</skill_content>\n</slash_skill_activation>\nreal user task";

    expect(stripUploadedFilesTag(content)).toBe("real user task");
  });

  test("hides leaked slash skill activation messages with no user text", () => {
    const messages = [
      {
        id: "slash-activation",
        type: "human",
        content:
          "<slash_skill_activation>\n<skill_content># Secret SKILL.md</skill_content>\n</slash_skill_activation>",
      },
      {
        id: "ai-1",
        type: "ai",
        content: "Public answer",
      },
    ] as Message[];

    const groups = getMessageGroups(messages);

    expect(groups.map((group) => group.type)).toEqual(["assistant"]);
    expect(
      groups.flatMap((group) => group.messages).map((message) => message.id),
    ).toEqual(["ai-1"]);
  });
});

test("hides internal todo reminder messages from message groups", () => {
  const messages = [
    {
      id: "human-1",
      type: "human",
      content: "Audit the middleware",
    },
    {
      id: "todo-reminder-1",
      type: "human",
      name: "todo_completion_reminder",
      content: "<system_reminder>finish todos</system_reminder>",
    },
    {
      id: "todo-reminder-2",
      type: "human",
      name: "todo_reminder",
      content: "<system_reminder>remember todos</system_reminder>",
    },
    {
      id: "ai-1",
      type: "ai",
      content: "Done",
    },
  ] as Message[];

  const groups = getMessageGroups(messages);

  expect(groups.map((group) => group.type)).toEqual(["human", "assistant"]);
  expect(
    groups.flatMap((group) => group.messages).map((message) => message.id),
  ).toEqual(["human-1", "ai-1"]);
});

test("hides assistant copy data while that turn is streaming", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "Partial answer",
    },
  ] as Message[];

  expect(getAssistantTurnCopyData(messages)).toBe("Partial answer");
  expect(getAssistantTurnCopyData(messages, { isStreaming: true })).toBeNull();
});

test("falls back to reasoning for a reasoning-only assistant turn's copy data", () => {
  // A turn can end with reasoning but no answer text (e.g. stopped during
  // thinking). getMessageCopyData already copies the reasoning in that case;
  // the turn-level copy button must not disappear instead.
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      additional_kwargs: { reasoning_content: "the actual reasoning" },
    },
  ] as Message[];

  expect(getAssistantTurnCopyData(messages)).toBe("the actual reasoning");
});

test("settled copy data is derived once per messages array reference (#5094)", () => {
  // Settled group arrays keep their identity across streaming chunks, and the
  // copy button re-renders per chunk. Reading `content` through a getter
  // proves the second settled call is served from the array-reference cache
  // instead of re-running the O(turn bytes) extraction.
  let contentReads = 0;
  const message = {
    id: "ai-1",
    type: "ai",
    get content() {
      contentReads += 1;
      return "Final answer";
    },
  } as unknown as Message;
  const messages = [message];

  expect(getAssistantTurnCopyData(messages)).toBe("Final answer");
  const readsAfterFirstCall = contentReads;
  expect(readsAfterFirstCall).toBeGreaterThan(0);

  expect(getAssistantTurnCopyData(messages)).toBe("Final answer");
  expect(contentReads).toBe(readsAfterFirstCall);
});

test("copy-data cache does not leak across array references", () => {
  const first = [
    { id: "ai-1", type: "ai", content: "first answer" },
  ] as Message[];
  const second = [
    { id: "ai-2", type: "ai", content: "second answer" },
  ] as Message[];

  expect(getAssistantTurnCopyData(first)).toBe("first answer");
  expect(getAssistantTurnCopyData(second)).toBe("second answer");
  // The streaming short-circuit stays ahead of the cache.
  expect(getAssistantTurnCopyData(second, { isStreaming: true })).toBeNull();
  expect(getAssistantTurnCopyData(second)).toBe("second answer");
});

test("null copy data is not cached for a reference", () => {
  // A turn with no copyable AI text must keep recomputing (and stay null)
  // rather than a cached null hiding a later value — the same array can be
  // re-used once messages are appended to a rebuilt group.
  const messages = [
    { id: "human-1", type: "human", content: "hi" },
  ] as Message[];

  expect(getAssistantTurnCopyData(messages)).toBeNull();
  expect(getAssistantTurnCopyData(messages)).toBeNull();
});

test("marks the latest assistant message as streaming", () => {
  const messages = [
    {
      id: "human-1",
      type: "human",
      content: "Hello",
    },
    {
      id: "ai-1",
      type: "ai",
      content: "Still generating",
    },
  ] as Message[];
  const groups = getMessageGroups(messages);
  const assistantGroupIndex = groups.findIndex(
    (group) => group.type === "assistant",
  );

  expect(
    isAssistantMessageGroupStreaming(
      groups[assistantGroupIndex]?.messages ?? [],
      getStreamingMessageLookup(messages, true, () => ({
        streamMetadata: { langgraph_node: "agent" },
      })),
    ),
  ).toBe(true);
  expect(
    isAssistantMessageGroupStreaming(
      groups[assistantGroupIndex]?.messages ?? [],
      getStreamingMessageLookup(messages, false, () => ({
        streamMetadata: { langgraph_node: "agent" },
      })),
    ),
  ).toBe(false);
});

test("compares stream metadata snapshots by keys and metadata identity", () => {
  const identifiedMessage = {
    id: "ai-1",
    type: "ai",
    content: "Completed answer",
  } as Message;
  const anonymousMessage = {
    type: "ai",
    content: "Anonymous answer",
  } as Message;
  const identifiedMetadata = { langgraph_node: "agent" };
  const anonymousMetadata = { langgraph_node: "agent" };
  const messages = [identifiedMessage, anonymousMessage];
  const snapshot = getStreamMetadataSnapshot(messages, (message) => ({
    streamMetadata:
      message === identifiedMessage ? identifiedMetadata : anonymousMetadata,
  }));
  const equivalentSnapshot = getStreamMetadataSnapshot(messages, (message) => ({
    streamMetadata:
      message === identifiedMessage ? identifiedMetadata : anonymousMetadata,
  }));
  const changedSnapshot = getStreamMetadataSnapshot(messages, (message) => ({
    streamMetadata:
      message === identifiedMessage
        ? { ...identifiedMetadata }
        : anonymousMetadata,
  }));
  const missingSnapshot = getStreamMetadataSnapshot(
    [identifiedMessage],
    () => ({ streamMetadata: identifiedMetadata }),
  );

  expect(areStreamMetadataSnapshotsEqual(snapshot, equivalentSnapshot)).toBe(
    true,
  );
  expect(areStreamMetadataSnapshotsEqual(snapshot, changedSnapshot)).toBe(
    false,
  );
  expect(areStreamMetadataSnapshotsEqual(snapshot, missingSnapshot)).toBe(
    false,
  );
});

test("ignores stream metadata retained from a completed turn", () => {
  const completedMetadata = { langgraph_node: "agent", langgraph_step: 1 };
  const activeMetadata = { langgraph_node: "agent", langgraph_step: 2 };
  const completedMessages = [
    {
      id: "human-1",
      type: "human",
      content: "Hello",
    },
    {
      id: "ai-1",
      type: "ai",
      content: "Completed answer",
    },
  ] as Message[];
  const settledMetadata = getStreamMetadataSnapshot(
    completedMessages,
    (message) =>
      message.id === "ai-1" ? { streamMetadata: completedMetadata } : undefined,
  );
  const messages = [
    ...completedMessages,
    {
      id: "human-2",
      type: "human",
      content: "Continue",
    },
    {
      id: "ai-2",
      type: "ai",
      content: "Still generating",
    },
  ] as Message[];
  const groups = getMessageGroups(messages).filter(
    (group) => group.type === "assistant",
  );
  const streamingMessages = getStreamingMessageLookup(
    messages,
    true,
    (message) => {
      if (message.id === "ai-1") {
        return { streamMetadata: completedMetadata };
      }
      if (message.id === "ai-2") {
        return { streamMetadata: activeMetadata };
      }
      return undefined;
    },
    settledMetadata,
  );

  expect(
    isAssistantMessageGroupStreaming(
      groups[0]?.messages ?? [],
      streamingMessages,
    ),
  ).toBe(false);
  expect(
    isAssistantMessageGroupStreaming(
      groups[1]?.messages ?? [],
      streamingMessages,
    ),
  ).toBe(true);
});

test("treats updated metadata for the same message id as active", () => {
  const message = {
    id: "ai-1",
    type: "ai",
    content: "Partial answer",
  } as Message;
  const completedMetadata = { langgraph_node: "agent", langgraph_step: 1 };
  const activeMetadata = { langgraph_node: "agent", langgraph_step: 2 };
  const settledMetadata = getStreamMetadataSnapshot([message], () => ({
    streamMetadata: completedMetadata,
  }));

  expect(
    isAssistantMessageGroupStreaming(
      [message],
      getStreamingMessageLookup(
        [message],
        true,
        () => ({ streamMetadata: activeMetadata }),
        settledMetadata,
      ),
    ),
  ).toBe(true);
});

test("keeps previous assistant copyable while waiting for a new visible answer", () => {
  const messages = [
    {
      id: "human-1",
      type: "human",
      content: "Hello",
    },
    {
      id: "ai-1",
      type: "ai",
      content: "Completed answer",
    },
    {
      id: "opt-human-1",
      type: "human",
      content: "Continue",
    },
  ] as Message[];
  const groups = getMessageGroups(messages);
  const assistantGroupIndex = groups.findIndex(
    (group) => group.type === "assistant",
  );

  expect(
    isAssistantMessageGroupStreaming(
      groups[assistantGroupIndex]?.messages ?? [],
      getStreamingMessageLookup(messages, true),
    ),
  ).toBe(false);
});

test("keeps previous assistant copyable while a hidden send is starting", () => {
  const messages = [
    {
      id: "human-1",
      type: "human",
      content: "Hello",
    },
    {
      id: "ai-1",
      type: "ai",
      content: "Completed answer",
    },
  ] as Message[];
  const groups = getMessageGroups(messages);
  const assistantGroupIndex = groups.findIndex(
    (group) => group.type === "assistant",
  );

  expect(
    isAssistantMessageGroupStreaming(
      groups[assistantGroupIndex]?.messages ?? [],
      getStreamingMessageLookup(messages, true),
    ),
  ).toBe(false);
});

test("keeps previous assistant copyable after a hidden send is appended", () => {
  const messages = [
    {
      id: "human-1",
      type: "human",
      content: "Hello",
    },
    {
      id: "ai-1",
      type: "ai",
      content: "Completed answer",
    },
    {
      id: "human-hidden",
      type: "human",
      content: "Save this agent",
      additional_kwargs: { hide_from_ui: true },
    },
  ] as Message[];
  const groups = getMessageGroups(messages);
  const assistantGroupIndex = groups.findIndex(
    (group) => group.type === "assistant",
  );

  expect(
    isAssistantMessageGroupStreaming(
      groups[assistantGroupIndex]?.messages ?? [],
      getStreamingMessageLookup(messages, true),
    ),
  ).toBe(false);
});

test("uses stream metadata to identify an assistant before optimistic input", () => {
  const messages = [
    {
      id: "human-1",
      type: "human",
      content: "Hello",
    },
    {
      id: "ai-1",
      type: "ai",
      content: "Completed answer",
    },
    {
      id: "ai-2",
      type: "ai",
      content: "Still generating",
    },
    {
      id: "opt-human-1",
      type: "human",
      content: "Continue",
    },
  ] as Message[];
  const assistantGroups = getMessageGroups(messages).filter(
    (group) => group.type === "assistant",
  );
  const groups = getMessageGroups(messages);
  const assistantGroupIndexes = groups
    .map((group, index) => (group.type === "assistant" ? index : -1))
    .filter((index) => index >= 0);

  expect(
    isAssistantMessageGroupStreaming(
      groups[assistantGroupIndexes[0] ?? -1]?.messages ?? [],
      getStreamingMessageLookup(messages, true, (message) =>
        message.id === "ai-2"
          ? { streamMetadata: { langgraph_node: "agent" } }
          : undefined,
      ),
    ),
  ).toBe(false);
  expect(
    isAssistantMessageGroupStreaming(
      groups[assistantGroupIndexes[1] ?? -1]?.messages ?? [],
      getStreamingMessageLookup(messages, true, (message) =>
        message.id === "ai-2"
          ? { streamMetadata: { langgraph_node: "agent" } }
          : undefined,
      ),
    ),
  ).toBe(true);
  expect(assistantGroups.map((group) => group.id)).toEqual(["ai-1", "ai-2"]);
});

test("does not mark a completed assistant group streaming from a later processing group", () => {
  const messages = [
    {
      id: "human-1",
      type: "human",
      content: "Hello",
    },
    {
      id: "ai-1",
      type: "ai",
      content: "Visible answer",
    },
    {
      id: "ai-2",
      type: "ai",
      content: "",
      tool_calls: [{ id: "tool-1", name: "web_search", args: {} }],
    },
  ] as Message[];
  const groups = getMessageGroups(messages);
  const assistantGroupIndex = groups.findIndex(
    (group) => group.type === "assistant",
  );

  expect(groups.map((group) => group.type)).toEqual([
    "human",
    "assistant",
    "assistant:processing",
  ]);
  expect(
    isAssistantMessageGroupStreaming(
      groups[assistantGroupIndex]?.messages ?? [],
      getStreamingMessageLookup(messages, true, (message) =>
        message.id === "ai-2"
          ? { streamMetadata: { langgraph_node: "agent" } }
          : undefined,
      ),
    ),
  ).toBe(false);
});

test("keeps streaming assistant hidden when a hidden control message follows it", () => {
  const messages = [
    {
      id: "human-1",
      type: "human",
      content: "Hello",
    },
    {
      id: "ai-1",
      type: "ai",
      content: "Still generating",
    },
    {
      id: "human-hidden",
      type: "human",
      content: "Save this agent",
      additional_kwargs: { hide_from_ui: true },
    },
  ] as Message[];
  const groups = getMessageGroups(messages);
  const assistantGroupIndex = groups.findIndex(
    (group) => group.type === "assistant",
  );

  expect(
    isAssistantMessageGroupStreaming(
      groups[assistantGroupIndex]?.messages ?? [],
      getStreamingMessageLookup(messages, true, (message) =>
        message.id === "ai-1"
          ? { streamMetadata: { langgraph_node: "agent" } }
          : undefined,
      ),
    ),
  ).toBe(true);
});
