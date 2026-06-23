import { describe, expect, test, vi, beforeEach } from "vitest";

import {
  DEMO_THREAD_IDS,
  loadStaticDemoThreads,
  loadStaticDemoThread,
  staticDemoThreadState,
} from "@/core/threads/static-demo";

describe("DEMO_THREAD_IDS", () => {
  test("is an array of 13 UUIDs", () => {
    expect(Array.isArray(DEMO_THREAD_IDS)).toBe(true);
    expect(DEMO_THREAD_IDS).toHaveLength(13);
  });

  test("each ID is a valid UUID format string", () => {
    const uuidRegex =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    for (const id of DEMO_THREAD_IDS) {
      expect(id).toMatch(uuidRegex);
    }
  });

  test("all IDs are unique", () => {
    const unique = new Set(DEMO_THREAD_IDS);
    expect(unique.size).toBe(DEMO_THREAD_IDS.length);
  });
});

describe("loadStaticDemoThread", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  test("fetches and returns a thread with thread_id set", async () => {
    const mockThread = {
      values: { title: "Test" },
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-06-15T12:00:00Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => mockThread,
    } as Response);

    const result = await loadStaticDemoThread("test-id");
    expect(result.thread_id).toBe("test-id");
    expect(result.updated_at).toBe("2024-06-15T12:00:00Z");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/demo/threads/test-id/thread.json",
    );
  });

  test("falls back to created_at when updated_at is missing", async () => {
    const mockThread = {
      values: { title: "Test" },
      created_at: "2024-01-01T00:00:00Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => mockThread,
    } as Response);

    const result = await loadStaticDemoThread("test-id");
    expect(result.updated_at).toBe("2024-01-01T00:00:00Z");
  });

  test("throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 404,
    } as Response);

    await expect(loadStaticDemoThread("bad-id")).rejects.toThrow(
      "Failed to load demo thread bad-id",
    );
  });

  test("URL-encodes the thread ID", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ values: {}, created_at: "2024-01-01T00:00:00Z" }),
    } as Response);

    await loadStaticDemoThread("id/with/slashes");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/demo/threads/id%2Fwith%2Fslashes/thread.json",
    );
  });
});

