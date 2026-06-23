import { describe, expect, test, vi } from "vitest";

import {
  threadTokenUsageQueryKey,
  threadTokenUsageToTokenUsage,
} from "@/core/threads/token-usage";
import type { ThreadTokenUsageResponse } from "@/core/threads/types";

describe("threadTokenUsageQueryKey", () => {
  test('returns ["thread-token-usage", undefined] with no argument', () => {
    expect(threadTokenUsageQueryKey()).toEqual([
      "thread-token-usage",
      undefined,
    ]);
  });

  test('returns ["thread-token-usage", "abc"] with string argument', () => {
    expect(threadTokenUsageQueryKey("abc")).toEqual([
      "thread-token-usage",
      "abc",
    ]);
  });

  test("returns tuple with null argument", () => {
    expect(threadTokenUsageQueryKey(null)).toEqual([
      "thread-token-usage",
      null,
    ]);
  });
});

describe("threadTokenUsageToTokenUsage", () => {
  test("returns null when usage is null", () => {
    expect(threadTokenUsageToTokenUsage(null)).toBeNull();
  });

  test("returns null when usage is undefined", () => {
    expect(threadTokenUsageToTokenUsage(undefined)).toBeNull();
  });

  test("maps backend response fields to UI token usage", () => {
    const response: ThreadTokenUsageResponse = {
      thread_id: "thread-1",
      total_input_tokens: 90,
      total_output_tokens: 60,
      total_tokens: 150,
      total_runs: 2,
      by_model: { unknown: { tokens: 150, runs: 2 } },
      by_caller: {
        lead_agent: 120,
        subagent: 25,
        middleware: 5,
      },
    };

    expect(threadTokenUsageToTokenUsage(response)).toEqual({
      inputTokens: 90,
      outputTokens: 60,
      totalTokens: 150,
    });
  });

  test("uses nullish coalescing for missing fields (empty object)", () => {
    // When fields are missing/undefined, ?? 0 defaults to 0
    const response = {} as ThreadTokenUsageResponse;
    expect(threadTokenUsageToTokenUsage(response)).toEqual({
      inputTokens: 0,
      outputTokens: 0,
      totalTokens: 0,
    });
  });

  test("handles partial response with some undefined fields", () => {
    const response = {
      thread_id: "thread-2",
      total_input_tokens: undefined,
      total_output_tokens: 30,
      total_tokens: undefined,
    } as unknown as ThreadTokenUsageResponse;

    expect(threadTokenUsageToTokenUsage(response)).toEqual({
      inputTokens: 0,
      outputTokens: 30,
      totalTokens: 0,
    });
  });

  test("handles zero token values", () => {
    const response: ThreadTokenUsageResponse = {
      thread_id: "thread-3",
      total_input_tokens: 0,
      total_output_tokens: 0,
      total_tokens: 0,
      total_runs: 0,
      by_model: {},
      by_caller: { lead_agent: 0, subagent: 0, middleware: 0 },
    };

    expect(threadTokenUsageToTokenUsage(response)).toEqual({
      inputTokens: 0,
      outputTokens: 0,
      totalTokens: 0,
    });
  });
});
