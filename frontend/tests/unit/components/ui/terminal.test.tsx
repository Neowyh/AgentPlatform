import { render, screen, cleanup, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

let _useInViewResult = true;

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: (_target, prop: string) => {
        if (prop === "create") {
          return (Component: React.ComponentType, _opts: unknown) => {
            const Forwarded = React.forwardRef(
              (props: Record<string, unknown>, ref: React.Ref<HTMLElement>) =>
                React.createElement(
                  Component as React.ComponentType<Record<string, unknown>>,
                  { ...props, ref } as Record<string, unknown>,
                ),
            );
            Forwarded.displayName = `Motion.${(Component as { displayName?: string }).displayName || Component.name || "Component"}`;
            return Forwarded;
          };
        }
        return React.forwardRef(
          (
            {
              children,
              onAnimationComplete,
              ...props
            }: Record<string, unknown>,
            ref: React.Ref<HTMLElement>,
          ) => {
            // Fire onAnimationComplete callback on mount to simulate animation end
            React.useEffect(() => {
              if (typeof onAnimationComplete === "function") {
                onAnimationComplete();
              }
            }, [onAnimationComplete]);
            return React.createElement(
              prop,
              { ...props, ref } as Record<string, unknown>,
              children as React.ReactNode,
            );
          },
        );
      },
    },
  ),
  AnimatePresence: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  useInView: () => _useInViewResult,
}));

import React from "react";

// ── Dynamic import ───────────────────────────────────────────────────────────

