import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/components/ui/skeleton", () => ({
  Skeleton: ({ className }: { className?: string }) => (
    <div data-testid="skeleton" className={className} />
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let MessageListSkeleton: typeof import("@/components/workspace/messages/skeleton").MessageListSkeleton;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/workspace/messages/skeleton");
  MessageListSkeleton = mod.MessageListSkeleton;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("MessageListSkeleton", () => {
  test("renders the skeleton container", () => {
    const { container } = render(<MessageListSkeleton />);
    expect(container.firstElementChild).toBeInTheDocument();
  });

  test("renders human message skeleton", () => {
    render(<MessageListSkeleton />);
    const humanMessage = screen.getByRole("human-message");
    expect(humanMessage).toBeInTheDocument();
  });

  test("renders assistant message skeleton", () => {
    render(<MessageListSkeleton />);
    const assistantMessage = screen.getByRole("assistant-message");
    expect(assistantMessage).toBeInTheDocument();
  });

  test("renders skeleton bars inside human message", () => {
    render(<MessageListSkeleton />);
    const humanMessage = screen.getByRole("human-message");
    const skeletons = humanMessage.querySelectorAll('[data-testid="skeleton"]');
    expect(skeletons.length).toBe(2);
  });

  test("renders skeleton bars inside assistant message", () => {
    render(<MessageListSkeleton />);
    const assistantMessage = screen.getByRole("assistant-message");
    const skeletons = assistantMessage.querySelectorAll(
      '[data-testid="skeleton"]',
    );
    expect(skeletons.length).toBe(8);
  });

  test("renders total of 10 skeleton bars", () => {
    render(<MessageListSkeleton />);
    const allSkeletons = screen.getAllByTestId("skeleton");
    expect(allSkeletons.length).toBe(10);
  });

  test("skeleton bars have animation delay styles", () => {
    render(<MessageListSkeleton />);
    const humanMessage = screen.getByRole("human-message");
    const animatedDivs = humanMessage.querySelectorAll("[style]");
    expect(animatedDivs.length).toBeGreaterThan(0);
  });

  test("skeleton bars have overflow-hidden", () => {
    render(<MessageListSkeleton />);
    const allSkeletons = screen.getAllByTestId("skeleton");
    const wrapper = allSkeletons[0]!.parentElement;
    expect(wrapper?.getAttribute("class")).toContain("overflow-hidden");
  });
});
