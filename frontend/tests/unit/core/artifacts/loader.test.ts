import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";

vi.mock("@/env", () => ({
  env: {
    NEXT_PUBLIC_BACKEND_BASE_URL: "",
    NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false",
  },
}));

vi.mock("@/core/static-mode", () => ({
  isStaticWebsiteOnly: vi.fn(() => false),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => ""),
}));

vi.mock("@/core/artifacts/preview", () => ({
  buildWriteFileDraftContent: vi.fn(),
}));

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

describe("loadArtifactContent", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("fetches artifact content and returns text with url", async () => {
    const { loadArtifactContent } = await import("@/core/artifacts/loader");

    mockFetch.mockResolvedValueOnce({
      text: () => Promise.resolve("<html>hello</html>"),
    });

    const result = await loadArtifactContent({
      filepath: "/mnt/user-data/outputs/report.html",
      threadId: "thread-1",
    });

    expect(result.content).toBe("<html>hello</html>");
    expect(result.url).toContain(
      "/api/threads/thread-1/artifacts/mnt/user-data/outputs/report.html",
    );
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  test("appends /SKILL.md to .skill file paths", async () => {
    const { loadArtifactContent } = await import("@/core/artifacts/loader");

    mockFetch.mockResolvedValueOnce({
      text: () => Promise.resolve("# Skill content"),
    });

    const result = await loadArtifactContent({
      filepath: "/mnt/user-data/outputs/my-tool.skill",
      threadId: "thread-1",
    });

    expect(result.url).toContain("my-tool.skill/SKILL.md");
    expect(result.content).toBe("# Skill content");
  });

  test("does not modify non-.skill file paths", async () => {
    const { loadArtifactContent } = await import("@/core/artifacts/loader");

    mockFetch.mockResolvedValueOnce({
      text: () => Promise.resolve("file content"),
    });

    await loadArtifactContent({
      filepath: "/mnt/user-data/outputs/data.json",
      threadId: "thread-2",
    });

    const calledUrl = mockFetch.mock.calls[0]![0] as string;
    expect(calledUrl).toContain("data.json");
    expect(calledUrl).not.toContain("SKILL.md");
  });

  test("passes isMock flag through to URL generation", async () => {
    const { loadArtifactContent } = await import("@/core/artifacts/loader");

    mockFetch.mockResolvedValueOnce({
      text: () => Promise.resolve("mock content"),
    });

    const result = await loadArtifactContent({
      filepath: "/mnt/user-data/outputs/report.html",
      threadId: "thread-1",
      isMock: true,
    });

    expect(result.url).toContain("/mock/api/threads/thread-1/artifacts");
    expect(result.content).toBe("mock content");
  });

  test("propagates fetch errors", async () => {
    const { loadArtifactContent } = await import("@/core/artifacts/loader");

    mockFetch.mockRejectedValueOnce(new Error("Network error"));

    await expect(
      loadArtifactContent({
        filepath: "/mnt/user-data/outputs/report.html",
        threadId: "thread-1",
      }),
    ).rejects.toThrow("Network error");
  });

  test("handles non-OK responses by returning the response text", async () => {
    const { loadArtifactContent } = await import("@/core/artifacts/loader");

    mockFetch.mockResolvedValueOnce({
      text: () => Promise.resolve("Not Found"),
    });

    const result = await loadArtifactContent({
      filepath: "/nonexistent/file.txt",
      threadId: "thread-1",
    });

    expect(result.content).toBe("Not Found");
  });

  test("normalizes paths without leading slash", async () => {
    const { loadArtifactContent } = await import("@/core/artifacts/loader");

    mockFetch.mockResolvedValueOnce({
      text: () => Promise.resolve("data"),
    });

    await loadArtifactContent({
      filepath: "mnt/user-data/outputs/file.txt",
      threadId: "thread-1",
    });

    const calledUrl = mockFetch.mock.calls[0]![0] as string;
    expect(calledUrl).toContain(
      "/api/threads/thread-1/artifacts/mnt/user-data/outputs/file.txt",
    );
  });

  test("handles .skill file with nested path correctly", async () => {
    const { loadArtifactContent } = await import("@/core/artifacts/loader");

    mockFetch.mockResolvedValueOnce({
      text: () => Promise.resolve("skill md content"),
    });

    const result = await loadArtifactContent({
      filepath: "/user-data/skills/analysis.skill",
      threadId: "thread-3",
    });

    expect(result.url).toContain("analysis.skill/SKILL.md");
    expect(result.content).toBe("skill md content");
  });
});

describe("loadArtifactContentFromToolCall", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("returns content from a matching tool call when message and tool call are found", async () => {
    const { loadArtifactContentFromToolCall } =
      await import("@/core/artifacts/loader");

    const mockThread = {
      messages: [
        {
          id: "msg-1",
          type: "ai",
          tool_calls: [
            {
              id: "tc-1",
              name: "write_file",
              args: { path: "/output/file.txt", content: "file content" },
            },
          ],
        },
      ],
    } as any;

    const result = loadArtifactContentFromToolCall({
      url: "write-file:/output/file.txt?message_id=msg-1&tool_call_id=tc-1",
      thread: mockThread,
    });

    expect(result).toBe("file content");
  });

  test("returns undefined when message_id does not match any message", async () => {
    const { loadArtifactContentFromToolCall } =
      await import("@/core/artifacts/loader");

    const mockThread = {
      messages: [
        {
          id: "msg-1",
          type: "ai",
          tool_calls: [
            {
              id: "tc-1",
              name: "write_file",
              args: { path: "/output/file.txt", content: "file content" },
            },
          ],
        },
      ],
    } as any;

    const result = loadArtifactContentFromToolCall({
      url: "write-file:/output/file.txt?message_id=nonexistent&tool_call_id=tc-1",
      thread: mockThread,
    });

    expect(result).toBeUndefined();
  });

  test("returns undefined when tool_call_id does not match any tool call", async () => {
    const { loadArtifactContentFromToolCall } =
      await import("@/core/artifacts/loader");

    const mockThread = {
      messages: [
        {
          id: "msg-1",
          type: "ai",
          tool_calls: [
            {
              id: "tc-1",
              name: "write_file",
              args: { path: "/output/file.txt", content: "file content" },
            },
          ],
        },
      ],
    } as any;

    const result = loadArtifactContentFromToolCall({
      url: "write-file:/output/file.txt?message_id=msg-1&tool_call_id=nonexistent",
      thread: mockThread,
    });

    expect(result).toBeUndefined();
  });

  test("returns undefined when message is not of type ai", async () => {
    const { loadArtifactContentFromToolCall } =
      await import("@/core/artifacts/loader");

    const mockThread = {
      messages: [
        {
          id: "msg-1",
          type: "human",
          tool_calls: [
            {
              id: "tc-1",
              name: "write_file",
              args: { path: "/output/file.txt", content: "file content" },
            },
          ],
        },
      ],
    } as any;

    const result = loadArtifactContentFromToolCall({
      url: "write-file:/output/file.txt?message_id=msg-1&tool_call_id=tc-1",
      thread: mockThread,
    });

    expect(result).toBeUndefined();
  });

  test("returns undefined when message has no tool_calls", async () => {
    const { loadArtifactContentFromToolCall } =
      await import("@/core/artifacts/loader");

    const mockThread = {
      messages: [
        {
          id: "msg-1",
          type: "ai",
        },
      ],
    } as any;

    const result = loadArtifactContentFromToolCall({
      url: "write-file:/output/file.txt?message_id=msg-1&tool_call_id=tc-1",
      thread: mockThread,
    });

    expect(result).toBeUndefined();
  });

  test("returns draft content from buildWriteFileDraftContent when available", async () => {
    const { buildWriteFileDraftContent } =
      await import("@/core/artifacts/preview");
    vi.mocked(buildWriteFileDraftContent).mockReturnValueOnce("draft content");

    const { loadArtifactContentFromToolCall } =
      await import("@/core/artifacts/loader");

    const mockThread = {
      messages: [],
    } as any;

    const result = loadArtifactContentFromToolCall({
      url: "write-file:/output/file.txt?message_id=msg-1&tool_call_id=tc-1",
      thread: mockThread,
    });

    expect(result).toBe("draft content");
    expect(buildWriteFileDraftContent).toHaveBeenCalled();
  });

  test("falls back to URL param parsing when buildWriteFileDraftContent returns undefined", async () => {
    const { buildWriteFileDraftContent } =
      await import("@/core/artifacts/preview");
    vi.mocked(buildWriteFileDraftContent).mockReturnValueOnce(undefined);

    const { loadArtifactContentFromToolCall } =
      await import("@/core/artifacts/loader");

    const mockThread = {
      messages: [
        {
          id: "msg-1",
          type: "ai",
          tool_calls: [
            {
              id: "tc-1",
              name: "write_file",
              args: { path: "/output/file.txt", content: "fallback content" },
            },
          ],
        },
      ],
    } as any;

    const result = loadArtifactContentFromToolCall({
      url: "write-file:/output/file.txt?message_id=msg-1&tool_call_id=tc-1",
      thread: mockThread,
    });

    expect(result).toBe("fallback content");
  });

  test("returns undefined when neither draft content nor tool call match is found", async () => {
    const { buildWriteFileDraftContent } =
      await import("@/core/artifacts/preview");
    vi.mocked(buildWriteFileDraftContent).mockReturnValueOnce(undefined);

    const { loadArtifactContentFromToolCall } =
      await import("@/core/artifacts/loader");

    const mockThread = {
      messages: [],
    } as any;

    const result = loadArtifactContentFromToolCall({
      url: "write-file:/output/file.txt?message_id=msg-1&tool_call_id=tc-1",
      thread: mockThread,
    });

    expect(result).toBeUndefined();
  });

  test("handles URL with encoded filepath by falling back to tool call lookup", async () => {
    const { buildWriteFileDraftContent } =
      await import("@/core/artifacts/preview");
    // buildWriteFileDraftContent returns undefined because encoded path won't match raw path
    vi.mocked(buildWriteFileDraftContent).mockReturnValueOnce(undefined);

    const { loadArtifactContentFromToolCall } =
      await import("@/core/artifacts/loader");

    const mockThread = {
      messages: [
        {
          id: "msg-1",
          type: "ai",
          tool_calls: [
            {
              id: "tc-1",
              name: "write_file",
              args: { path: "/output/my file.txt", content: "encoded content" },
            },
          ],
        },
      ],
    } as any;

    const result = loadArtifactContentFromToolCall({
      url: "write-file:/output/my%20file.txt?message_id=msg-1&tool_call_id=tc-1",
      thread: mockThread,
    });

    // Falls back to URL param lookup, which finds the tool call by id
    expect(result).toBe("encoded content");
  });

  test("handles missing query parameters gracefully", async () => {
    const { buildWriteFileDraftContent } =
      await import("@/core/artifacts/preview");
    vi.mocked(buildWriteFileDraftContent).mockReturnValueOnce(undefined);

    const { loadArtifactContentFromToolCall } =
      await import("@/core/artifacts/loader");

    const mockThread = {
      messages: [],
    } as any;

    const result = loadArtifactContentFromToolCall({
      url: "write-file:/output/file.txt",
      thread: mockThread,
    });

    expect(result).toBeUndefined();
  });
});