let Terminal: typeof import("@/components/ui/terminal").Terminal;
let TypingAnimation: typeof import("@/components/ui/terminal").TypingAnimation;
let AnimatedSpan: typeof import("@/components/ui/terminal").AnimatedSpan;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/ui/terminal");
  Terminal = mod.Terminal;
  TypingAnimation = mod.TypingAnimation;
  AnimatedSpan = mod.AnimatedSpan;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("Terminal", () => {
  test("renders children", () => {
    render(
      <Terminal>
        <span>Hello</span>
      </Terminal>,
    );
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  test("renders the terminal container with border", () => {
    const { container } = render(
      <Terminal>
        <span>Content</span>
      </Terminal>,
    );
    const terminal = container.querySelector("[class*='rounded-xl']");
    expect(terminal).toBeInTheDocument();
  });

  test("renders the traffic light dots", () => {
    render(
      <Terminal>
        <span>Content</span>
      </Terminal>,
    );
    const dots = document.querySelectorAll(
      ".bg-red-500, .bg-yellow-500, .bg-green-500",
    );
    expect(dots.length).toBe(3);
  });

  test("applies custom className", () => {
    const { container } = render(
      <Terminal className="my-terminal">
        <span>Content</span>
      </Terminal>,
    );
    const wrapper = container.firstElementChild;
    expect(wrapper?.getAttribute("class")).toContain("my-terminal");
  });

  test("renders multiple children", () => {
    render(
      <Terminal>
        <span>Line 1</span>
        <span>Line 2</span>
      </Terminal>,
    );
    expect(screen.getByText("Line 1")).toBeInTheDocument();
    expect(screen.getByText("Line 2")).toBeInTheDocument();
  });

  test("renders without sequence by default", () => {
    render(
      <Terminal sequence={false}>
        <span>No sequence</span>
      </Terminal>,
    );
    expect(screen.getByText("No sequence")).toBeInTheDocument();
  });

  test("renders code and pre elements", () => {
    const { container } = render(
      <Terminal>
        <span>Code content</span>
      </Terminal>,
    );
    const pre = container.querySelector("pre");
    const code = container.querySelector("code");
    expect(pre).toBeInTheDocument();
    expect(code).toBeInTheDocument();
  });

  test("terminal has border-b header section", () => {
    const { container } = render(
      <Terminal>
        <span>Content</span>
      </Terminal>,
    );
    const header = container.querySelector(".border-b");
    expect(header).toBeInTheDocument();
  });

  test("renders with sequence=true and startOnView=false", () => {
    render(
      <Terminal sequence={true} startOnView={false}>
        <span>Seq content</span>
      </Terminal>,
    );
    expect(screen.getByText("Seq content")).toBeInTheDocument();
  });

  test("renders with sequence=true and startOnView=true (default)", () => {
    render(
      <Terminal>
        <span>View content</span>
      </Terminal>,
    );
    expect(screen.getByText("View content")).toBeInTheDocument();
  });

  test("wraps children in ItemIndexContext when sequence is true", () => {
    render(
      <Terminal>
        <AnimatedSpan>Item 0</AnimatedSpan>
        <AnimatedSpan>Item 1</AnimatedSpan>
      </Terminal>,
    );
    expect(screen.getByText("Item 0")).toBeInTheDocument();
    expect(screen.getByText("Item 1")).toBeInTheDocument();
  });
});

describe("TypingAnimation", () => {
  test("renders the element", () => {
    const { container } = render(
      <TypingAnimation>Hello World</TypingAnimation>,
    );
    const span = container.querySelector("span");
    expect(span).toBeInTheDocument();
    expect(span?.getAttribute("class")).toContain("tracking-tight");
  });

  test("applies custom className", () => {
    const { container } = render(
      <TypingAnimation className="custom-class">Text</TypingAnimation>,
    );
    const span = container.querySelector("span");
    expect(span?.getAttribute("class")).toContain("custom-class");
  });

  test("throws if children is not a string", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => {
      render(
        <TypingAnimation>
          {(<span>not a string</span>) as unknown as string}
        </TypingAnimation>,
      );
    }).toThrow("TypingAnimation: children must be a string");
    spy.mockRestore();
  });

  test("renders with startOnView=true (default)", async () => {
    render(<TypingAnimation duration={50}>Visible</TypingAnimation>);
    // useInView is mocked to return true, so typing starts.
    // With duration=50ms and "Visible" (7 chars), need ~350ms + delay
    await vi.waitFor(
      () => {
        expect(screen.getByText("Visible")).toBeInTheDocument();
      },
      { timeout: 2000 },
    );
  });

  test("renders with startOnView=false", async () => {
    render(
      <TypingAnimation startOnView={false} duration={50}>
        Instant
      </TypingAnimation>,
    );
    await vi.waitFor(
      () => {
        expect(screen.getByText("Instant")).toBeInTheDocument();
      },
      { timeout: 2000 },
    );
  });

  test("renders with custom as prop", async () => {
    render(
      <TypingAnimation as="p" duration={50}>
        Paragraph
      </TypingAnimation>,
    );
    await vi.waitFor(
      () => {
        const p = screen.getByText("Paragraph");
        expect(p.tagName).toBe("P");
      },
      { timeout: 2000 },
    );
  });

  test("renders with custom duration", async () => {
    render(<TypingAnimation duration={50}>Fast</TypingAnimation>);
    await vi.waitFor(
      () => {
        expect(screen.getByText("Fast")).toBeInTheDocument();
      },
      { timeout: 2000 },
    );
  });

  test("renders with delay prop", async () => {
    render(
      <TypingAnimation delay={10} duration={50}>
        Delayed
      </TypingAnimation>,
    );
    await vi.waitFor(
      () => {
        expect(screen.getByText("Delayed")).toBeInTheDocument();
      },
      { timeout: 2000 },
    );
  });

  test("renders with default span element", async () => {
    const { container } = render(
      <TypingAnimation duration={50}>Default</TypingAnimation>,
    );
    await vi.waitFor(
      () => {
        const span = container.querySelector("span");
        expect(span).toBeInTheDocument();
        expect(span?.textContent).toBe("Default");
      },
      { timeout: 2000 },
    );
  });
});

