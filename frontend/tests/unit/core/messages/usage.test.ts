import type { Message } from "@langchain/langgraph-sdk";
import { expect, test } from "vitest";

import {
  accumulateUsage,
  addUsage,
  formatTokenCount,
  getUsageMetadata,
  hasNonZeroUsage,
  selectHeaderTokenUsage,
  type TokenUsage,
} from "@/core/messages/usage";
import {
  getAssistantTurnUsageMessages,
  getMessageGroups,
} from "@/core/messages/utils";

test("accumulates each AI message usage only once by message id", () => {
  const aiMessage = {
    id: "ai-1",
    type: "ai",
    content: "Answer",
    usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
  } as Message;

  expect(accumulateUsage([aiMessage, aiMessage])).toEqual({
    inputTokens: 10,
    outputTokens: 5,
    totalTokens: 15,
  });
});

test("counts later usage-bearing snapshots for the same AI message id", () => {
  const earlySnapshot = {
    id: "ai-1",
    type: "ai",
    content: "Streaming...",
  } as Message;
  const completedSnapshot = {
    id: "ai-1",
    type: "ai",
    content: "Complete answer",
    usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
  } as Message;

  expect(accumulateUsage([earlySnapshot, completedSnapshot])).toEqual({
    inputTokens: 10,
    outputTokens: 5,
    totalTokens: 15,
  });
});

test("keeps header and per-turn aggregation consistent for duplicated UI groups", () => {
  const messages = [
    {
      id: "human-1",
      type: "human",
      content: "Explain this",
    },
    {
      id: "ai-1",
      type: "ai",
      content: "<think>checking context</think>Final answer",
      usage_metadata: { input_tokens: 20, output_tokens: 7, total_tokens: 27 },
    },
  ] as Message[];

  const groups = getMessageGroups(messages);
  const usageMessagesByGroupIndex = getAssistantTurnUsageMessages(groups);
  const turnUsageMessages = usageMessagesByGroupIndex.at(-1);

  expect(groups.map((group) => group.type)).toEqual([
    "human",
    "assistant:processing",
    "assistant",
  ]);
  expect(turnUsageMessages?.map((message) => message.id)).toEqual([
    "ai-1",
    "ai-1",
  ]);
  expect(accumulateUsage(messages)).toEqual(
    accumulateUsage(turnUsageMessages!),
  );
  expect(accumulateUsage(turnUsageMessages!)).toEqual({
    inputTokens: 20,
    outputTokens: 7,
    totalTokens: 27,
  });
});

