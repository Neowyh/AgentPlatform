import { renderHook, act } from "@testing-library/react";
import type { ReadonlyURLSearchParams } from "next/navigation";
import { describe, expect, test, vi, beforeEach } from "vitest";

vi.mock("next/navigation", () => ({
  useParams: vi.fn(() => ({ thread_id: "test-id" })),
  usePathname: vi.fn(() => "/chats/test-id"),
  useSearchParams: vi.fn(() => new URLSearchParams()),
}));

vi.mock("@/core/utils/uuid", () => ({
  uuid: vi.fn(() => "generated-uuid"),
}));

import { useThreadChat } from "@/components/workspace/chats/use-thread-chat";
import { useParams, usePathname, useSearchParams } from "next/navigation";

import { uuid } from "@/core/utils/uuid";

const mockUseParams = vi.mocked(useParams);
const mockUsePathname = vi.mocked(usePathname);
const mockUseSearchParams = vi.mocked(useSearchParams);
const mockUuid = vi.mocked(uuid);

beforeEach(() => {
  vi.clearAllMocks();
  mockUseParams.mockReturnValue({ thread_id: "test-id" });
  mockUsePathname.mockReturnValue("/chats/test-id");
  mockUseSearchParams.mockReturnValue(
    new URLSearchParams() as unknown as ReadonlyURLSearchParams,
  );
});

describe("useThreadChat", () => {
  test("returns the thread_id from the path when it is a normal id", () => {
    const { result } = renderHook(() => useThreadChat());
    expect(result.current.threadId).toBe("test-id");
    expect(result.current.isNewThread).toBe(false);
  });

  test("generates a UUID and sets isNewThread=true when path has 'new'", () => {
    mockUseParams.mockReturnValue({ thread_id: "new" });
    mockUsePathname.mockReturnValue("/chats/new");

    const { result } = renderHook(() => useThreadChat());
    expect(result.current.threadId).toBe("generated-uuid");
    expect(result.current.isNewThread).toBe(true);
    expect(mockUuid).toHaveBeenCalled();
  });

  test("isMock is true when search params contain mock=true", () => {
    mockUseSearchParams.mockReturnValue(
      new URLSearchParams("mock=true") as unknown as ReadonlyURLSearchParams,
    );
    const { result } = renderHook(() => useThreadChat());
    expect(result.current.isMock).toBe(true);
  });

  test("isMock is false when search params do not contain mock=true", () => {
    mockUseSearchParams.mockReturnValue(
      new URLSearchParams() as unknown as ReadonlyURLSearchParams,
    );
    const { result } = renderHook(() => useThreadChat());
    expect(result.current.isMock).toBe(false);
  });

  test("sets isNewThread=true when pathname ends with /new via useEffect", () => {
    mockUseParams.mockReturnValue({ thread_id: "test-id" });
    mockUsePathname.mockReturnValue("/chats/test-id");

    const { result, rerender } = renderHook(() => useThreadChat());
    expect(result.current.isNewThread).toBe(false);

    // Simulate navigation to /new
    mockUsePathname.mockReturnValue("/chats/new");
    rerender();

    expect(result.current.isNewThread).toBe(true);
  });

  test("setThreadId updates the threadId", () => {
    const { result } = renderHook(() => useThreadChat());
    expect(result.current.threadId).toBe("test-id");

    act(() => {
      result.current.setThreadId("new-thread-id");
    });

    expect(result.current.threadId).toBe("new-thread-id");
  });
});
