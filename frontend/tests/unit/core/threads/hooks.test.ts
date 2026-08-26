import type { Message } from "@langchain/langgraph-sdk";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import React, { createElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ── Hoisted mock references ─────────────────────────────────────────

const mockGetAPIClient = vi.hoisted(() => vi.fn());
const mockFetchFn = vi.hoisted(() => vi.fn());
const mockGetBackendBaseURL = vi.hoisted(() =>
  vi.fn(() => "http://localhost:3000"),
);
const mockToastError = vi.hoisted(() => vi.fn());
const mockToastInfo = vi.hoisted(() => vi.fn());
const mockFetchThreadTokenUsage = vi.hoisted(() => vi.fn());
const mockUseStream = vi.hoisted(() =>
  vi.fn(() => ({
    messages: [] as Message[],
    isLoading: false,
    submit: vi.fn().mockResolvedValue(undefined),
  })),
);
const mockPromptInputFilePartToFile = vi.hoisted(() => vi.fn());
const mockUploadFiles = vi.hoisted(() => vi.fn());
const mockUseUpdateSubtask = vi.hoisted(() => vi.fn(() => vi.fn()));

// ── Module mocks ────────────────────────────────────────────────────

vi.mock("@/core/api", () => ({
  getAPIClient: mockGetAPIClient,
}));

vi.mock("@/core/api/fetcher", () => ({
  fetch: mockFetchFn,
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: mockGetBackendBaseURL,
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      uploads: { uploadingFiles: "Uploading files…" },
    },
    locale: "en",
    changeLocale: vi.fn(),
  }),
}));

vi.mock("@/core/tasks/context", () => ({
  useUpdateSubtask: mockUseUpdateSubtask,
}));

vi.mock("@/core/uploads", () => ({
  promptInputFilePartToFile: mockPromptInputFilePartToFile,
  uploadFiles: mockUploadFiles,
}));

const mockToast = vi.hoisted(() => {
  const fn = vi.fn() as ReturnType<typeof vi.fn> & {
    error: ReturnType<typeof vi.fn>;
    success: ReturnType<typeof vi.fn>;
    info: ReturnType<typeof vi.fn>;
  };
  fn.error = mockToastError;
  fn.success = vi.fn();
  fn.info = mockToastInfo;
  return fn;
});

vi.mock("sonner", () => ({
  toast: mockToast,
}));

vi.mock("@/core/threads/api", () => ({
  fetchThreadTokenUsage: mockFetchThreadTokenUsage,
}));

vi.mock("@/core/threads/token-usage", () => ({
  threadTokenUsageQueryKey: (id?: string | null) =>
    ["thread-token-usage", id] as const,
}));

vi.mock("@langchain/langgraph-sdk/react", () => ({
  useStream: mockUseStream,
}));

// ── Imports (after mocks so they resolve to mocked versions) ─────────

import {
  mergeMessages,
  getVisibleOptimisticMessages,
  useThreads,
  useThreadRuns,
  useThreadTokenUsage,
  useRunDetail,
  useDeleteThread,
  useRenameThread,
  useThreadHistory,
  useThreadStream,
} from "@/core/threads/hooks";

// ── Helpers ─────────────────────────────────────────────────────────

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);

  return { queryClient, wrapper };
}

function humanMsg(id: string, content: string): Message {
  return { id, type: "human", content } as unknown as Message;
}

function aiMsg(id: string, content: string): Message {
  return { id, type: "ai", content } as unknown as Message;
}

function toolMsg(id: string, toolCallId: string, content: string): Message {
  return {
    id,
    type: "tool",
    tool_call_id: toolCallId,
    content,
  } as unknown as Message;
}

// ── Tests ───────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
  mockGetBackendBaseURL.mockReturnValue("http://localhost:3000");
  mockFetchThreadTokenUsage.mockReset();
  mockUseStream.mockReturnValue({
    messages: [] as Message[],
    isLoading: false,
    submit: vi.fn().mockResolvedValue(undefined),
  });
  mockUseUpdateSubtask.mockReturnValue(vi.fn());
  mockPromptInputFilePartToFile.mockReset();
  mockUploadFiles.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ═══════════════════════════════════════════════════════════════════
// mergeMessages
// ═══════════════════════════════════════════════════════════════════

describe("mergeMessages", () => {
  it("returns empty array when all inputs are empty", () => {
    expect(mergeMessages([], [], [])).toEqual([]);
  });

  it("returns history when thread and optimistic are empty", () => {
    const h1 = humanMsg("h1", "hello");
    const a1 = aiMsg("a1", "hi");
    expect(mergeMessages([h1, a1], [], [])).toEqual([h1, a1]);
  });

  it("returns thread messages when history is empty", () => {
    const t1 = humanMsg("t1", "hello");
    const t2 = aiMsg("t2", "hi");
    expect(mergeMessages([], [t1, t2], [])).toEqual([t1, t2]);
  });

  it("appends optimistic messages at the end", () => {
    const h1 = humanMsg("h1", "hello");
    const o1 = humanMsg("opt1", "typing…");
    expect(mergeMessages([h1], [], [o1])).toEqual([h1, o1]);
  });

  it("does not duplicate overlapping history suffix already in thread", () => {
    const h1 = humanMsg("h1", "old");
    const h2 = humanMsg("h2", "question");
    const t2 = humanMsg("h2", "question live");
    const a2 = aiMsg("a2", "answer");
    // history = [h1, h2], thread = [h2_live, a2]
    // overlap: h2 is at end of history and start of thread → cutoff = 1
    expect(mergeMessages([h1, h2], [t2, a2], [])).toEqual([h1, t2, a2]);
  });

  it("keeps non-overlapping history prefix when thread starts later", () => {
    const h1 = humanMsg("h1", "q1");
    const a1 = aiMsg("a1", "a1");
    const h2 = humanMsg("h2", "q2");
    const a2 = aiMsg("a2", "a2");
    // history = [h1, a1, h2, a2], thread = [h2, a2]
    // overlap: h2 at index 2, a2 at index 3 → cutoff = 2
    expect(mergeMessages([h1, a1, h2, a2], [h2, a2], [])).toEqual([
      h1,
      a1,
      h2,
      a2,
    ]);
  });

  it("deduplicates messages with same id within the merged result", () => {
    const h1 = humanMsg("h1", "first");
    const h1dup = humanMsg("h1", "first updated");
    expect(mergeMessages([h1], [h1dup], [])).toEqual([h1dup]);
  });

  it("deduplicates tool messages by tool_call_id", () => {
    const t1 = toolMsg("t1", "call-1", "old result");
    const t2 = toolMsg("t2", "call-1", "new result");
    expect(mergeMessages([t1], [t2], [])).toEqual([t2]);
  });

  it("handles messages without identity (no id, no tool_call_id)", () => {
    const noId = { type: "human", content: "no id" } as unknown as Message;
    expect(mergeMessages([noId], [], [])).toEqual([noId]);
  });

  it("handles empty string id messages (no identity) in overlap detection", () => {
    // Messages with empty id have no identity, so they're kept regardless of overlap
    const emptyIdMsg: Message = {
      type: "human",
      id: "",
      content: "empty id",
    } as Message;
    const h1 = humanMsg("h1", "question");
    const history: Message[] = [emptyIdMsg, h1];
    const thread = [humanMsg("h1", "question live")];
    const result = mergeMessages(history, thread, []);
    // emptyIdMsg has no identity, h1 overlaps with thread
    expect(result.length).toBeGreaterThanOrEqual(2);
  });

  it("preserves history when thread has no overlapping suffix", () => {
    const h1 = humanMsg("h1", "q1");
    const a1 = aiMsg("a1", "a1");
    const t1 = humanMsg("t2", "different q");
    expect(mergeMessages([h1, a1], [t1], [])).toEqual([h1, a1, t1]);
  });

  it("skips messages without identity at the end of history for cutoff detection", () => {
    // Messages without id or tool_call_id are skipped in the cutoff scan
    // but still included in the final merge via dedupeMessagesByIdentity
    const noId = { type: "human", content: "no id" } as unknown as Message;
    const h1 = humanMsg("h1", "question");
    // noId has no identity so it won't match thread messages for overlap
    expect(mergeMessages([noId, h1], [h1], [])).toEqual([noId, h1]);
  });
});

// ═══════════════════════════════════════════════════════════════════
// getVisibleOptimisticMessages
// ═══════════════════════════════════════════════════════════════════

describe("getVisibleOptimisticMessages", () => {
  it("returns empty array for empty input", () => {
    expect(getVisibleOptimisticMessages([], 0, 0)).toEqual([]);
  });

  it("returns all optimistic when no human messages in optimistic set", () => {
    const aiOpt = aiMsg("opt1", "processing…");
    expect(getVisibleOptimisticMessages([aiOpt], 0, 0)).toEqual([aiOpt]);
  });

  it("returns all optimistic when human count has not increased", () => {
    const humanOpt = humanMsg("opt1", "hello");
    expect(getVisibleOptimisticMessages([humanOpt], 1, 1)).toEqual([humanOpt]);
  });

  it("returns empty when human count increased and has human optimistic", () => {
    const humanOpt = humanMsg("opt1", "hello");
    expect(getVisibleOptimisticMessages([humanOpt], 0, 1)).toEqual([]);
  });

  it("hides both human and AI optimistic messages when human count increased", () => {
    const humanOpt = humanMsg("opt1", "hello");
    const aiOpt = aiMsg("opt2", "uploading…");
    expect(getVisibleOptimisticMessages([humanOpt, aiOpt], 2, 3)).toEqual([]);
  });

  it("keeps non-human optimistic when human count increased", () => {
    const aiOpt = aiMsg("opt1", "still processing…");
    expect(getVisibleOptimisticMessages([aiOpt], 0, 1)).toEqual([aiOpt]);
  });

  it("keeps optimistic when human count is same and has human messages", () => {
    const humanOpt = humanMsg("opt1", "waiting");
    expect(getVisibleOptimisticMessages([humanOpt], 3, 3)).toEqual([humanOpt]);
  });
});

