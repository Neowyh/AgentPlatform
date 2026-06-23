import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
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

vi.mock("@/components/workspace/messages/context", () => ({
  useThread: vi.fn(),
}));

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: queryClient },
      children,
    );
  };
}

describe("useArtifactContent", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("returns artifact content from fetch for non-write-file paths", async () => {
    const { useThread } =
      await import("@/components/workspace/messages/context");
    vi.mocked(useThread).mockReturnValue({
      thread: { messages: [] } as any,
      isMock: false,
    });

    mockFetch.mockResolvedValueOnce({
      text: () => Promise.resolve("<html>artifact content</html>"),
    });

    const { useArtifactContent } = await import("@/core/artifacts/hooks");
    const { result } = renderHook(
      () =>
        useArtifactContent({
          filepath: "/mnt/user-data/outputs/report.html",
          threadId: "thread-1",
          enabled: true,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.content).toBe("<html>artifact content</html>");
    expect(result.current.url).toContain(
      "/api/threads/thread-1/artifacts/mnt/user-data/outputs/report.html",
    );
    expect(result.current.error).toBeNull();
  });

  test("returns content from tool call for write-file: prefixed paths", async () => {
    const { buildWriteFileDraftContent } =
      await import("@/core/artifacts/preview");
    vi.mocked(buildWriteFileDraftContent).mockReturnValueOnce(
      "draft file content",
    );

    const { useThread } =
      await import("@/components/workspace/messages/context");
    vi.mocked(useThread).mockReturnValue({
      thread: { messages: [] } as any,
      isMock: false,
    });

    const { useArtifactContent } = await import("@/core/artifacts/hooks");
    const { result } = renderHook(
      () =>
        useArtifactContent({
          filepath:
            "write-file:/output/file.txt?message_id=msg-1&tool_call_id=tc-1",
          threadId: "thread-1",
          enabled: true,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.content).toBe("draft file content");
    });

    expect(result.current.url).toBeUndefined();
  });

  test("returns null content for write-file paths when draft is undefined", async () => {
    const { buildWriteFileDraftContent } =
      await import("@/core/artifacts/preview");
    vi.mocked(buildWriteFileDraftContent).mockReturnValueOnce(undefined);

    const { useThread } =
      await import("@/components/workspace/messages/context");
    vi.mocked(useThread).mockReturnValue({
      thread: { messages: [] } as any,
      isMock: false,
    });

    const { useArtifactContent } = await import("@/core/artifacts/hooks");
    const { result } = renderHook(
      () =>
        useArtifactContent({
          filepath:
            "write-file:/output/file.txt?message_id=msg-1&tool_call_id=tc-1",
          threadId: "thread-1",
          enabled: true,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.content).toBeUndefined();
  });

  test("does not fetch when enabled is false", async () => {
    const { useThread } =
      await import("@/components/workspace/messages/context");
    vi.mocked(useThread).mockReturnValue({
      thread: { messages: [] } as any,
      isMock: false,
    });

    const { useArtifactContent } = await import("@/core/artifacts/hooks");
    const { result } = renderHook(
      () =>
        useArtifactContent({
          filepath: "/mnt/user-data/outputs/report.html",
          threadId: "thread-1",
          enabled: false,
        }),
      { wrapper: createWrapper() },
    );

    // Wait a tick to ensure no fetch is triggered
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(mockFetch).not.toHaveBeenCalled();
    // When query is disabled, isLoading is false (query is idle, not loading)
    expect(result.current.isLoading).toBe(false);
  });

  test("reports loading state correctly", async () => {
    const { useThread } =
      await import("@/components/workspace/messages/context");
    vi.mocked(useThread).mockReturnValue({
      thread: { messages: [] } as any,
      isMock: false,
    });

    // Create a deferred promise to control when fetch resolves
    let resolveFetch: (value: any) => void;
    const fetchPromise = new Promise((resolve) => {
      resolveFetch = resolve;
    });
    mockFetch.mockReturnValueOnce(fetchPromise);

    const { useArtifactContent } = await import("@/core/artifacts/hooks");
    const { result } = renderHook(
      () =>
        useArtifactContent({
          filepath: "/mnt/user-data/outputs/report.html",
          threadId: "thread-1",
          enabled: true,
        }),
      { wrapper: createWrapper() },
    );

    expect(result.current.isLoading).toBe(true);

    resolveFetch!({
      text: () => Promise.resolve("resolved content"),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.content).toBe("resolved content");
  });

  test("reports error when fetch fails", async () => {
    const { useThread } =
      await import("@/components/workspace/messages/context");
    vi.mocked(useThread).mockReturnValue({
      thread: { messages: [] } as any,
      isMock: false,
    });

    mockFetch.mockRejectedValueOnce(new Error("Fetch failed"));

    const { useArtifactContent } = await import("@/core/artifacts/hooks");
    const { result } = renderHook(
      () =>
        useArtifactContent({
          filepath: "/mnt/user-data/outputs/report.html",
          threadId: "thread-1",
          enabled: true,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.content).toBeUndefined();
    expect(result.current.error).toBeDefined();
  });

  test("passes isMock flag to the loader", async () => {
    const { useThread } =
      await import("@/components/workspace/messages/context");
    vi.mocked(useThread).mockReturnValue({
      thread: { messages: [] } as any,
      isMock: true,
    });

    mockFetch.mockResolvedValueOnce({
      text: () => Promise.resolve("mock content"),
    });

    const { useArtifactContent } = await import("@/core/artifacts/hooks");
    const { result } = renderHook(
      () =>
        useArtifactContent({
          filepath: "/mnt/user-data/outputs/report.html",
          threadId: "thread-1",
          enabled: true,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const calledUrl = mockFetch.mock.calls[0]![0] as string;
    expect(calledUrl).toContain("/mock/api/threads/thread-1/artifacts");
    expect(result.current.content).toBe("mock content");
  });

  test("uses correct query key including isMock", async () => {
    const { useThread } =
      await import("@/components/workspace/messages/context");
    vi.mocked(useThread).mockReturnValue({
      thread: { messages: [] } as any,
      isMock: true,
    });

    mockFetch.mockResolvedValue({
      text: () => Promise.resolve("content"),
    });

    const { useArtifactContent } = await import("@/core/artifacts/hooks");
    const { result, unmount } = renderHook(
      () =>
        useArtifactContent({
          filepath: "/test/file.html",
          threadId: "thread-1",
          enabled: true,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    unmount();
  });

  test("handles .skill file paths by appending SKILL.md", async () => {
    const { useThread } =
      await import("@/components/workspace/messages/context");
    vi.mocked(useThread).mockReturnValue({
      thread: { messages: [] } as any,
      isMock: false,
    });

    mockFetch.mockResolvedValueOnce({
      text: () => Promise.resolve("# Skill content"),
    });

    const { useArtifactContent } = await import("@/core/artifacts/hooks");
    const { result } = renderHook(
      () =>
        useArtifactContent({
          filepath: "/mnt/user-data/outputs/my-skill.skill",
          threadId: "thread-1",
          enabled: true,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const calledUrl = mockFetch.mock.calls[0]![0] as string;
    expect(calledUrl).toContain("my-skill.skill/SKILL.md");
    expect(result.current.content).toBe("# Skill content");
  });

  test("does not provide url for write-file paths", async () => {
    const { buildWriteFileDraftContent } =
      await import("@/core/artifacts/preview");
    vi.mocked(buildWriteFileDraftContent).mockReturnValueOnce("draft");

    const { useThread } =
      await import("@/components/workspace/messages/context");
    vi.mocked(useThread).mockReturnValue({
      thread: { messages: [] } as any,
      isMock: false,
    });

    const { useArtifactContent } = await import("@/core/artifacts/hooks");
    const { result } = renderHook(
      () =>
        useArtifactContent({
          filepath:
            "write-file:/output/file.txt?message_id=msg-1&tool_call_id=tc-1",
          threadId: "thread-1",
          enabled: true,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.content).toBe("draft");
    });

    expect(result.current.url).toBeUndefined();
  });
});
