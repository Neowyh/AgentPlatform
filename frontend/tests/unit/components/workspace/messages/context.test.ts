import { renderHook } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, test } from "vitest";

import {
  ThreadContext,
  useThread,
} from "@/components/workspace/messages/context";

describe("ThreadContext", () => {
  test("is defined", () => {
    expect(ThreadContext).toBeDefined();
  });
});

describe("useThread", () => {
  test("throws when used outside provider", () => {
    expect(() => {
      renderHook(() => useThread());
    }).toThrow("useThread must be used within a ThreadContext");
  });

  test("returns context value when used inside provider", () => {
    const mockValue = { thread: {} as any, isMock: true };
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      createElement(ThreadContext.Provider, { value: mockValue }, children);

    const { result } = renderHook(() => useThread(), { wrapper });

    expect(result.current).toBe(mockValue);
    expect(result.current.thread).toBeDefined();
    expect(result.current.isMock).toBe(true);
  });
});