test("prefers backend thread usage for header totals", () => {
  const messages = [
    {
      id: "ai-visible",
      type: "ai",
      content: "Visible answer",
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];

  expect(
    selectHeaderTokenUsage({
      backendUsage: { inputTokens: 100, outputTokens: 50, totalTokens: 150 },
      messages,
    }),
  ).toEqual({
    inputTokens: 100,
    outputTokens: 50,
    totalTokens: 150,
  });
});

test("adds current in-flight message usage to backend header totals", () => {
  const completedMessages = [
    {
      id: "ai-completed",
      type: "ai",
      content: "Completed answer",
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
    {
      id: "ai-pending",
      type: "ai",
      content: "Streaming answer",
      usage_metadata: { input_tokens: 4, output_tokens: 6, total_tokens: 10 },
    },
  ] as Message[];

  expect(
    selectHeaderTokenUsage({
      backendUsage: { inputTokens: 100, outputTokens: 50, totalTokens: 150 },
      messages: completedMessages,
      pendingMessages: [completedMessages[1]!],
    }),
  ).toEqual({
    inputTokens: 104,
    outputTokens: 56,
    totalTokens: 160,
  });
});

test("falls back to visible messages when backend usage is unavailable or zero", () => {
  const messages = [
    {
      id: "ai-visible",
      type: "ai",
      content: "Visible answer",
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];

  expect(
    selectHeaderTokenUsage({
      backendUsage: null,
      messages,
    }),
  ).toEqual({
    inputTokens: 10,
    outputTokens: 5,
    totalTokens: 15,
  });
  expect(
    selectHeaderTokenUsage({
      backendUsage: { inputTokens: 0, outputTokens: 0, totalTokens: 0 },
      messages,
    }),
  ).toEqual({
    inputTokens: 10,
    outputTokens: 5,
    totalTokens: 15,
  });
});

// ---------------------------------------------------------------------------
// getUsageMetadata
// ---------------------------------------------------------------------------

test("getUsageMetadata returns null for non-AI messages", () => {
  const message = { type: "human", content: "hello" } as Message;
  expect(getUsageMetadata(message)).toBeNull();
});

test("getUsageMetadata returns null when usage_metadata is absent", () => {
  const message = { type: "ai", content: "answer" } as Message;
  expect(getUsageMetadata(message)).toBeNull();
});

test("getUsageMetadata extracts token counts from usage_metadata", () => {
  const message = {
    type: "ai",
    content: "answer",
    usage_metadata: { input_tokens: 10, output_tokens: 20, total_tokens: 30 },
  } as unknown as Message;
  expect(getUsageMetadata(message)).toEqual({
    inputTokens: 10,
    outputTokens: 20,
    totalTokens: 30,
  });
});

test("getUsageMetadata defaults missing token counts to zero", () => {
  const message = {
    type: "ai",
    content: "answer",
    usage_metadata: {},
  } as unknown as Message;
  expect(getUsageMetadata(message)).toEqual({
    inputTokens: 0,
    outputTokens: 0,
    totalTokens: 0,
  });
});

// ---------------------------------------------------------------------------
// hasNonZeroUsage
// ---------------------------------------------------------------------------

test("hasNonZeroUsage returns false for null", () => {
  expect(hasNonZeroUsage(null)).toBe(false);
});

test("hasNonZeroUsage returns false for undefined", () => {
  expect(hasNonZeroUsage(undefined)).toBe(false);
});

test("hasNonZeroUsage returns false for zero usage", () => {
  expect(
    hasNonZeroUsage({ inputTokens: 0, outputTokens: 0, totalTokens: 0 }),
  ).toBe(false);
});

test("hasNonZeroUsage returns true when inputTokens > 0", () => {
  expect(
    hasNonZeroUsage({ inputTokens: 10, outputTokens: 0, totalTokens: 10 }),
  ).toBe(true);
});

test("hasNonZeroUsage returns true when outputTokens > 0", () => {
  expect(
    hasNonZeroUsage({ inputTokens: 0, outputTokens: 5, totalTokens: 5 }),
  ).toBe(true);
});

test("hasNonZeroUsage returns true when totalTokens > 0", () => {
  expect(
    hasNonZeroUsage({ inputTokens: 0, outputTokens: 0, totalTokens: 1 }),
  ).toBe(true);
});

// ---------------------------------------------------------------------------
// addUsage
// ---------------------------------------------------------------------------

test("addUsage sums both TokenUsage objects", () => {
  const base: TokenUsage = {
    inputTokens: 10,
    outputTokens: 20,
    totalTokens: 30,
  };
  const delta: TokenUsage = { inputTokens: 5, outputTokens: 3, totalTokens: 8 };
  expect(addUsage(base, delta)).toEqual({
    inputTokens: 15,
    outputTokens: 23,
    totalTokens: 38,
  });
});

test("addUsage with zero delta returns the same values", () => {
  const base: TokenUsage = {
    inputTokens: 10,
    outputTokens: 20,
    totalTokens: 30,
  };
  const zero: TokenUsage = { inputTokens: 0, outputTokens: 0, totalTokens: 0 };
  expect(addUsage(base, zero)).toEqual(base);
});

// ---------------------------------------------------------------------------
// formatTokenCount
// ---------------------------------------------------------------------------

test("formatTokenCount formats numbers below 10,000 with locale separators", () => {
  expect(formatTokenCount(0)).toBe("0");
  expect(formatTokenCount(1)).toBe("1");
  expect(formatTokenCount(999)).toBe("999");
  expect(formatTokenCount(1234)).toBe("1,234");
  expect(formatTokenCount(9999)).toBe("9,999");
});

test("formatTokenCount formats numbers >= 10,000 as K notation", () => {
  expect(formatTokenCount(10000)).toBe("10.0K");
  expect(formatTokenCount(12345)).toBe("12.3K");
  expect(formatTokenCount(99999)).toBe("100.0K");
  expect(formatTokenCount(1234567)).toBe("1234.6K");
});

test("formatTokenCount handles exactly 9999", () => {
  expect(formatTokenCount(9999)).toBe("9,999");
});

test("formatTokenCount handles exactly 10000", () => {
  expect(formatTokenCount(10000)).toBe("10.0K");
});

// ---------------------------------------------------------------------------
// accumulateUsage – additional edge cases
// ---------------------------------------------------------------------------

test("accumulateUsage returns null when no messages have usage", () => {
  const messages = [
    { type: "human", content: "hello" } as Message,
    { type: "ai", content: "hi" } as Message,
  ];
  expect(accumulateUsage(messages)).toBeNull();
});

test("accumulateUsage returns null for empty messages array", () => {
  expect(accumulateUsage([])).toBeNull();
});

test("accumulateUsage sums across multiple AI messages with different ids", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "a",
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
    {
      id: "ai-2",
      type: "ai",
      content: "b",
      usage_metadata: { input_tokens: 20, output_tokens: 10, total_tokens: 30 },
    },
  ] as Message[];
  expect(accumulateUsage(messages)).toEqual({
    inputTokens: 30,
    outputTokens: 15,
    totalTokens: 45,
  });
});

// ---------------------------------------------------------------------------
// selectHeaderTokenUsage – additional edge cases
// ---------------------------------------------------------------------------

test("selectHeaderTokenUsage returns null when no messages and no backend", () => {
  expect(
    selectHeaderTokenUsage({ backendUsage: null, messages: [] }),
  ).toBeNull();
});

test("selectHeaderTokenUsage returns backend usage when pendingMessages is empty array", () => {
  const backend = { inputTokens: 100, outputTokens: 50, totalTokens: 150 };
  expect(
    selectHeaderTokenUsage({
      backendUsage: backend,
      messages: [],
      pendingMessages: [],
    }),
  ).toEqual(backend);
});
