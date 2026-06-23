import { describe, test, expect, vi, beforeEach } from "vitest";

// Mock fs and path before importing the module
vi.mock("fs", () => ({
  default: {
    readdirSync: vi.fn(),
    readFileSync: vi.fn(),
  },
}));

vi.mock("path", () => ({
  default: {
    resolve: vi.fn((...args: string[]) => args.join("/")),
  },
}));

import fs from "fs";
import path from "path";

import { POST } from "@/app/mock/api/threads/search/route";

const mockReaddirSync = vi.mocked(fs.readdirSync);
const mockReadFileSync = vi.mocked(fs.readFileSync);
const mockPathResolve = vi.mocked(path.resolve);

function createThreadDir(name: string) {
  return {
    name,
    isDirectory: () => true,
  } as unknown as import("fs").Dirent<NonSharedBuffer>;
}

function createFile(name: string) {
  return {
    name,
    isDirectory: () => false,
  } as unknown as import("fs").Dirent<NonSharedBuffer>;
}

function createThreadJson(overrides: Record<string, unknown> = {}) {
  return JSON.stringify({
    thread_id: "test-thread",
    title: "Test Thread",
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-06-01T00:00:00Z",
    ...overrides,
  });
}

async function makeRequest(body: unknown = {}) {
  return new Request("http://localhost/api/threads/search", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("mock search route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPathResolve.mockImplementation((...args: string[]) => args.join("/"));
  });

  test("POST returns threads array", async () => {
    mockReaddirSync.mockReturnValueOnce([
      createThreadDir("thread-1"),
      createThreadDir("thread-2"),
    ]);
    mockReadFileSync
      .mockReturnValueOnce(
        createThreadJson({ updated_at: "2025-06-01T00:00:00Z" }),
      )
      .mockReturnValueOnce(
        createThreadJson({ updated_at: "2025-05-01T00:00:00Z" }),
      );

    const response = await POST(await makeRequest());
    const data = await response.json();

    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBe(2);
  });

  test("filters out non-directory entries", async () => {
    mockReaddirSync.mockReturnValueOnce([
      createThreadDir("thread-1"),
      createFile("readme.txt"),
      createFile(".DS_Store"),
    ]);
    mockReadFileSync.mockReturnValueOnce(createThreadJson());

    const response = await POST(await makeRequest());
    const data = await response.json();

    expect(data.length).toBe(1);
  });

  test("filters out hidden directories", async () => {
    mockReaddirSync.mockReturnValueOnce([
      createThreadDir("thread-1"),
      createThreadDir(".hidden"),
    ]);
    mockReadFileSync.mockReturnValueOnce(createThreadJson());

    const response = await POST(await makeRequest());
    const data = await response.json();

    expect(data.length).toBe(1);
    expect(data[0].thread_id).toBe("thread-1");
  });

  test("applies default limit of 50", async () => {
    const dirs = Array.from({ length: 60 }, (_, i) =>
      createThreadDir(`thread-${i}`),
    );
    mockReaddirSync.mockReturnValueOnce(dirs);
    for (let i = 0; i < 60; i++) {
      mockReadFileSync.mockReturnValueOnce(
        createThreadJson({ thread_id: `thread-${i}` }),
      );
    }

    const response = await POST(await makeRequest());
    const data = await response.json();

    expect(data.length).toBe(50);
  });

  test("respects custom limit", async () => {
    const dirs = Array.from({ length: 10 }, (_, i) =>
      createThreadDir(`thread-${i}`),
    );
    mockReaddirSync.mockReturnValueOnce(dirs);
    for (let i = 0; i < 10; i++) {
      mockReadFileSync.mockReturnValueOnce(
        createThreadJson({ thread_id: `thread-${i}` }),
      );
    }

    const response = await POST(await makeRequest({ limit: 3 }));
    const data = await response.json();

    expect(data.length).toBe(3);
  });

  test("respects offset", async () => {
    const dirs = Array.from({ length: 5 }, (_, i) =>
      createThreadDir(`thread-${i}`),
    );
    mockReaddirSync.mockReturnValueOnce(dirs);
    for (let i = 0; i < 5; i++) {
      mockReadFileSync.mockReturnValueOnce(
        createThreadJson({ thread_id: `thread-${i}` }),
      );
    }

    const response = await POST(await makeRequest({ offset: 2, limit: 2 }));
    const data = await response.json();

    expect(data.length).toBe(2);
    expect(data[0].thread_id).toBe("thread-2");
    expect(data[1].thread_id).toBe("thread-3");
  });

  test("sorts by updated_at desc by default", async () => {
    mockReaddirSync.mockReturnValueOnce([
      createThreadDir("thread-a"),
      createThreadDir("thread-b"),
    ]);
    mockReadFileSync
      .mockReturnValueOnce(
        createThreadJson({
          thread_id: "thread-a",
          updated_at: "2025-01-01T00:00:00Z",
        }),
      )
      .mockReturnValueOnce(
        createThreadJson({
          thread_id: "thread-b",
          updated_at: "2025-06-01T00:00:00Z",
        }),
      );

    const response = await POST(await makeRequest());
    const data = await response.json();

    expect(data[0].thread_id).toBe("thread-b");
    expect(data[1].thread_id).toBe("thread-a");
  });

  test("sorts by updated_at asc when specified", async () => {
    mockReaddirSync.mockReturnValueOnce([
      createThreadDir("thread-a"),
      createThreadDir("thread-b"),
    ]);
    mockReadFileSync
      .mockReturnValueOnce(
        createThreadJson({
          thread_id: "thread-a",
          updated_at: "2025-01-01T00:00:00Z",
        }),
      )
      .mockReturnValueOnce(
        createThreadJson({
          thread_id: "thread-b",
          updated_at: "2025-06-01T00:00:00Z",
        }),
      );

    const response = await POST(
      await makeRequest({ sortBy: "updated_at", sortOrder: "asc" }),
    );
    const data = await response.json();

    expect(data[0].thread_id).toBe("thread-a");
    expect(data[1].thread_id).toBe("thread-b");
  });

  test("sorts by created_at when specified", async () => {
    mockReaddirSync.mockReturnValueOnce([
      createThreadDir("thread-a"),
      createThreadDir("thread-b"),
    ]);
    mockReadFileSync
      .mockReturnValueOnce(
        createThreadJson({
          thread_id: "thread-a",
          created_at: "2025-06-01T00:00:00Z",
          updated_at: "2025-01-01T00:00:00Z",
        }),
      )
      .mockReturnValueOnce(
        createThreadJson({
          thread_id: "thread-b",
          created_at: "2025-01-01T00:00:00Z",
          updated_at: "2025-06-01T00:00:00Z",
        }),
      );

    const response = await POST(
      await makeRequest({ sortBy: "created_at", sortOrder: "desc" }),
    );
    const data = await response.json();

    expect(data[0].thread_id).toBe("thread-a");
    expect(data[1].thread_id).toBe("thread-b");
  });

  test("handles empty request body", async () => {
    mockReaddirSync.mockReturnValueOnce([createThreadDir("thread-1")]);
    mockReadFileSync.mockReturnValueOnce(createThreadJson());

    const response = await POST(await makeRequest());
    const data = await response.json();

    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBe(1);
  });

  test("returns empty array when no threads exist", async () => {
    mockReaddirSync.mockReturnValueOnce([]);

    const response = await POST(await makeRequest());
    const data = await response.json();

    expect(data).toEqual([]);
  });

  test("each thread result has thread_id field", async () => {
    mockReaddirSync.mockReturnValueOnce([createThreadDir("thread-1")]);
    mockReadFileSync.mockReturnValueOnce(
      createThreadJson({ thread_id: "thread-1" }),
    );

    const response = await POST(await makeRequest());
    const data = await response.json();

    expect(data[0]).toHaveProperty("thread_id", "thread-1");
  });

  test("handles NaN limit gracefully", async () => {
    mockReaddirSync.mockReturnValueOnce([
      createThreadDir("thread-1"),
      createThreadDir("thread-2"),
      createThreadDir("thread-3"),
    ]);
    mockReadFileSync.mockReturnValueOnce(
      createThreadJson({ thread_id: "thread-1" }),
    );
    mockReadFileSync.mockReturnValueOnce(
      createThreadJson({ thread_id: "thread-2" }),
    );
    mockReadFileSync.mockReturnValueOnce(
      createThreadJson({ thread_id: "thread-3" }),
    );

    const response = await POST(await makeRequest({ limit: NaN }));
    const data = await response.json();

    // NaN limit falls back to default of 50
    expect(data.length).toBe(3);
  });

  test("handles negative limit gracefully", async () => {
    mockReaddirSync.mockReturnValueOnce([
      createThreadDir("thread-1"),
      createThreadDir("thread-2"),
    ]);
    mockReadFileSync.mockReturnValueOnce(
      createThreadJson({ thread_id: "thread-1" }),
    );
    mockReadFileSync.mockReturnValueOnce(
      createThreadJson({ thread_id: "thread-2" }),
    );

    const response = await POST(await makeRequest({ limit: -5 }));
    const data = await response.json();

    // Negative limit is normalized to 0 via Math.max(0, Math.floor(-5)) = 0
    expect(data.length).toBe(0);
  });
});
