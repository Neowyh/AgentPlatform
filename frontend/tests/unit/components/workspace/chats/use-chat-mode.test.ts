import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";

const mockSetInput = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: vi.fn(),
  useSearchParams: vi.fn(),
}));

vi.mock("@/components/ai-elements/prompt-input", () => ({
  usePromptInputController: vi.fn(() => ({
    textInput: { setInput: mockSetInput },
  })),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: vi.fn(() => ({
    t: { inputBox: { createSkillPrompt: "Create a skill..." } },
  })),
}));

vi.mock("react", async () => {
  const actual = await vi.importActual<typeof import("react")>("react");
  return {
    ...actual,
    useEffect: actual.useEffect,
    useMemo: actual.useMemo,
    useRef: actual.useRef,
  };
});

import { renderHook } from "@testing-library/react";
import { useParams, useSearchParams } from "next/navigation";

import { usePromptInputController } from "@/components/ai-elements/prompt-input";
import { useSpecificChatMode } from "@/components/workspace/chats/use-chat-mode";
import { useI18n } from "@/core/i18n/hooks";

describe("useSpecificChatMode", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("sets initial prompt when thread_id is 'new' and mode is 'skill'", () => {
    vi.mocked(useParams).mockReturnValue({ thread_id: "new" });
    vi.mocked(useSearchParams).mockReturnValue(
      new URLSearchParams("mode=skill") as unknown as ReturnType<
        typeof useSearchParams
      >,
    );

    const { result } = renderHook(() => useSpecificChatMode());
    expect(result).toBeDefined();

    vi.advanceTimersByTime(150);
    expect(mockSetInput).toHaveBeenCalledWith("Create a skill...");
  });

  test("does not set initial prompt when thread_id is not 'new'", () => {
    vi.mocked(useParams).mockReturnValue({ thread_id: "abc-123" });
    vi.mocked(useSearchParams).mockReturnValue(
      new URLSearchParams("mode=skill") as unknown as ReturnType<
        typeof useSearchParams
      >,
    );

    renderHook(() => useSpecificChatMode());

    vi.advanceTimersByTime(150);
    expect(mockSetInput).not.toHaveBeenCalled();
  });

  test("does not set initial prompt when mode is not 'skill'", () => {
    vi.mocked(useParams).mockReturnValue({ thread_id: "new" });
    vi.mocked(useSearchParams).mockReturnValue(
      new URLSearchParams("mode=chat") as unknown as ReturnType<
        typeof useSearchParams
      >,
    );

    renderHook(() => useSpecificChatMode());

    vi.advanceTimersByTime(150);
    expect(mockSetInput).not.toHaveBeenCalled();
  });

  test("sets initial prompt from '?prompt=' param when thread_id is 'new'", () => {
    vi.mocked(useParams).mockReturnValue({ thread_id: "new" });
    vi.mocked(useSearchParams).mockReturnValue(
      new URLSearchParams("prompt=hello%20world") as unknown as ReturnType<
        typeof useSearchParams
      >,
    );

    renderHook(() => useSpecificChatMode());

    vi.advanceTimersByTime(150);
    expect(mockSetInput).toHaveBeenCalledWith("hello world");
  });

  test("does not set initial prompt when there are no search params", () => {
    vi.mocked(useParams).mockReturnValue({ thread_id: "new" });
    vi.mocked(useSearchParams).mockReturnValue(
      new URLSearchParams("") as unknown as ReturnType<typeof useSearchParams>,
    );

    renderHook(() => useSpecificChatMode());

    vi.advanceTimersByTime(150);
    expect(mockSetInput).not.toHaveBeenCalled();
  });

  test("focuses textarea and sets selection range after setInput", () => {
    const mockFocus = vi.fn();
    const mockTextarea = {
      focus: mockFocus,
      selectionStart: 0,
      selectionEnd: 0,
      value: "Create a skill...",
    };
    const originalQuerySelector = document.querySelector.bind(document);
    document.querySelector = vi.fn().mockImplementation((selector: string) => {
      if (selector === "textarea") return mockTextarea as unknown as Element;
      return originalQuerySelector(selector);
      test("re-prefills when the same prompt param reappears after being cleared", () => {
        vi.mocked(useParams).mockReturnValue({ thread_id: "new" });

        // First: prompt present
        vi.mocked(useSearchParams).mockReturnValue(
          new URLSearchParams("prompt=hello") as unknown as ReturnType<
            typeof useSearchParams
          >,
        );

        const { rerender } = renderHook(() => useSpecificChatMode());
        vi.advanceTimersByTime(150);
        expect(mockSetInput).toHaveBeenCalledWith("hello");

        // Then: navigate to same route without prompt (component does NOT remount)
        vi.mocked(useSearchParams).mockReturnValue(
          new URLSearchParams("") as unknown as ReturnType<
            typeof useSearchParams
          >,
        );
        rerender();
        vi.advanceTimersByTime(150);
        expect(mockSetInput).toHaveBeenCalledTimes(1);

        // Back to the same prompt URL — should fire again
        vi.mocked(useSearchParams).mockReturnValue(
          new URLSearchParams("prompt=hello") as unknown as ReturnType<
            typeof useSearchParams
          >,
        );
        rerender();
        vi.advanceTimersByTime(150);
        expect(mockSetInput).toHaveBeenCalledTimes(2);
        expect(mockSetInput).toHaveBeenLastCalledWith("hello");
      });
    });

    vi.mocked(useParams).mockReturnValue({ thread_id: "new" });
    vi.mocked(useSearchParams).mockReturnValue(
      new URLSearchParams("mode=skill") as unknown as ReturnType<
        typeof useSearchParams
      >,
    );

    renderHook(() => useSpecificChatMode());

    vi.advanceTimersByTime(150);
    expect(mockSetInput).toHaveBeenCalledWith("Create a skill...");
    expect(mockFocus).toHaveBeenCalled();
    expect(mockTextarea.selectionStart).toBe(mockTextarea.value.length);
    expect(mockTextarea.selectionEnd).toBe(mockTextarea.value.length);

    document.querySelector = originalQuerySelector;
  });

  test("does not call setInput again when inputInitialValue stays the same on re-render (dedup)", () => {
    vi.mocked(useParams).mockReturnValue({ thread_id: "new" });
    vi.mocked(useSearchParams).mockReturnValue(
      new URLSearchParams("mode=skill") as unknown as ReturnType<
        typeof useSearchParams
      >,
    );

    const { rerender } = renderHook(() => useSpecificChatMode());

    vi.advanceTimersByTime(150);
    expect(mockSetInput).toHaveBeenCalledTimes(1);

    // Re-render with same params - effect deps unchanged, should not re-run
    rerender();
    vi.advanceTimersByTime(150);
    expect(mockSetInput).toHaveBeenCalledTimes(1);
  });

  test("updates setInputRef when promptInputController changes and triggers effect with new value", () => {
    const mockSetInput2 = vi.fn();

    vi.mocked(useParams).mockReturnValue({ thread_id: "new" });
    vi.mocked(useSearchParams).mockReturnValue(
      new URLSearchParams("mode=skill") as unknown as ReturnType<
        typeof useSearchParams
      >,
    );

    const { rerender } = renderHook(() => useSpecificChatMode());

    vi.advanceTimersByTime(150);
    expect(mockSetInput).toHaveBeenCalledWith("Create a skill...");

    // Change the promptInputController to return a different setInput
    vi.mocked(usePromptInputController).mockReturnValue({
      textInput: { setInput: mockSetInput2 },
    } as unknown as ReturnType<typeof usePromptInputController>);

    // Change i18n to return a different prompt to trigger the effect
    vi.mocked(useI18n).mockReturnValue({
      t: { inputBox: { createSkillPrompt: "Different prompt..." } },
    } as unknown as ReturnType<typeof useI18n>);

    rerender();
    vi.advanceTimersByTime(150);

    // The new setInput should be called with the new prompt
    expect(mockSetInput2).toHaveBeenCalledWith("Different prompt...");
    // The old setInput should not be called again
    expect(mockSetInput).toHaveBeenCalledTimes(1);
  });
});