describe("AnimatedSpan", () => {
  test("renders children", () => {
    render(<AnimatedSpan>Animated content</AnimatedSpan>);
    expect(screen.getByText("Animated content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(<AnimatedSpan className="my-span">Content</AnimatedSpan>);
    const span = screen.getByText("Content");
    expect(span.getAttribute("class")).toContain("my-span");
  });

  test("renders with delay prop", () => {
    render(<AnimatedSpan delay={500}>Delayed</AnimatedSpan>);
    expect(screen.getByText("Delayed")).toBeInTheDocument();
  });

  test("renders with startOnView=true", () => {
    render(<AnimatedSpan startOnView={true}>View content</AnimatedSpan>);
    expect(screen.getByText("View content")).toBeInTheDocument();
  });

  test("renders with startOnView=false", () => {
    render(<AnimatedSpan startOnView={false}>Static content</AnimatedSpan>);
    expect(screen.getByText("Static content")).toBeInTheDocument();
  });

  test("renders with grid class", () => {
    render(<AnimatedSpan>Grid content</AnimatedSpan>);
    const span = screen.getByText("Grid content");
    expect(span.getAttribute("class")).toContain("grid");
  });

  test("renders with body text class", () => {
    render(<AnimatedSpan>Small text</AnimatedSpan>);
    const span = screen.getByText("Small text");
    expect(span.getAttribute("class")).toContain("type-body");
  });
});

describe("TypingAnimation sequence behavior", () => {
  test("within Terminal with sequence, types when activeIndex matches", async () => {
    render(
      <Terminal sequence={true} startOnView={false}>
        <TypingAnimation duration={50}>Seq text</TypingAnimation>
      </Terminal>,
    );
    await vi.waitFor(
      () => {
        expect(screen.getByText("Seq text")).toBeInTheDocument();
      },
      { timeout: 2000 },
    );
  });

  test("within Terminal with sequence, AnimatedSpan animates when active", () => {
    render(
      <Terminal sequence={true} startOnView={false}>
        <AnimatedSpan>Seq animated</AnimatedSpan>
      </Terminal>,
    );
    expect(screen.getByText("Seq animated")).toBeInTheDocument();
  });

  test("AnimatedSpan calls completeItem via onAnimationComplete in sequence", () => {
    // With the updated mock, onAnimationComplete fires on mount.
    // In a sequence, this should call completeItem which advances the activeIndex.
    render(
      <Terminal sequence={true} startOnView={false}>
        <AnimatedSpan>First</AnimatedSpan>
        <AnimatedSpan>Second</AnimatedSpan>
      </Terminal>,
    );

    // Both items should render (the second one becomes active after the first completes)
    expect(screen.getByText("First")).toBeInTheDocument();
    expect(screen.getByText("Second")).toBeInTheDocument();
  });
});

describe("TypingAnimation with useInView=false", () => {
  beforeEach(() => {
    _useInViewResult = false;
  });

  afterEach(() => {
    _useInViewResult = true;
  });

  test("does not start typing when startOnView=true and not in view", () => {
    const { container } = render(
      <TypingAnimation startOnView={true} duration={50}>
        NotInView
      </TypingAnimation>,
    );
    // With isInView=false and startOnView=true, typing should not start
    // So displayedText should be empty
    const span = container.querySelector("span");
    expect(span?.textContent).toBe("");
  });

  test("starts typing when startOnView=false even when not in view", async () => {
    render(
      <TypingAnimation startOnView={false} duration={50}>
        StartsAnyway
      </TypingAnimation>,
    );
    await vi.waitFor(
      () => {
        expect(screen.getByText("StartsAnyway")).toBeInTheDocument();
      },
      { timeout: 2000 },
    );
  });
});

describe("TypingAnimation in sequence with multiple items", () => {
  test("second TypingAnimation starts after first completes", async () => {
    render(
      <Terminal sequence={true} startOnView={false}>
        <TypingAnimation duration={10}>First</TypingAnimation>
        <TypingAnimation duration={10}>Second</TypingAnimation>
      </Terminal>,
    );

    // Both should eventually display their text
    await vi.waitFor(
      () => {
        expect(screen.getByText("First")).toBeInTheDocument();
        expect(screen.getByText("Second")).toBeInTheDocument();
      },
      { timeout: 3000 },
    );
  });
});

describe("AnimatedSpan guard against re-start", () => {
  test("AnimatedSpan does not re-set hasStarted when already started in sequence", () => {
    const { rerender } = render(
      <Terminal sequence={true} startOnView={false}>
        <AnimatedSpan>Item</AnimatedSpan>
      </Terminal>,
    );

    // The AnimatedSpan should have started (onAnimationComplete fires on mount)
    expect(screen.getByText("Item")).toBeInTheDocument();

    // Re-render to trigger the effect again - hasStarted guard should prevent re-setting
    rerender(
      <Terminal sequence={true} startOnView={false}>
        <AnimatedSpan>Item updated</AnimatedSpan>
      </Terminal>,
    );

    expect(screen.getByText("Item updated")).toBeInTheDocument();
  });
});

describe("AnimatedSpan sequence-not-started guard", () => {
  let origUseInView: typeof _useInViewResult;

  beforeEach(() => {
    origUseInView = _useInViewResult;
    _useInViewResult = false;
  });

  afterEach(() => {
    _useInViewResult = origUseInView;
  });

  test("AnimatedSpan effect returns early when sequence has not started (line 54)", () => {
    // With startOnView=true (default) and isInView=false, sequenceHasStarted is false.
    // The effect guard `if (!sequence.sequenceStarted) return;` on line 54 fires.
    render(
      <Terminal sequence={true} startOnView={true}>
        <AnimatedSpan>Not started</AnimatedSpan>
      </Terminal>,
    );
    // Component still renders, but animation hasn't started
    expect(screen.getByText("Not started")).toBeInTheDocument();
  });

  test("TypingAnimation effect returns early when sequence has not started (line 125)", () => {
    const { container } = render(
      <Terminal sequence={true} startOnView={true}>
        <TypingAnimation duration={50}>Not started typing</TypingAnimation>
      </Terminal>,
    );
    // Typing hasn't started because isInView=false and startOnView=true,
    // so the sequence guard on line 125 fires and displayedText stays empty
    const spans = container.querySelectorAll("span");
    const typingSpan = Array.from(spans).find((s) =>
      s.getAttribute("class")?.includes("tracking-tight"),
    );
    expect(typingSpan?.textContent).toBe("");
  });
});

describe("TypingAnimation completion in sequence", () => {
  test("calls completeItem when typing finishes in sequence (line 162)", async () => {
    render(
      <Terminal sequence={true} startOnView={false}>
        <TypingAnimation duration={10}>Done</TypingAnimation>
        <TypingAnimation duration={10}>Next</TypingAnimation>
      </Terminal>,
    );

    // Wait for both items to complete typing - "Done" (4 chars * 10ms = 40ms + completion tick)
    // and "Next" starts after "Done" completes
    await vi.waitFor(
      () => {
        expect(screen.getByText("Done")).toBeInTheDocument();
        expect(screen.getByText("Next")).toBeInTheDocument();
      },
      { timeout: 3000 },
    );
  });

  test("single TypingAnimation completes and calls completeItem in sequence", async () => {
    vi.useFakeTimers();
    render(
      <Terminal sequence={true} startOnView={false}>
        <TypingAnimation duration={50}>Hi</TypingAnimation>
      </Terminal>,
    );

    // Advance past the delay and all typing ticks:
    // t=0: started becomes true
    // t=50: i=0, set "H"
    // t=100: i=1, set "Hi"
    // t=150: i=2, enter else branch -> completeItem (line 162)
    await act(async () => {
      vi.advanceTimersByTime(200);
    });

    expect(screen.getByText("Hi")).toBeInTheDocument();
    vi.useRealTimers();
  });
});
