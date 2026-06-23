import { render, screen, cleanup, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: (_target, prop: string) => {
        if (prop === "create") {
          return (Component: React.ComponentType) => Component;
        }
        return React.forwardRef(
          (
            { children, ...props }: Record<string, unknown>,
            ref: React.Ref<HTMLElement>,
          ) =>
            React.createElement(
              prop,
              { ...props, ref },
              children as React.ReactNode,
            ),
        );
      },
    },
  ),
  AnimatePresence: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

import React from "react";

vi.mock("@/components/ui/aurora-text", () => ({
  AuroraText: ({ children }: { children: React.ReactNode }) => (
    <span data-testid="aurora-text">{children}</span>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let WordRotate: typeof import("@/components/ui/word-rotate").WordRotate;

beforeEach(async () => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  const mod = await import("@/components/ui/word-rotate");
  WordRotate = mod.WordRotate;
});

afterEach(() => {
  vi.useRealTimers();
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("WordRotate", () => {
  test("renders the first word initially", () => {
    render(<WordRotate words={["Hello", "World"]} />);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  test("renders AuroraText component", () => {
    render(<WordRotate words={["Test"]} />);
    expect(screen.getByTestId("aurora-text")).toBeInTheDocument();
  });

  test("rotates to next word after duration", () => {
    render(<WordRotate words={["First", "Second"]} duration={1000} />);
    expect(screen.getByText("First")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByText("Second")).toBeInTheDocument();
  });

  test("wraps around to first word after last word", () => {
    render(<WordRotate words={["A", "B", "C"]} duration={500} />);
    expect(screen.getByText("A")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(screen.getByText("B")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(screen.getByText("C")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(screen.getByText("A")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    const { container } = render(
      <WordRotate words={["Word"]} className="my-rotate" />,
    );
    expect(container.firstElementChild).toHaveAttribute(
      "class",
      expect.stringContaining("overflow-hidden"),
    );
  });

  test("uses custom duration", () => {
    render(<WordRotate words={["X", "Y"]} duration={2000} />);
    expect(screen.getByText("X")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(screen.getByText("Y")).toBeInTheDocument();
  });

  test("renders single word correctly", () => {
    render(<WordRotate words={["Only"]} />);
    expect(screen.getByText("Only")).toBeInTheDocument();
  });

  test("cleans up interval on unmount", () => {
    const clearIntervalSpy = vi.spyOn(global, "clearInterval");
    const { unmount } = render(<WordRotate words={["A", "B"]} />);
    unmount();
    expect(clearIntervalSpy).toHaveBeenCalled();
    clearIntervalSpy.mockRestore();
  });
});