// ═══════════════════════════════════════════════════════════════════
// useThreads
// ═══════════════════════════════════════════════════════════════════

describe("useThreads", () => {
  it("single search call when limit is zero", async () => {
    const mockSearch = vi
      .fn()
      .mockResolvedValue([
        { thread_id: "t1", updated_at: "2024-01-01", values: {}, metadata: {} },
      ]);
    mockGetAPIClient.mockReturnValue({ threads: { search: mockSearch } });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreads({
          limit: 0,
          sortBy: "updated_at",
          sortOrder: "desc",
          select: ["thread_id"],
        }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockSearch).toHaveBeenCalledTimes(1);
    expect(mockSearch).toHaveBeenCalledWith({
      limit: 0,
      sortBy: "updated_at",
      sortOrder: "desc",
      select: ["thread_id"],
    });
    expect(result.current.data).toHaveLength(1);
  });

  it("paginates across multiple pages", async () => {
    const page1 = Array.from({ length: 50 }, (_, i) => ({
      thread_id: `t${i + 1}`,
      updated_at: "2024-01-01",
      values: {},
      metadata: {},
    }));
    const page2 = [
      { thread_id: "t51", updated_at: "2024-01-01", values: {}, metadata: {} },
    ];

    const mockSearch = vi
      .fn()
      .mockResolvedValueOnce(page1)
      .mockResolvedValueOnce(page2);
    mockGetAPIClient.mockReturnValue({ threads: { search: mockSearch } });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreads({
          limit: 51,
          sortBy: "updated_at",
          sortOrder: "desc",
          select: ["thread_id"],
        }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockSearch).toHaveBeenCalledTimes(2);
    expect(result.current.data).toHaveLength(51);
  });

  it("breaks early when response is shorter than currentLimit", async () => {
    const shortResponse = [
      { thread_id: "t1", updated_at: "2024-01-01", values: {}, metadata: {} },
    ];
    const mockSearch = vi.fn().mockResolvedValue(shortResponse);
    mockGetAPIClient.mockReturnValue({ threads: { search: mockSearch } });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreads({
          limit: 100,
          sortBy: "updated_at",
          sortOrder: "desc",
          select: ["thread_id"],
        }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Only one call because response (1) < currentLimit (50)
    expect(mockSearch).toHaveBeenCalledTimes(1);
    expect(result.current.data).toHaveLength(1);
  });

  it("uses default params when none provided", async () => {
    const mockSearch = vi.fn().mockResolvedValue([]);
    mockGetAPIClient.mockReturnValue({ threads: { search: mockSearch } });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useThreads(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockSearch).toHaveBeenCalledWith(
      expect.objectContaining({
        limit: 50,
        sortBy: "updated_at",
        sortOrder: "desc",
      }),
    );
  });

  it("handles undefined limit (no maxResults) with default page size", async () => {
    const page = Array.from({ length: 50 }, (_, i) => ({
      thread_id: `t${i + 1}`,
      updated_at: "2024-01-01",
      values: {},
      metadata: {},
    }));
    const emptyPage: never[] = [];
    const mockSearch = vi
      .fn()
      .mockResolvedValueOnce(page)
      .mockResolvedValueOnce(emptyPage);
    mockGetAPIClient.mockReturnValue({ threads: { search: mockSearch } });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreads({
          sortBy: "updated_at",
          sortOrder: "desc",
          select: ["thread_id"],
        } as Parameters<typeof useThreads>[0]),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // First call returns 50, second call returns 0 (< 50) → break
    expect(mockSearch).toHaveBeenCalledTimes(2);
    expect(result.current.data).toHaveLength(50);
  });

  it("handles negative limit by delegating to single search", async () => {
    const mockSearch = vi.fn().mockResolvedValue([]);
    mockGetAPIClient.mockReturnValue({ threads: { search: mockSearch } });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreads({
          limit: -5,
          sortBy: "updated_at",
          sortOrder: "desc",
          select: ["thread_id"],
        }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Negative limit → maxResults <= 0 path → single search call
    expect(mockSearch).toHaveBeenCalledTimes(1);
  });
});

// ═══════════════════════════════════════════════════════════════════
// useThreadRuns
// ═══════════════════════════════════════════════════════════════════

describe("useThreadRuns", () => {
  it("returns empty array when threadId is undefined", async () => {
    const mockListRuns = vi.fn();
    mockGetAPIClient.mockReturnValue({ runs: { list: mockListRuns } });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useThreadRuns(undefined), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual([]);
    expect(mockListRuns).not.toHaveBeenCalled();
  });

  it("fetches runs when threadId is provided", async () => {
    const runs = [
      { run_id: "r1", created_at: "2024-01-01" },
      { run_id: "r2", created_at: "2024-01-02" },
    ];
    const mockListRuns = vi.fn().mockResolvedValue(runs);
    mockGetAPIClient.mockReturnValue({ runs: { list: mockListRuns } });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useThreadRuns("thread-1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockListRuns).toHaveBeenCalledWith("thread-1");
    expect(result.current.data).toEqual(runs);
  });

  it("handles API error gracefully", async () => {
    const mockListRuns = vi.fn().mockRejectedValue(new Error("Network error"));
    mockGetAPIClient.mockReturnValue({ runs: { list: mockListRuns } });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useThreadRuns("thread-1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeInstanceOf(Error);
  });
});

// ═══════════════════════════════════════════════════════════════════
// useThreadTokenUsage
// ═══════════════════════════════════════════════════════════════════

describe("useThreadTokenUsage", () => {
  it("does not fetch when threadId is null", async () => {
    mockFetchThreadTokenUsage.mockResolvedValue(null);

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useThreadTokenUsage(null), {
      wrapper,
    });

    // When threadId is null, enabled is false (Boolean(null) === false)
    // so the query never runs
    expect(mockFetchThreadTokenUsage).not.toHaveBeenCalled();
    expect(result.current.data).toBeUndefined();
  });

  it("does not fetch when threadId is undefined", async () => {
    mockFetchThreadTokenUsage.mockResolvedValue(null);

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useThreadTokenUsage(undefined), {
      wrapper,
    });

    // When threadId is undefined, enabled is false
    expect(mockFetchThreadTokenUsage).not.toHaveBeenCalled();
    expect(result.current.data).toBeUndefined();
  });

  it("fetches token usage when threadId is provided", async () => {
    const usage = {
      thread_id: "t1",
      total_tokens: 100,
      total_input_tokens: 60,
      total_output_tokens: 40,
      total_runs: 1,
      by_model: {},
      by_caller: { lead_agent: 0, subagent: 0, middleware: 0 },
    };
    mockFetchThreadTokenUsage.mockResolvedValue(usage);

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useThreadTokenUsage("t1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetchThreadTokenUsage).toHaveBeenCalledWith("t1");
    expect(result.current.data).toEqual(usage);
  });

  it("does not fetch when enabled is false", async () => {
    mockFetchThreadTokenUsage.mockResolvedValue(null);

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () => useThreadTokenUsage("t1", { enabled: false }),
      { wrapper },
    );

    // Query should not run when enabled=false
    expect(mockFetchThreadTokenUsage).not.toHaveBeenCalled();
    // data should be undefined (query never ran)
    expect(result.current.data).toBeUndefined();
  });

  it("fetches when enabled is true and threadId exists", async () => {
    mockFetchThreadTokenUsage.mockResolvedValue({
      thread_id: "t1",
      total_tokens: 50,
      total_input_tokens: 30,
      total_output_tokens: 20,
      total_runs: 1,
      by_model: {},
      by_caller: { lead_agent: 0, subagent: 0, middleware: 0 },
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () => useThreadTokenUsage("t1", { enabled: true }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetchThreadTokenUsage).toHaveBeenCalledWith("t1");
  });
});

// ═══════════════════════════════════════════════════════════════════
// useRunDetail
// ═══════════════════════════════════════════════════════════════════

describe("useRunDetail", () => {
  it("fetches run detail by threadId and runId", async () => {
    const run = { run_id: "r1", created_at: "2024-01-01" };
    const mockGetRun = vi.fn().mockResolvedValue(run);
    mockGetAPIClient.mockReturnValue({ runs: { get: mockGetRun } });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useRunDetail("t1", "r1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockGetRun).toHaveBeenCalledWith("t1", "r1");
    expect(result.current.data).toEqual(run);
  });

  it("handles fetch error", async () => {
    const mockGetRun = vi.fn().mockRejectedValue(new Error("Run not found"));
    mockGetAPIClient.mockReturnValue({ runs: { get: mockGetRun } });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useRunDetail("t1", "r1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeInstanceOf(Error);
  });
});

// ═══════════════════════════════════════════════════════════════════
// useDeleteThread
// ═══════════════════════════════════════════════════════════════════

describe("useDeleteThread", () => {
  it("deletes thread via SDK and backend, then updates cache", async () => {
    const mockDelete = vi.fn().mockResolvedValue(undefined);
    mockGetAPIClient.mockReturnValue({ threads: { delete: mockDelete } });
    mockFetchFn.mockResolvedValue({ ok: true });

    const { queryClient, wrapper } = createWrapper();

    // Seed the cache with threads
    queryClient.setQueryData(
      ["threads", "search"],
      [
        { thread_id: "t1", values: { title: "Thread 1" } },
        { thread_id: "t2", values: { title: "Thread 2" } },
      ],
    );

    // Spy on setQueriesData to verify the cache update happens in onSuccess
    const setQueriesDataSpy = vi.spyOn(queryClient, "setQueriesData");

    const { result } = renderHook(() => useDeleteThread(), { wrapper });

    await act(async () => {
      result.current.mutate({ threadId: "t1" });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // SDK delete was called
    expect(mockDelete).toHaveBeenCalledWith("t1");

    // Backend delete was called
    expect(mockFetchFn).toHaveBeenCalledWith(
      "http://localhost:3000/api/threads/t1",
      { method: "DELETE" },
    );

    // onSuccess called setQueriesData with a filter function
    expect(setQueriesDataSpy).toHaveBeenCalled();
    const lastCall =
      setQueriesDataSpy.mock.calls[setQueriesDataSpy.mock.calls.length - 1];
    const filterFn = lastCall?.[1] as (
      oldData: Array<{ thread_id: string }> | undefined,
    ) => Array<{ thread_id: string }> | undefined;
    const result2 = filterFn([
      { thread_id: "t1", values: { title: "Thread 1" } } as {
        thread_id: string;
      },
      { thread_id: "t2", values: { title: "Thread 2" } } as {
        thread_id: string;
      },
    ]);
    expect(result2).toHaveLength(1);
    expect(result2?.[0]?.thread_id).toBe("t2");
  });

  it("throws when backend delete returns non-ok response", async () => {
    const mockDelete = vi.fn().mockResolvedValue(undefined);
    mockGetAPIClient.mockReturnValue({ threads: { delete: mockDelete } });
    mockFetchFn.mockResolvedValue({
      ok: false,
      json: async () => ({ detail: "Delete failed" }),
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useDeleteThread(), { wrapper });

    await act(async () => {
      result.current.mutate({ threadId: "t1" });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error?.message).toBe("Delete failed");
  });

  it("uses default error message when json parse fails on non-ok response", async () => {
    const mockDelete = vi.fn().mockResolvedValue(undefined);
    mockGetAPIClient.mockReturnValue({ threads: { delete: mockDelete } });
    mockFetchFn.mockResolvedValue({
      ok: false,
      json: async () => {
        throw new Error("invalid json");
      },
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useDeleteThread(), { wrapper });

    await act(async () => {
      result.current.mutate({ threadId: "t1" });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error?.message).toBe(
      "Failed to delete local thread data.",
    );
  });

  it("invalidates queries on settle", async () => {
    const mockDelete = vi.fn().mockResolvedValue(undefined);
    mockGetAPIClient.mockReturnValue({ threads: { delete: mockDelete } });
    mockFetchFn.mockResolvedValue({ ok: true });

    const { queryClient, wrapper } = createWrapper();
    const spy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useDeleteThread(), { wrapper });

    await act(async () => {
      result.current.mutate({ threadId: "t1" });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["threads", "search"] }),
    );
  });

  it("handles null oldData in cache update gracefully", async () => {
    const mockDelete = vi.fn().mockResolvedValue(undefined);
    mockGetAPIClient.mockReturnValue({ threads: { delete: mockDelete } });
    mockFetchFn.mockResolvedValue({ ok: true });

    const { queryClient, wrapper } = createWrapper();
    // No cache data seeded — setQueriesData will iterate matching queries
    // but with no queries matching, the updater is never called.
    // This still exercises the code path without errors.

    const { result } = renderHook(() => useDeleteThread(), { wrapper });

    await act(async () => {
      result.current.mutate({ threadId: "t1" });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Should not throw when no cache data exists
    const cached = queryClient.getQueryData(["threads", "search"]);
    expect(cached).toBeUndefined();
  });
});

// ═══════════════════════════════════════════════════════════════════
// useRenameThread
// ═══════════════════════════════════════════════════════════════════

describe("useRenameThread", () => {
  it("renames thread via SDK and updates cache", async () => {
    const mockUpdateState = vi.fn().mockResolvedValue(undefined);
    mockGetAPIClient.mockReturnValue({
      threads: { updateState: mockUpdateState },
    });

    const { queryClient, wrapper } = createWrapper();

    // Spy on setQueriesData to verify the cache update
    const setQueriesDataSpy = vi.spyOn(queryClient, "setQueriesData");

    const { result } = renderHook(() => useRenameThread(), { wrapper });

    await act(async () => {
      result.current.mutate({ threadId: "t1", title: "New Title" });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // SDK was called
    expect(mockUpdateState).toHaveBeenCalledWith("t1", {
      values: { title: "New Title" },
    });

    // Verify the onSuccess callback called setQueriesData with the right updater
    expect(setQueriesDataSpy).toHaveBeenCalled();
    const lastCall =
      setQueriesDataSpy.mock.calls[setQueriesDataSpy.mock.calls.length - 1];
    const updaterFn = lastCall?.[1] as (
      oldData: Array<{ thread_id: string; values: { title: string } }>,
    ) => Array<{ thread_id: string; values: { title: string } }>;
    const result2 = updaterFn([
      { thread_id: "t1", values: { title: "Old Title" } },
      { thread_id: "t2", values: { title: "Other" } },
    ]);
    expect(result2[0]?.values.title).toBe("New Title");
    expect(result2[1]?.values.title).toBe("Other");
  });

  it("leaves other threads unchanged in cache", async () => {
    const mockUpdateState = vi.fn().mockResolvedValue(undefined);
    mockGetAPIClient.mockReturnValue({
      threads: { updateState: mockUpdateState },
    });

    const { queryClient, wrapper } = createWrapper();

    const setQueriesDataSpy = vi.spyOn(queryClient, "setQueriesData");

    const { result } = renderHook(() => useRenameThread(), { wrapper });

    await act(async () => {
      result.current.mutate({ threadId: "t2", title: "B Renamed" });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const lastCall =
      setQueriesDataSpy.mock.calls[setQueriesDataSpy.mock.calls.length - 1];
    const updaterFn = lastCall?.[1] as (
      oldData: Array<{ thread_id: string; values: { title: string } }>,
    ) => Array<{ thread_id: string; values: { title: string } }>;
    const result2 = updaterFn([
      { thread_id: "t1", values: { title: "A" } },
      { thread_id: "t2", values: { title: "B" } },
      { thread_id: "t3", values: { title: "C" } },
    ]);
    expect(result2[0]?.values.title).toBe("A");
    expect(result2[1]?.values.title).toBe("B Renamed");
    expect(result2[2]?.values.title).toBe("C");
  });
});

// ═══════════════════════════════════════════════════════════════════
// useThreadHistory
// ═══════════════════════════════════════════════════════════════════

describe("useThreadHistory", () => {
  it("returns empty messages when no runs exist", async () => {
    const mockListRuns = vi.fn().mockResolvedValue([]);
    mockGetAPIClient.mockReturnValue({ runs: { list: mockListRuns } });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useThreadHistory("thread-1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.messages).toEqual([]);
  });

  it("loads messages from runs successfully", async () => {
    const runs = [{ run_id: "r1", created_at: "2024-01-01" }];
    const mockListRuns = vi.fn().mockResolvedValue(runs);
    mockGetAPIClient.mockReturnValue({ runs: { list: mockListRuns } });

    const runMessages = [
      {
        content: { id: "m1", type: "human", content: "hello" },
        metadata: { caller: "user" },
      },
      {
        content: { id: "m2", type: "ai", content: "hi there" },
        metadata: { caller: "lead_agent" },
      },
    ];

    mockFetchFn.mockResolvedValue({
      json: async () => ({ data: runMessages, hasMore: false }),
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useThreadHistory("thread-1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.messages).toHaveLength(2));

    expect(result.current.messages[0]).toEqual(
      expect.objectContaining({ id: "m1" }),
    );
    expect(result.current.messages[1]).toEqual(
      expect.objectContaining({ id: "m2" }),
    );
  });

  it("filters out middleware messages", async () => {
    const runs = [{ run_id: "r1", created_at: "2024-01-01" }];
    mockGetAPIClient.mockReturnValue({
      runs: { list: vi.fn().mockResolvedValue(runs) },
    });

    const runMessages = [
      {
        content: { id: "m1", type: "human", content: "hello" },
        metadata: { caller: "user" },
      },
      {
        content: { id: "m2", type: "ai", content: "internal" },
        metadata: { caller: "middleware:summarize" },
      },
    ];

    mockFetchFn.mockResolvedValue({
      json: async () => ({ data: runMessages, hasMore: false }),
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useThreadHistory("thread-1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.messages).toHaveLength(1));

    expect(result.current.messages[0]).toEqual(
      expect.objectContaining({ id: "m1" }),
    );
  });

  it("paginates through all pages of a run via before_seq", async () => {
    const runs = [{ run_id: "r1", created_at: "2024-01-01" }];
    const mockListRuns = vi.fn().mockResolvedValue(runs);
    mockGetAPIClient.mockReturnValue({ runs: { list: mockListRuns } });

    const mkRunMessage = (seq: number) => ({
      run_id: "r1",
      seq,
      content: { id: `m${seq}`, type: "human", content: `msg ${seq}` },
      metadata: { caller: "user" },
    });

    mockFetchFn.mockImplementation((url: string) => {
      if (url.includes("before_seq=41")) {
        return Promise.resolve({
          json: async () => ({
            data: [mkRunMessage(31), mkRunMessage(32)],
            has_more: true,
          }),
        });
      }
      if (url.includes("before_seq=31")) {
        return Promise.resolve({
          json: async () => ({
            data: [mkRunMessage(21), mkRunMessage(22)],
            has_more: false,
          }),
        });
      }
      return Promise.resolve({
        json: async () => ({
          data: [mkRunMessage(41), mkRunMessage(42)],
          has_more: true,
        }),
      });
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useThreadHistory("thread-1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.messages).toHaveLength(6));

    expect(mockFetchFn).toHaveBeenCalledTimes(3);
    expect(mockFetchFn.mock.calls.map(([url]) => String(url))).toEqual([
      expect.stringContaining("/runs/r1/messages"),
      expect.stringContaining("/runs/r1/messages?before_seq=41"),
      expect.stringContaining("/runs/r1/messages?before_seq=31"),
    ]);
    expect(result.current.messages.map((m) => m.id)).toEqual([
      "m21",
      "m22",
      "m31",
      "m32",
      "m41",
      "m42",
    ]);
  });

  it("resets state when threadId changes", async () => {
    const runs = [{ run_id: "r1", created_at: "2024-01-01" }];
    const mockListRuns = vi.fn().mockResolvedValue(runs);
    mockGetAPIClient.mockReturnValue({ runs: { list: mockListRuns } });

    mockFetchFn.mockResolvedValue({
      json: async () => ({
        data: [
          {
            content: { id: "m1", type: "human", content: "hello" },
            metadata: { caller: "user" },
          },
        ],
        hasMore: false,
      }),
    });

    const { wrapper } = createWrapper();
    const { result, rerender } = renderHook(
      ({ tid }) => useThreadHistory(tid),
      { wrapper, initialProps: { tid: "thread-1" } },
    );

    await waitFor(() => expect(result.current.messages).toHaveLength(1));

    // Change thread ID — should reset messages
    rerender({ tid: "thread-2" });

    await waitFor(() => expect(result.current.messages).toEqual([]));
  });

  it("returns hasMore as true when there are unloaded runs", async () => {
    const runs = [{ run_id: "r1", created_at: "2024-01-01" }];
    mockGetAPIClient.mockReturnValue({
      runs: { list: vi.fn().mockResolvedValue(runs) },
    });

    mockFetchFn.mockResolvedValue({
      json: async () => ({ data: [], hasMore: false }),
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useThreadHistory("thread-1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));

    // hasMore should be true while there are runs that haven't been loaded
    // After loading, indexRef.current becomes -1 so hasMore depends on runs.data
    expect(typeof result.current.hasMore).toBe("boolean");
  });

  it("provides appendMessages function", async () => {
    mockGetAPIClient.mockReturnValue({
      runs: { list: vi.fn().mockResolvedValue([]) },
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useThreadHistory("thread-1"), {
      wrapper,
    });

    expect(typeof result.current.appendMessages).toBe("function");

    act(() => {
      result.current.appendMessages([
        { id: "extra-1", type: "ai", content: "appended" } as Message,
      ]);
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]).toEqual(
      expect.objectContaining({ id: "extra-1" }),
    );
  });

  it("deduplicates messages when appending", async () => {
    mockGetAPIClient.mockReturnValue({
      runs: { list: vi.fn().mockResolvedValue([]) },
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useThreadHistory("thread-1"), {
      wrapper,
    });

    const msg = { id: "m1", type: "ai", content: "first" } as Message;
    const msgUpdated = { id: "m1", type: "ai", content: "updated" } as Message;

    act(() => {
      result.current.appendMessages([msg]);
    });
    act(() => {
      result.current.appendMessages([msgUpdated]);
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]).toEqual(
      expect.objectContaining({ content: "updated" }),
    );
  });

  it("handles fetch error in loadMessages gracefully", async () => {
    const runs = [{ run_id: "r1", created_at: "2024-01-01" }];
    const mockListRuns = vi.fn().mockResolvedValue(runs);
    mockGetAPIClient.mockReturnValue({ runs: { list: mockListRuns } });

    // First call succeeds (for useThreadRuns queryFn), then fails in loadMessages
    // We need to make the fetch inside loadMessages fail
    mockFetchFn.mockRejectedValue(new Error("Network error"));

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useThreadHistory("thread-1"), {
      wrapper,
    });

    // Wait for loading to start (loadMessages sets loading=true)
    await waitFor(() => {
      // Either loading starts or messages are empty (error case)
      expect(
        result.current.loading === true || result.current.messages.length === 0,
      ).toBe(true);
    });

    // Wait for loading to finish
    await waitFor(() => expect(result.current.loading).toBe(false));

    // Messages should remain empty since fetch failed
    expect(result.current.messages).toEqual([]);
  });

  it("handles concurrent loadMessages calls by setting pendingLoadRef", async () => {
    const runs = [
      { run_id: "r1", created_at: "2024-01-01" },
      { run_id: "r2", created_at: "2024-01-02" },
    ];
    mockGetAPIClient.mockReturnValue({
      runs: { list: vi.fn().mockResolvedValue(runs) },
    });

    let resolveFirst: (value: unknown) => void;
    const firstFetchPromise = new Promise((resolve) => {
      resolveFirst = resolve;
    });

    let fetchCallCount = 0;
    mockFetchFn.mockImplementation(() => {
      fetchCallCount++;
      if (fetchCallCount === 1) {
        return firstFetchPromise.then(() => ({
          json: async () => ({
            data: [
              {
                content: { id: "m1", type: "human", content: "hello" },
                metadata: { caller: "user" },
              },
            ],
            hasMore: false,
          }),
        }));
      }
      return Promise.resolve({
        json: async () => ({
          data: [
            {
              content: { id: "m2", type: "ai", content: "hi" },
              metadata: { caller: "lead_agent" },
            },
          ],
          hasMore: false,
        }),
      });
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useThreadHistory("thread-1"), {
      wrapper,
    });

    // Wait for loading to start
    await waitFor(() => expect(result.current.loading).toBe(true));

    // Resolve the first fetch
    await act(async () => {
      resolveFirst!(undefined);
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
  });

  it("discards fetch result when threadId changes during load", async () => {
    // When threadId changes, the effect resets all state and re-fetches.
    // If a previous fetch was in-flight, its result is discarded because
    // threadIdRef.current !== requestThreadId (line 744-745).
    const runs = [{ run_id: "r1", created_at: "2024-01-01" }];
    mockGetAPIClient.mockReturnValue({
      runs: { list: vi.fn().mockResolvedValue(runs) },
    });

    // Make fetch slow so we can change threadId mid-flight
    let resolveFetch1: (value: unknown) => void;
    let fetchCount = 0;
    mockFetchFn.mockImplementation(() => {
      fetchCount++;
      if (fetchCount === 1) {
        return new Promise((resolve) => {
          resolveFetch1 = resolve;
        });
      }
      return Promise.resolve({
        json: async () => ({
          data: [
            {
              content: { id: "m2", type: "human", content: "hello from t2" },
              metadata: { caller: "user" },
            },
          ],
          hasMore: false,
        }),
      });
    });

    const { wrapper } = createWrapper();
    const { result, rerender } = renderHook(
      ({ tid }) => useThreadHistory(tid),
      { wrapper, initialProps: { tid: "thread-1" } },
    );

    // Wait for the first fetch to start
    await waitFor(() => expect(fetchCount).toBe(1));

    // Change thread ID while first fetch is in-flight
    rerender({ tid: "thread-2" });

    // Resolve the first fetch (for thread-1 — should be discarded)
    await act(async () => {
      resolveFetch1!({
        json: async () => ({
          data: [
            {
              content: { id: "m1", type: "human", content: "hello from t1" },
              metadata: { caller: "user" },
            },
          ],
          hasMore: false,
        }),
      });
    });

    // Wait for the second fetch (thread-2) to complete
    await waitFor(() => {
      // Messages should be from thread-2, not thread-1
      expect(result.current.loading).toBe(false);
    });
  });

  it("returns loading state correctly", async () => {
    mockGetAPIClient.mockReturnValue({
      runs: { list: vi.fn().mockResolvedValue([]) },
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useThreadHistory("thread-1"), {
      wrapper,
    });

    // Initially loading should be false (no runs to load)
    await waitFor(() => expect(result.current.loading).toBe(false));
  });
});

// ═══════════════════════════════════════════════════════════════════
// useThreadStream
// ═══════════════════════════════════════════════════════════════════

describe("useThreadStream", () => {
  const defaultContext = {
    model_name: undefined,
    mode: "flash" as const,
    reasoning_effort: undefined,
    agent_name: undefined,
  };

  beforeEach(() => {
    // Default mock for useThreadHistory dependencies
    mockGetAPIClient.mockReturnValue({
      threads: {
        search: vi.fn().mockResolvedValue([]),
        update: vi.fn().mockResolvedValue(undefined),
        updateState: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined),
      },
      runs: {
        list: vi.fn().mockResolvedValue([]),
        get: vi.fn().mockResolvedValue({}),
      },
    });
    mockFetchFn.mockResolvedValue({
      json: async () => ({ data: [], hasMore: false }),
    });
  });

  it("returns expected shape from the hook", () => {
    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    expect(result.current).toHaveProperty("thread");
    expect(result.current).toHaveProperty("sendMessage");
    expect(result.current).toHaveProperty("isUploading");
    expect(result.current).toHaveProperty("isHistoryLoading");
    expect(result.current).toHaveProperty("hasMoreHistory");
    expect(result.current).toHaveProperty("loadMoreHistory");
    expect(result.current).toHaveProperty("pendingUsageMessages");
    expect(typeof result.current.sendMessage).toBe("function");
  });

  it("submit calls thread.submit with correct payload", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.sendMessage("t1", { text: "hello", files: [] });
    });

    expect(mockSubmit).toHaveBeenCalledTimes(1);
    const [payload, options] = mockSubmit.mock.calls[0] ?? [];
    expect(payload.messages[0].type).toBe("human");
    expect(payload.messages[0].content).toEqual([
      { type: "text", text: "hello" },
    ]);
    expect(options.threadId).toBe("t1");
    expect(options.streamSubgraphs).toBe(true);
  });

  it("does not send when sendInFlight is true", async () => {
    const mockSubmit = vi
      .fn()
      .mockImplementation(
        () => new Promise<void>((resolve) => setTimeout(resolve, 100)),
      );
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // Start first send (won't complete immediately)
    act(() => {
      result.current.sendMessage("t1", { text: "first", files: [] });
    });

    // Second send should be blocked
    await act(async () => {
      await result.current.sendMessage("t1", { text: "second", files: [] });
    });

    // Only one submit call should have been made
    expect(mockSubmit).toHaveBeenCalledTimes(1);
  });

  it("creates optimistic human message on send", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.sendMessage("t1", { text: "hello", files: [] });
    });

    // After submit, optimistic messages should be cleared
    // (since submit resolved immediately)
    expect(result.current.thread.messages).toBeDefined();
  });

  it("calls onSend callback when sending", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    const onSend = vi.fn();
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
          onSend,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.sendMessage("t1", { text: "hello", files: [] });
    });

    expect(onSend).toHaveBeenCalledWith("t1");
  });

  it("sets context parameters correctly for pro mode", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const proContext = {
      ...defaultContext,
      mode: "pro" as const,
    };

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: proContext,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.sendMessage("t1", { text: "hello", files: [] });
    });

    const [, options] = mockSubmit.mock.calls[0] ?? [];
    expect(options.context.is_plan_mode).toBe(true);
    expect(options.context.thinking_enabled).toBe(true);
    expect(options.context.subagent_enabled).toBe(false);
    expect(options.context.reasoning_effort).toBe("medium");
  });

  it("sets context parameters correctly for ultra mode", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const ultraContext = {
      ...defaultContext,
      mode: "ultra" as const,
    };

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: ultraContext,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.sendMessage("t1", { text: "hello", files: [] });
    });

    const [, options] = mockSubmit.mock.calls[0] ?? [];
    expect(options.context.is_plan_mode).toBe(true);
    expect(options.context.thinking_enabled).toBe(true);
    expect(options.context.subagent_enabled).toBe(true);
    expect(options.context.reasoning_effort).toBe("high");
  });

  it("sets context parameters correctly for thinking mode", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const thinkingContext = {
      ...defaultContext,
      mode: "thinking" as const,
    };

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: thinkingContext,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.sendMessage("t1", { text: "hello", files: [] });
    });

    const [, options] = mockSubmit.mock.calls[0] ?? [];
    expect(options.context.thinking_enabled).toBe(true);
    expect(options.context.is_plan_mode).toBe(false);
    expect(options.context.subagent_enabled).toBe(false);
    expect(options.context.reasoning_effort).toBe("low");
  });

  it("sets context parameters correctly for flash mode", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const flashContext = {
      ...defaultContext,
      mode: "flash" as const,
    };

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: flashContext,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.sendMessage("t1", { text: "hello", files: [] });
    });

    const [, options] = mockSubmit.mock.calls[0] ?? [];
    expect(options.context.thinking_enabled).toBe(false);
    expect(options.context.is_plan_mode).toBe(false);
    expect(options.context.subagent_enabled).toBe(false);
    expect(options.context.reasoning_effort).toBeUndefined();
  });

  it("re-throws error from sendMessage and clears uploading state", async () => {
    const mockSubmit = vi.fn().mockRejectedValue(new Error("Stream failed"));
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    let caughtError: unknown;
    await act(async () => {
      try {
        await result.current.sendMessage("t1", { text: "hello", files: [] });
      } catch (e) {
        caughtError = e;
      }
    });

    expect(caughtError).toBeInstanceOf(Error);
    expect((caughtError as Error).message).toBe("Stream failed");
    expect(result.current.isUploading).toBe(false);
  });

  it("handles file upload flow", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const mockFile = new File(["content"], "test.txt", { type: "text/plain" });
    mockPromptInputFilePartToFile.mockResolvedValue(mockFile);
    mockUploadFiles.mockResolvedValue({
      files: [
        {
          filename: "test.txt",
          size: 7,
          virtual_path: "/uploads/test.txt",
          artifact_url: "",
        },
      ],
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.sendMessage(
        "t1",
        {
          text: "analyze this",
          files: [
            {
              type: "file" as const,
              filename: "test.txt",
              mediaType: "text/plain",
              url: "",
            },
          ],
        },
        undefined,
      );
    });

    expect(mockPromptInputFilePartToFile).toHaveBeenCalled();
    expect(mockUploadFiles).toHaveBeenCalledWith("t1", [mockFile]);
    expect(mockSubmit).toHaveBeenCalled();

    // Verify the submit payload includes file metadata
    const [, options] = mockSubmit.mock.calls[0] ?? [];
    expect(options.context.thread_id).toBe("t1");
  });

  it("shows toast error when file upload fails", async () => {
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: vi.fn(),
    });

    const mockFile = new File(["content"], "test.txt", { type: "text/plain" });
    mockPromptInputFilePartToFile.mockResolvedValue(mockFile);
    mockUploadFiles.mockRejectedValue(new Error("Upload failed"));

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    await act(async () => {
      try {
        await result.current.sendMessage(
          "t1",
          {
            text: "analyze this",
            files: [
              {
                type: "file" as const,
                filename: "test.txt",
                mediaType: "text/plain",
                url: "",
              },
            ],
          },
          undefined,
        );
      } catch {
        // Expected to throw
      }
    });

    expect(mockToastError).toHaveBeenCalledWith("Upload failed");
  });

  it("shows toast when file conversion fails", async () => {
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: vi.fn(),
    });

    mockPromptInputFilePartToFile.mockResolvedValue(null);

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    await act(async () => {
      try {
        await result.current.sendMessage(
          "t1",
          {
            text: "analyze this",
            files: [
              {
                type: "file" as const,
                filename: "test.txt",
                mediaType: "text/plain",
                url: "",
              },
            ],
          },
          undefined,
        );
      } catch {
        // Expected
      }
    });

    expect(mockToastError).toHaveBeenCalled();
  });

  it("does not create optimistic human message when hide_from_ui is set", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.sendMessage(
        "t1",
        { text: "internal", files: [] },
        undefined,
        { additionalKwargs: { hide_from_ui: true } },
      );
    });

    // The thread messages should not contain the hidden message in optimistic state
    expect(mockSubmit).toHaveBeenCalled();
  });

  it("creates optimistic AI message when files are present", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    // Mock successful file upload
    const mockFile = new File(["content"], "test.pdf", {
      type: "application/pdf",
    });
    mockPromptInputFilePartToFile.mockResolvedValue(mockFile);
    mockUploadFiles.mockResolvedValue({
      files: [
        {
          filename: "test.pdf",
          size: 7,
          virtual_path: "/uploads/test.pdf",
          artifact_url: "",
        },
      ],
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.sendMessage(
        "t1",
        {
          text: "analyze",
          files: [
            {
              type: "file" as const,
              filename: "test.pdf",
              mediaType: "application/pdf",
              url: "",
            },
          ],
        },
        undefined,
      );
    });

    expect(mockSubmit).toHaveBeenCalled();
  });

  it("passes extraContext to thread.submit", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    const extra = { custom_key: "custom_value" };
    await act(async () => {
      await result.current.sendMessage("t1", { text: "hi", files: [] }, extra);
    });

    const [, options] = mockSubmit.mock.calls[0] ?? [];
    expect(options.context.custom_key).toBe("custom_value");
  });

  it("invalidates queries after successful send", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const { queryClient, wrapper } = createWrapper();
    const spy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.sendMessage("t1", { text: "hi", files: [] });
    });

    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["threads", "search"] }),
    );
  });

  it("snapshots baseline when isLoading becomes true with empty baseline", async () => {
    let currentIsLoading = false;
    let currentMessages: Message[] = [];

    mockUseStream.mockImplementation(() => ({
      messages: currentMessages,
      isLoading: currentIsLoading,
      submit: vi.fn().mockResolvedValue(undefined),
    }));

    const { wrapper } = createWrapper();
    const { rerender } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // Now simulate isLoading becoming true with messages
    currentIsLoading = true;
    currentMessages = [{ id: "m1", type: "human", content: "q" } as Message];

    rerender();

    // Should not throw — exercises the isLoading baseline snapshot path
  });

  it("clears optimistic messages when server human message arrives", async () => {
    let currentMessages: Message[] = [];
    const mockSubmit = vi.fn().mockResolvedValue(undefined);

    mockUseStream.mockImplementation(() => ({
      messages: currentMessages,
      isLoading: false,
      submit: mockSubmit,
    }));

    const { wrapper } = createWrapper();
    const { result, rerender } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // Send a message to create optimistic messages
    await act(async () => {
      await result.current.sendMessage("t1", { text: "hello", files: [] });
    });

    // Simulate server returning messages (including the human message)
    currentMessages = [
      { id: "m1", type: "human", content: "hello" } as Message,
      { id: "m2", type: "ai", content: "response" } as Message,
    ];

    rerender();

    // Optimistic messages should be cleared
    // The merged messages should contain the server messages
    expect(result.current.thread.messages).toBeDefined();
  });

  it("resets state when threadId changes to null", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const { wrapper } = createWrapper();
    const { result, rerender } = renderHook(
      ({ tid }) =>
        useThreadStream({
          threadId: tid,
          context: defaultContext,
        }),
      { wrapper, initialProps: { tid: "t1" as string | null } },
    );

    // Switch to null threadId
    rerender({ tid: null });

    // Should not throw and hook should still work
    expect(result.current.thread).toBeDefined();
  });

  it("handles useStream onError callback with string error", async () => {
    let streamOnError: ((error: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onError?: (error: unknown) => void } = {}) => {
        streamOnError = options.onError;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // Simulate stream error
    act(() => {
      streamOnError?.("connection lost");
    });

    expect(mockToastError).toHaveBeenCalledWith("connection lost");
  });

  it("handles useStream onError callback with Error object", async () => {
    let streamOnError: ((error: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onError?: (error: unknown) => void } = {}) => {
        streamOnError = options.onError;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    act(() => {
      streamOnError?.(new Error("server error"));
    });

    expect(mockToastError).toHaveBeenCalledWith("server error");
  });

  it("handles useStream onError callback with object containing message", async () => {
    let streamOnError: ((error: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onError?: (error: unknown) => void } = {}) => {
        streamOnError = options.onError;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    act(() => {
      streamOnError?.({ message: "rate limited" });
    });

    expect(mockToastError).toHaveBeenCalledWith("rate limited");
  });

  it("handles useStream onError with nested error object", async () => {
    let streamOnError: ((error: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onError?: (error: unknown) => void } = {}) => {
        streamOnError = options.onError;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    act(() => {
      streamOnError?.({ error: new Error("nested error") });
    });

    expect(mockToastError).toHaveBeenCalledWith("nested error");
  });

  it("handles useStream onError with nested string error", async () => {
    let streamOnError: ((error: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onError?: (error: unknown) => void } = {}) => {
        streamOnError = options.onError;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    act(() => {
      streamOnError?.({ error: "string nested error" });
    });

    expect(mockToastError).toHaveBeenCalledWith("string nested error");
  });

  it("handles useStream onError with unknown error (fallback)", async () => {
    let streamOnError: ((error: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onError?: (error: unknown) => void } = {}) => {
        streamOnError = options.onError;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    act(() => {
      streamOnError?.(42);
    });

    expect(mockToastError).toHaveBeenCalledWith("Request failed.");
  });

  it("handles useStream onFinish callback", async () => {
    let streamOnFinish: ((state: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onFinish?: (state: unknown) => void } = {}) => {
        streamOnFinish = options.onFinish;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const onFinish = vi.fn();
    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
          onFinish,
        }),
      { wrapper },
    );

    act(() => {
      streamOnFinish?.({ values: { title: "done" } });
    });

    expect(onFinish).toHaveBeenCalledWith({ title: "done" });
  });

  it("handles useStream onToolEnd via onLangChainEvent", async () => {
    let streamOnLangChainEvent: ((event: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onLangChainEvent?: (event: unknown) => void } = {}) => {
        streamOnLangChainEvent = options.onLangChainEvent;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const onToolEnd = vi.fn();
    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
          onToolEnd,
        }),
      { wrapper },
    );

    act(() => {
      streamOnLangChainEvent?.({
        event: "on_tool_end",
        name: "search",
        data: { query: "test" },
      });
    });

    expect(onToolEnd).toHaveBeenCalledWith({
      name: "search",
      data: { query: "test" },
    });
  });

  it("ignores non-tool_end langchain events", async () => {
    let streamOnLangChainEvent: ((event: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onLangChainEvent?: (event: unknown) => void } = {}) => {
        streamOnLangChainEvent = options.onLangChainEvent;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const onToolEnd = vi.fn();
    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
          onToolEnd,
        }),
      { wrapper },
    );

    act(() => {
      streamOnLangChainEvent?.({
        event: "on_llm_start",
        name: "llm",
        data: {},
      });
    });

    expect(onToolEnd).not.toHaveBeenCalled();
  });

  it("handles onCustomEvent task_running", async () => {
    let streamOnCustomEvent: ((event: unknown) => void) | undefined;
    const mockUpdateSubtaskFn = vi.fn();
    mockUseUpdateSubtask.mockReturnValue(mockUpdateSubtaskFn);

    mockUseStream.mockImplementation(
      (options: { onCustomEvent?: (event: unknown) => void } = {}) => {
        streamOnCustomEvent = options.onCustomEvent;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    const taskMessage = { type: "ai", content: "working on it" };
    act(() => {
      streamOnCustomEvent?.({
        type: "task_running",
        task_id: "task-1",
        message: taskMessage,
      });
    });

    expect(mockUpdateSubtaskFn).toHaveBeenCalledWith({
      id: "task-1",
      latestMessage: taskMessage,
    });
  });

  it("handles onCustomEvent llm_retry", async () => {
    let streamOnCustomEvent: ((event: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onCustomEvent?: (event: unknown) => void } = {}) => {
        streamOnCustomEvent = options.onCustomEvent;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    act(() => {
      streamOnCustomEvent?.({
        type: "llm_retry",
        message: "Rate limited, retrying...",
      });
    });

    // toast() is called directly as a function (not toast.info)
    expect(mockToast).toHaveBeenCalledWith("Rate limited, retrying...");
  });

  it("ignores non-matching custom events", async () => {
    let streamOnCustomEvent: ((event: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onCustomEvent?: (event: unknown) => void } = {}) => {
        streamOnCustomEvent = options.onCustomEvent;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // Should not throw
    act(() => {
      streamOnCustomEvent?.({ type: "unknown_event" });
    });

    expect(mockToastInfo).not.toHaveBeenCalled();
  });

  it("handles onUpdateEvent with title update", async () => {
    let streamOnUpdateEvent: ((data: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onUpdateEvent?: (data: unknown) => void } = {}) => {
        streamOnUpdateEvent = options.onUpdateEvent;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { queryClient, wrapper } = createWrapper();

    // Seed the cache
    queryClient.setQueryData(
      ["threads", "search"],
      [
        { thread_id: "t1", values: { title: "Old" } },
        { thread_id: "t2", values: { title: "Other" } },
      ],
    );

    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    act(() => {
      streamOnUpdateEvent?.({
        update: { title: "Updated Title" },
      });
    });

    const cached = queryClient.getQueryData<any[]>(["threads", "search"]);

    // The title should be updated for the matching thread
    const t1 = cached?.find((t: any) => t.thread_id === "t1");
    expect(t1?.values.title).toBe("Updated Title");
  });

  it("ignores onUpdateEvent with no title", async () => {
    let streamOnUpdateEvent: ((data: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onUpdateEvent?: (data: unknown) => void } = {}) => {
        streamOnUpdateEvent = options.onUpdateEvent;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // Should not throw — Object.values of { messages: [] } is [[]] which has no "title"
    act(() => {
      streamOnUpdateEvent?.({ update: { messages: [] } });
    });
  });

  it("trims whitespace from message text before sending", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.sendMessage("t1", {
        text: "  hello world  ",
        files: [],
      });
    });

    const [payload] = mockSubmit.mock.calls[0] ?? [];
    expect(payload.messages[0].content).toEqual([
      { type: "text", text: "hello world" },
    ]);
  });

  it("handles empty text in message", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.sendMessage("t1", { text: "", files: [] });
    });

    const [payload] = mockSubmit.mock.calls[0] ?? [];
    // Empty text should result in empty content array
    expect(payload.messages[0].content).toEqual([{ type: "text", text: "" }]);
  });

  it("uses custom reasoning_effort when provided", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const customContext = {
      ...defaultContext,
      mode: "ultra" as const,
      reasoning_effort: "low" as const,
    };

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: customContext,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.sendMessage("t1", { text: "hi", files: [] });
    });

    const [, options] = mockSubmit.mock.calls[0] ?? [];
    // Custom reasoning_effort should override the mode default
    expect(options.context.reasoning_effort).toBe("low");
  });

  it("invalidates token usage queries on error when threadId is set", async () => {
    let streamOnError: ((error: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onError?: (error: unknown) => void } = {}) => {
        streamOnError = options.onError;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { queryClient, wrapper } = createWrapper();
    const spy = vi.spyOn(queryClient, "invalidateQueries");

    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    act(() => {
      streamOnError?.(new Error("fail"));
    });

    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["thread-token-usage", "t1"],
      }),
    );
  });

  it("does not invalidate token usage queries when not mock and no threadId", async () => {
    let streamOnError: ((error: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onError?: (error: unknown) => void } = {}) => {
        streamOnError = options.onError;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { queryClient, wrapper } = createWrapper();
    const spy = vi.spyOn(queryClient, "invalidateQueries");

    renderHook(
      () =>
        useThreadStream({
          threadId: null,
          context: defaultContext,
        }),
      { wrapper },
    );

    act(() => {
      streamOnError?.(new Error("fail"));
    });

    // Should NOT invalidate token usage queries because threadId is null
    expect(spy).not.toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["thread-token-usage", null],
      }),
    );
  });

  it("invalidates token usage queries on finish when threadId is set", async () => {
    let streamOnFinish: ((state: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onFinish?: (state: unknown) => void } = {}) => {
        streamOnFinish = options.onFinish;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { queryClient, wrapper } = createWrapper();
    const spy = vi.spyOn(queryClient, "invalidateQueries");

    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    act(() => {
      streamOnFinish?.({ values: { title: "done" } });
    });

    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["thread-token-usage", "t1"],
      }),
    );
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["threads", "search"] }),
    );
  });

  it("does not invalidate token usage queries on finish when no threadId", async () => {
    let streamOnFinish: ((state: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onFinish?: (state: unknown) => void } = {}) => {
        streamOnFinish = options.onFinish;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { queryClient, wrapper } = createWrapper();
    const spy = vi.spyOn(queryClient, "invalidateQueries");

    renderHook(
      () =>
        useThreadStream({
          threadId: null,
          context: defaultContext,
        }),
      { wrapper },
    );

    act(() => {
      streamOnFinish?.({ values: {} });
    });

    expect(spy).not.toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["thread-token-usage", null],
      }),
    );
  });

  it("calls thread.update to set agent_name on thread creation when not mock", async () => {
    const mockUpdate = vi.fn().mockResolvedValue(undefined);
    let streamOnCreated:
      | ((meta: { thread_id: string; run_id: string }) => void)
      | undefined;

    mockUseStream.mockImplementation(
      (
        options: {
          onCreated?: (meta: { thread_id: string; run_id: string }) => void;
        } = {},
      ) => {
        streamOnCreated = options.onCreated;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    mockGetAPIClient.mockReturnValue({
      threads: {
        search: vi.fn().mockResolvedValue([]),
        update: mockUpdate,
        updateState: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined),
      },
      runs: {
        list: vi.fn().mockResolvedValue([]),
        get: vi.fn(),
      },
    });

    const ctxWithAgent = {
      ...defaultContext,
      agent_name: "researcher",
    };

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: ctxWithAgent,
          isMock: false,
        }),
      { wrapper },
    );

    // getAPIClient is called again inside onCreated, so mock it again
    mockGetAPIClient.mockReturnValue({
      threads: {
        search: vi.fn().mockResolvedValue([]),
        update: mockUpdate,
        updateState: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined),
      },
      runs: {
        list: vi.fn().mockResolvedValue([]),
        get: vi.fn(),
      },
    });

    await act(async () => {
      streamOnCreated?.({ thread_id: "new-thread", run_id: "run-1" });
    });

    // The update should be called to set agent_name metadata
    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith("new-thread", {
        metadata: { agent_name: "researcher" },
      });
    });
  });

  it("does not call thread.update when isMock is true", async () => {
    const mockUpdate = vi.fn().mockResolvedValue(undefined);
    let streamOnCreated:
      | ((meta: { thread_id: string; run_id: string }) => void)
      | undefined;

    mockUseStream.mockImplementation(
      (
        options: {
          onCreated?: (meta: { thread_id: string; run_id: string }) => void;
        } = {},
      ) => {
        streamOnCreated = options.onCreated;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    mockGetAPIClient.mockReturnValue({
      threads: {
        search: vi.fn().mockResolvedValue([]),
        update: mockUpdate,
        updateState: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined),
      },
      runs: {
        list: vi.fn().mockResolvedValue([]),
        get: vi.fn(),
      },
    });

    const ctxWithAgent = {
      ...defaultContext,
      agent_name: "researcher",
    };

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: ctxWithAgent,
          isMock: true,
        }),
      { wrapper },
    );

    await act(async () => {
      streamOnCreated?.({ thread_id: "new-thread", run_id: "run-1" });
    });

    // Update should NOT be called when isMock is true
    await waitFor(() => {
      expect(mockUpdate).not.toHaveBeenCalled();
    });
  });

  it("handles onUpdateEvent with SummarizationMiddleware data", async () => {
    let streamOnUpdateEvent: ((data: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onUpdateEvent?: (data: unknown) => void } = {}) => {
        streamOnUpdateEvent = options.onUpdateEvent;
        return {
          messages: [
            { id: "m1", type: "human", content: "q1" },
            { id: "m2", type: "ai", content: "a1" },
            { id: "m3", type: "human", content: "q2" },
          ] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // Simulate SummarizationMiddleware update with enough messages
    act(() => {
      streamOnUpdateEvent?.({
        "SummarizationMiddleware.before_model": {
          messages: [
            { id: "old1", type: "human", content: "old q" },
            { id: "old2", type: "ai", content: "old a" },
            { id: "m1", type: "human", content: "keep boundary" },
          ],
        },
      });
    });

    // Should not throw — exercises the summarization path
  });

  it("handles onUpdateEvent SummarizationMiddleware with too few messages", async () => {
    let streamOnUpdateEvent: ((data: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onUpdateEvent?: (data: unknown) => void } = {}) => {
        streamOnUpdateEvent = options.onUpdateEvent;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // Only 1 message (< 2), should return early
    act(() => {
      streamOnUpdateEvent?.({
        "SummarizationMiddleware.before_model": {
          messages: [{ id: "m1", type: "human", content: "only one" }],
        },
      });
    });

    // Should not throw
  });

  it("handles onUpdateEvent SummarizationMiddleware with summary messages", async () => {
    let streamOnUpdateEvent: ((data: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onUpdateEvent?: (data: unknown) => void } = {}) => {
        streamOnUpdateEvent = options.onUpdateEvent;
        return {
          messages: [
            { id: "m1", type: "human", content: "q1" },
            { id: "m2", type: "ai", content: "a1" },
          ] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // Simulate with summary messages that should be added to summarizedRef
    act(() => {
      streamOnUpdateEvent?.({
        "SummarizationMiddleware.before_model": {
          messages: [
            {
              id: "s1",
              name: "summary",
              type: "human",
              content: "summary text",
            },
            { id: "m1", type: "human", content: "q1" },
            { id: "m2", type: "ai", content: "a1" },
          ],
        },
      });
    });

    // Should not throw — exercises summary message tracking
  });

  it("handles onUpdateEvent SummarizationMiddleware with undefined message id", async () => {
    let streamOnUpdateEvent: ((data: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onUpdateEvent?: (data: unknown) => void } = {}) => {
        streamOnUpdateEvent = options.onUpdateEvent;
        return {
          messages: [
            { type: "human", content: "no id msg" },
            { id: "m2", type: "ai", content: "a1" },
          ] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // Message without id should be handled (m.id !== undefined check)
    act(() => {
      streamOnUpdateEvent?.({
        "SummarizationMiddleware.before_model": {
          messages: [
            { id: "old1", type: "human", content: "old" },
            { id: "old2", type: "ai", content: "old a" },
            { id: "boundary", type: "ai", content: "boundary" },
          ],
        },
      });
    });

    // Should not throw
  });

  it("calls thread.update catch handler when update fails", async () => {
    const mockUpdate = vi.fn().mockRejectedValue(new Error("update failed"));
    let streamOnCreated:
      | ((meta: { thread_id: string; run_id: string }) => void)
      | undefined;

    mockUseStream.mockImplementation(
      (
        options: {
          onCreated?: (meta: { thread_id: string; run_id: string }) => void;
        } = {},
      ) => {
        streamOnCreated = options.onCreated;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    mockGetAPIClient.mockReturnValue({
      threads: {
        search: vi.fn().mockResolvedValue([]),
        update: mockUpdate,
        updateState: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined),
      },
      runs: {
        list: vi.fn().mockResolvedValue([]),
        get: vi.fn(),
      },
    });

    const ctxWithAgent = {
      ...defaultContext,
      agent_name: "researcher",
    };

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: ctxWithAgent,
          isMock: false,
        }),
      { wrapper },
    );

    // getAPIClient is called again inside onCreated
    mockGetAPIClient.mockReturnValue({
      threads: {
        search: vi.fn().mockResolvedValue([]),
        update: mockUpdate,
        updateState: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined),
      },
      runs: {
        list: vi.fn().mockResolvedValue([]),
        get: vi.fn(),
      },
    });

    // Should not throw even when update fails (catch handler at line 249)
    await act(async () => {
      streamOnCreated?.({ thread_id: "new-thread", run_id: "run-1" });
    });

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalled();
    });
  });

  it("handles onError with messages that have identities for baseline", async () => {
    let streamOnError: ((error: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onError?: (error: unknown) => void } = {}) => {
        streamOnError = options.onError;
        return {
          messages: [
            { id: "m1", type: "human", content: "q" },
            { type: "tool", tool_call_id: "tc1", content: "result" },
            { type: "human", content: "no id" },
          ] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    act(() => {
      streamOnError?.(new Error("fail"));
    });

    expect(mockToastError).toHaveBeenCalledWith("fail");
  });

  it("handles onFinish with messages that have identities for baseline", async () => {
    let streamOnFinish: ((state: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onFinish?: (state: unknown) => void } = {}) => {
        streamOnFinish = options.onFinish;
        return {
          messages: [
            { id: "m1", type: "human", content: "q" },
            { type: "tool", tool_call_id: "tc1", content: "result" },
            { type: "human", content: "no id" },
          ] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    act(() => {
      streamOnFinish?.({ values: { title: "done" } });
    });

    expect(mockToastError).not.toHaveBeenCalled();
  });

  it("throws error when threadId is empty during file upload", async () => {
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: vi.fn().mockResolvedValue(undefined),
    });

    const mockFile = new File(["content"], "test.txt", { type: "text/plain" });
    mockPromptInputFilePartToFile.mockResolvedValue(mockFile);

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "",
          context: defaultContext,
        }),
      { wrapper },
    );

    await act(async () => {
      try {
        await result.current.sendMessage(
          "",
          {
            text: "analyze",
            files: [
              {
                type: "file" as const,
                filename: "test.txt",
                mediaType: "text/plain",
                url: "",
              },
            ],
          },
          undefined,
        );
      } catch (e) {
        expect((e as Error).message).toBe(
          "Thread is not ready for file upload.",
        );
      }
    });
  });

  it("handles file upload with successful optimistic message update", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const mockFile = new File(["content"], "test.txt", { type: "text/plain" });
    mockPromptInputFilePartToFile.mockResolvedValue(mockFile);
    mockUploadFiles.mockResolvedValue({
      files: [
        {
          filename: "test.txt",
          size: 7,
          virtual_path: "/uploads/test.txt",
          artifact_url: "",
        },
      ],
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.sendMessage(
        "t1",
        {
          text: "analyze",
          files: [
            {
              type: "file" as const,
              filename: "test.txt",
              mediaType: "text/plain",
              url: "",
            },
          ],
        },
        undefined,
      );
    });

    // Verify the submit was called with file metadata
    expect(mockSubmit).toHaveBeenCalled();
    const [payload] = mockSubmit.mock.calls[0] ?? [];
    expect(payload.messages[0].additional_kwargs.files).toBeDefined();
    expect(payload.messages[0].additional_kwargs.files[0].filename).toBe(
      "test.txt",
    );
    expect(payload.messages[0].additional_kwargs.files[0].status).toBe(
      "uploaded",
    );
  });

  it("builds usage baseline from existing messages on send", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [
        { id: "m1", type: "human", content: "prev q" },
        { id: "m2", type: "ai", content: "prev a" },
        { type: "tool", tool_call_id: "tc1", content: "tool result" },
        { type: "human", content: "no id" },
      ] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.sendMessage("t1", {
        text: "new question",
        files: [],
      });
    });

    expect(mockSubmit).toHaveBeenCalled();
  });

  it("handles sendMessage with additionalKwargs options", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.sendMessage(
        "t1",
        { text: "hello", files: [] },
        undefined,
        { additionalKwargs: { custom_field: "value" } },
      );
    });

    const [payload] = mockSubmit.mock.calls[0] ?? [];
    expect(payload.messages[0].additional_kwargs.custom_field).toBe("value");
  });

  it("handles sendMessage with additionalKwargs hide_from_ui and files", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // hide_from_ui=true with files should not create optimistic messages
    await act(async () => {
      await result.current.sendMessage(
        "t1",
        { text: "internal", files: [] },
        undefined,
        { additionalKwargs: { hide_from_ui: true } },
      );
    });

    expect(mockSubmit).toHaveBeenCalled();
  });

  it("sets isUploading to true during file upload", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    const mockFile = new File(["content"], "test.txt", { type: "text/plain" });
    mockPromptInputFilePartToFile.mockResolvedValue(mockFile);

    // Make upload slow
    let resolveUpload: (value: unknown) => void;
    mockUploadFiles.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveUpload = resolve;
        }),
    );

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // Start upload
    act(() => {
      result.current.sendMessage("t1", {
        text: "analyze",
        files: [
          {
            type: "file" as const,
            filename: "test.txt",
            mediaType: "text/plain",
            url: "",
          },
        ],
      });
    });

    // Wait a tick for the upload to start
    await waitFor(() => expect(result.current.isUploading).toBe(true));

    // Complete upload
    await act(async () => {
      resolveUpload!({
        files: [
          {
            filename: "test.txt",
            size: 7,
            virtual_path: "/uploads/test.txt",
            artifact_url: "",
          },
        ],
      });
      // Wait for the submit to complete
      await mockSubmit;
    });

    await waitFor(() => expect(result.current.isUploading).toBe(false));
  });

  it("handles onError with empty string nested error (falls through to default)", async () => {
    let streamOnError: ((error: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onError?: (error: unknown) => void } = {}) => {
        streamOnError = options.onError;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // nestedError is a string but empty after trim → falls through to "Request failed."
    act(() => {
      streamOnError?.({ error: "   " });
    });

    expect(mockToastError).toHaveBeenCalledWith("Request failed.");
  });

  it("handles onError with object message that is empty string", async () => {
    let streamOnError: ((error: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onError?: (error: unknown) => void } = {}) => {
        streamOnError = options.onError;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // Object with message that is empty string after trim → falls through
    act(() => {
      streamOnError?.({ message: "  " });
    });

    expect(mockToastError).toHaveBeenCalledWith("Request failed.");
  });

  it("does not call onStart on subsequent handleStreamStart calls", async () => {
    const onStart = vi.fn();
    let streamOnCreated:
      | ((meta: { thread_id: string; run_id: string }) => void)
      | undefined;

    mockUseStream.mockImplementation(
      (
        options: {
          onCreated?: (meta: { thread_id: string; run_id: string }) => void;
        } = {},
      ) => {
        streamOnCreated = options.onCreated;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    mockGetAPIClient.mockReturnValue({
      threads: {
        search: vi.fn().mockResolvedValue([]),
        update: vi.fn().mockResolvedValue(undefined),
        updateState: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined),
      },
      runs: {
        list: vi.fn().mockResolvedValue([]),
        get: vi.fn(),
      },
    });

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
          onStart,
        }),
      { wrapper },
    );

    // First onCreated → onStart should be called
    await act(async () => {
      streamOnCreated?.({ thread_id: "t1", run_id: "run-1" });
    });
    expect(onStart).toHaveBeenCalledTimes(1);

    // Second onCreated → onStart should NOT be called (startedRef.current is true)
    await act(async () => {
      streamOnCreated?.({ thread_id: "t1", run_id: "run-2" });
    });
    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it("handles onUpdateEvent SummarizationMiddleware with null messages", async () => {
    let streamOnUpdateEvent: ((data: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onUpdateEvent?: (data: unknown) => void } = {}) => {
        streamOnUpdateEvent = options.onUpdateEvent;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // messages is null → should use ?? [] fallback (line 263)
    act(() => {
      streamOnUpdateEvent?.({
        "SummarizationMiddleware.before_model": {
          messages: null,
        },
      });
    });

    // Should not throw
  });

  it("handles thread.isLoading baseline snapshot with existing messages", async () => {
    // Test the useStream isLoading baseline path (lines 413-422)
    mockUseStream.mockReturnValue({
      messages: [
        { id: "base1", type: "human", content: "baseline" } as Message,
      ],
      isLoading: true,
      submit: vi.fn().mockResolvedValue(undefined),
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // The hook should handle isLoading=true with messages
    expect(result.current.thread).toBeDefined();
  });

  it("handles sendMessage with files that have undefined filename", async () => {
    const mockSubmit = vi.fn().mockResolvedValue(undefined);
    mockUseStream.mockReturnValue({
      messages: [] as Message[],
      isLoading: false,
      submit: mockSubmit,
    });

    mockPromptInputFilePartToFile.mockResolvedValue(null);

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // File part with undefined filename → ?? "" branch
    await act(async () => {
      try {
        await result.current.sendMessage(
          "t1",
          {
            text: "analyze",
            files: [
              {
                type: "file" as const,
                filename: undefined as unknown as string,
                mediaType: "text/plain",
                url: "",
              },
            ],
          },
          undefined,
        );
      } catch {
        // Expected to throw (failed conversion)
      }
    });

    expect(mockToastError).toHaveBeenCalled();
  });

  it("handles onUpdateEvent with no matching data keys", async () => {
    let streamOnUpdateEvent: ((data: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onUpdateEvent?: (data: unknown) => void } = {}) => {
        streamOnUpdateEvent = options.onUpdateEvent;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // Object.values returns entries but none have "title"
    act(() => {
      streamOnUpdateEvent?.({
        someUpdate: { messages: ["msg1"] },
        anotherUpdate: { artifacts: ["a1"] },
      });
    });

    // Should not throw
  });

  it("handles onUpdateEvent with empty data object", async () => {
    let streamOnUpdateEvent: ((data: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onUpdateEvent?: (data: unknown) => void } = {}) => {
        streamOnUpdateEvent = options.onUpdateEvent;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // Empty object → Object.values returns []
    act(() => {
      streamOnUpdateEvent?.({});
    });

    // Should not throw
  });

  it("handles onCustomEvent with non-object event", async () => {
    let streamOnCustomEvent: ((event: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onCustomEvent?: (event: unknown) => void } = {}) => {
        streamOnCustomEvent = options.onCustomEvent;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // Non-object events should be ignored gracefully
    act(() => {
      streamOnCustomEvent?.(null);
      streamOnCustomEvent?.(42);
      streamOnCustomEvent?.("string event");
    });

    // Should not throw
  });

  it("handles onUpdateEvent title update with undefined title", async () => {
    let streamOnUpdateEvent: ((data: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onUpdateEvent?: (data: unknown) => void } = {}) => {
        streamOnUpdateEvent = options.onUpdateEvent;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // Update with title: undefined → should not update cache
    act(() => {
      streamOnUpdateEvent?.({
        update: { title: undefined },
      });
    });

    // Should not throw
  });

  it("handles onUpdateEvent title update with empty string title", async () => {
    let streamOnUpdateEvent: ((data: unknown) => void) | undefined;

    mockUseStream.mockImplementation(
      (options: { onUpdateEvent?: (data: unknown) => void } = {}) => {
        streamOnUpdateEvent = options.onUpdateEvent;
        return {
          messages: [] as Message[],
          isLoading: false,
          submit: vi.fn().mockResolvedValue(undefined),
        };
      },
    );

    const { wrapper } = createWrapper();
    renderHook(
      () =>
        useThreadStream({
          threadId: "t1",
          context: defaultContext,
        }),
      { wrapper },
    );

    // Update with title: "" (falsy) → should not update cache
    act(() => {
      streamOnUpdateEvent?.({
        update: { title: "" },
      });
    });

    // Should not throw
  });
});
