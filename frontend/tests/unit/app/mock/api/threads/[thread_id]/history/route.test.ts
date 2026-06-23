import { describe, test, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";

vi.mock("fs", () => ({
  default: {
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

import { POST } from "@/app/mock/api/threads/[thread_id]/history/route";

const mockReadFileSync = vi.mocked(fs.readFileSync);
const mockPathResolve = vi.mocked(path.resolve);

function makeParams(threadId: string) {
  return { params: Promise.resolve({ thread_id: threadId }) };
}

describe("mock history route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPathResolve.mockImplementation((...args: string[]) => args.join("/"));
  });

  test("POST returns single-element array when no history field", async () => {
    const threadData = {
      thread_id: "test-123",
      title: "Test Thread",
    };
    mockReadFileSync.mockReturnValueOnce(JSON.stringify(threadData));

    const request = new NextRequest(
      "http://localhost/api/threads/test-123/history",
      {
        method: "POST",
      },
    );
    const response = await POST(request, makeParams("test-123"));
    const data = await response.json();

    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBe(1);
    expect(data[0].thread_id).toBe("test-123");
  });

  test("POST returns full json when history field is an array", async () => {
    const threadData = {
      thread_id: "test-456",
      history: [
        { type: "human", content: "Hello" },
        { type: "ai", content: "Hi there" },
      ],
    };
    mockReadFileSync.mockReturnValueOnce(JSON.stringify(threadData));

    const request = new NextRequest(
      "http://localhost/api/threads/test-456/history",
      {
        method: "POST",
      },
    );
    const response = await POST(request, makeParams("test-456"));
    const data = await response.json();

    // When history is an array, the route returns the full json object
    expect(data).toHaveProperty("thread_id", "test-456");
    expect(data.history).toEqual(threadData.history);
  });

  test("POST returns full json when history is an empty array", async () => {
    const threadData = {
      thread_id: "test-789",
      history: [],
    };
    mockReadFileSync.mockReturnValueOnce(JSON.stringify(threadData));

    const request = new NextRequest(
      "http://localhost/api/threads/test-789/history",
      {
        method: "POST",
      },
    );
    const response = await POST(request, makeParams("test-789"));
    const data = await response.json();

    // history: [] is an array, so the route returns the full json object
    expect(data).toHaveProperty("thread_id", "test-789");
    expect(data).toHaveProperty("history");
  });

  test("reads thread.json from correct path", async () => {
    mockReadFileSync.mockReturnValueOnce(JSON.stringify({ thread_id: "abc" }));

    const request = new NextRequest(
      "http://localhost/api/threads/abc/history",
      {
        method: "POST",
      },
    );
    await POST(request, makeParams("abc"));

    expect(mockReadFileSync).toHaveBeenCalledOnce();
    const [filePath] = mockReadFileSync.mock.calls[0]!;
    expect(filePath).toContain("abc/thread.json");
  });

  test("returns Response with JSON content type", async () => {
    mockReadFileSync.mockReturnValueOnce(JSON.stringify({ thread_id: "x" }));

    const request = new NextRequest("http://localhost/api/threads/x/history", {
      method: "POST",
    });
    const response = await POST(request, makeParams("x"));

    expect(response.headers.get("content-type")).toContain("application/json");
  });
});