describe("loadStaticDemoThreads", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  function makeMockThread(updatedAt: string, createdAt?: string) {
    return {
      values: { title: "Test" },
      updated_at: updatedAt,
      created_at: createdAt ?? updatedAt,
    };
  }

  test("loads all demo threads by default", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => makeMockThread("2024-01-01T00:00:00Z"),
    } as Response);

    const result = await loadStaticDemoThreads();
    expect(result).toHaveLength(DEMO_THREAD_IDS.length);
    // fetch is called once per demo thread
    expect(globalThis.fetch).toHaveBeenCalledTimes(DEMO_THREAD_IDS.length);
  });

  test("respects limit parameter", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => makeMockThread("2024-01-01T00:00:00Z"),
    } as Response);

    const result = await loadStaticDemoThreads({ limit: 3 });
    expect(result).toHaveLength(3);
  });

  test("respects offset parameter", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => makeMockThread("2024-01-01T00:00:00Z"),
    } as Response);

    const all = await loadStaticDemoThreads();
    vi.restoreAllMocks();

    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => makeMockThread("2024-01-01T00:00:00Z"),
    } as Response);

    const offsetResult = await loadStaticDemoThreads({ offset: 5 });
    expect(offsetResult).toHaveLength(all.length - 5);
  });

  test("combines offset and limit", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => makeMockThread("2024-01-01T00:00:00Z"),
    } as Response);

    const result = await loadStaticDemoThreads({ offset: 2, limit: 4 });
    expect(result).toHaveLength(4);
  });

  test("sorts by updated_at descending by default", async () => {
    const timestamps = [
      "2024-01-01T00:00:00Z",
      "2024-06-15T12:00:00Z",
      "2024-03-10T08:00:00Z",
    ];
    let callCount = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
      const ts = timestamps[callCount % timestamps.length]!;
      callCount++;
      return {
        ok: true,
        json: async () => makeMockThread(ts),
      } as Response;
    });

    const result = await loadStaticDemoThreads();
    // With desc sort, later timestamps come first
    for (let i = 1; i < result.length; i++) {
      const prev = Date.parse(result[i - 1]!.updated_at);
      const curr = Date.parse(result[i]!.updated_at);
      expect(prev).toBeGreaterThanOrEqual(curr);
    }
  });

  test("sorts by updated_at ascending when sortOrder is asc", async () => {
    const timestamps = [
      "2024-06-15T12:00:00Z",
      "2024-01-01T00:00:00Z",
      "2024-03-10T08:00:00Z",
    ];
    let callCount = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
      const ts = timestamps[callCount % timestamps.length]!;
      callCount++;
      return {
        ok: true,
        json: async () => makeMockThread(ts),
      } as Response;
    });

    const result = await loadStaticDemoThreads({ sortOrder: "asc" });
    for (let i = 1; i < result.length; i++) {
      const prev = Date.parse(result[i - 1]!.updated_at);
      const curr = Date.parse(result[i]!.updated_at);
      expect(prev).toBeLessThanOrEqual(curr);
    }
  });

  test("offset 0 returns all threads when no limit", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => makeMockThread("2024-01-01T00:00:00Z"),
    } as Response);

    const result = await loadStaticDemoThreads({ offset: 0 });
    expect(result).toHaveLength(DEMO_THREAD_IDS.length);
  });

  test("negative offset is clamped to 0", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => makeMockThread("2024-01-01T00:00:00Z"),
    } as Response);

    const result = await loadStaticDemoThreads({ offset: -5 });
    expect(result).toHaveLength(DEMO_THREAD_IDS.length);
  });

  test("limit larger than array returns all threads", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => makeMockThread("2024-01-01T00:00:00Z"),
    } as Response);

    const result = await loadStaticDemoThreads({ limit: 100 });
    expect(result).toHaveLength(DEMO_THREAD_IDS.length);
  });
});

describe("staticDemoThreadState", () => {
  test("creates a valid ThreadState from a thread", () => {
    const thread = {
      thread_id: "test-id",
      values: { title: "Test", messages: [] },
      updated_at: "2024-01-01T00:00:00Z",
      created_at: "2024-01-01T00:00:00Z",
      metadata: { key: "value" },
    } as any;

    const state = staticDemoThreadState(thread);
    expect(state.values).toBe(thread.values);
    expect(state.next).toEqual([]);
    expect(state.checkpoint.thread_id).toBe("test-id");
    expect(state.checkpoint.checkpoint_ns).toBe("");
    expect(state.checkpoint.checkpoint_id).toBeNull();
    expect(state.checkpoint.checkpoint_map).toBeNull();
    expect(state.metadata).toEqual({ key: "value" });
    expect(state.created_at).toBe("2024-01-01T00:00:00Z");
    expect(state.parent_checkpoint).toBeNull();
    expect(state.tasks).toEqual([]);
  });

  test("uses updated_at as created_at when both present", () => {
    const thread = {
      thread_id: "test-id",
      values: {},
      updated_at: "2024-06-15T12:00:00Z",
      created_at: "2024-01-01T00:00:00Z",
    } as any;

    const state = staticDemoThreadState(thread);
    expect(state.created_at).toBe("2024-06-15T12:00:00Z");
  });

  test("handles missing metadata", () => {
    const thread = {
      thread_id: "test-id",
      values: {},
      updated_at: null,
      created_at: null,
    } as any;

    const state = staticDemoThreadState(thread);
    expect(state.metadata).toBeNull();
    expect(state.created_at).toBeNull();
  });

  test("falls back to created_at when updated_at is missing", () => {
    const thread = {
      thread_id: "test-id",
      values: {},
      created_at: "2024-01-01T00:00:00Z",
    } as any;

    const state = staticDemoThreadState(thread);
    expect(state.created_at).toBe("2024-01-01T00:00:00Z");
  });
});
