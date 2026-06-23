import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockScrollToBottom = vi.fn();
let mockIsAtBottom = true;

vi.mock("use-stick-to-bottom", () => ({
  useStickToBottomContext: () => ({
    isAtBottom: mockIsAtBottom,
    scrollToBottom: mockScrollToBottom,
  }),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

import { ConversationScrollButton } from "@/components/ai-elements/conversation";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  mockIsAtBottom = true;
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("ConversationScrollButton", () => {
  test("does not render when isAtBottom is true", () => {
    mockIsAtBottom = true;
    const { container } = render(<ConversationScrollButton />);
    expect(container.innerHTML).toBe("");
  });

  test("renders when isAtBottom is false", () => {
    mockIsAtBottom = false;
    render(<ConversationScrollButton data-testid="scroll-btn" />);
    expect(screen.getByTestId("scroll-btn")).toBeInTheDocument();
  });

  test("calls scrollToBottom on click", () => {
    mockIsAtBottom = false;
    render(<ConversationScrollButton data-testid="scroll-btn" />);
    fireEvent.click(screen.getByTestId("scroll-btn"));
    expect(mockScrollToBottom).toHaveBeenCalledTimes(1);
  });

  test("has arrow down icon", () => {
    mockIsAtBottom = false;
    render(<ConversationScrollButton data-testid="scroll-btn" />);
    const svg = screen.getByTestId("scroll-btn").querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  test("applies custom className", () => {
    mockIsAtBottom = false;
    render(
      <ConversationScrollButton
        className="custom-scroll"
        data-testid="scroll-btn"
      />,
    );
    expect(screen.getByTestId("scroll-btn")).toHaveClass("custom-scroll");
  });

  test("renders as button with correct type and variant", () => {
    mockIsAtBottom = false;
    render(<ConversationScrollButton data-testid="scroll-btn" />);
    const btn = screen.getByTestId("scroll-btn");
    expect(btn.tagName).toBe("BUTTON");
    expect(btn).toHaveAttribute("type", "button");
  });
});
