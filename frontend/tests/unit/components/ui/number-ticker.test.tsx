import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

let motionValueCallback: ((latest: number) => void) | null = null;

vi.mock("motion/react", () => ({
  useInView: () => true,
  useMotionValue: (initial: number) => {
    let value = initial;
    return {
      get: () => value,
      set: (v: number) => {
        value = v;
      },
      on: vi.fn(),
    };
  },
  useSpring: (mv: { get: () => number }) => {
    const callbacks: Array<(v: number) => void> = [];
    return {
      on: vi.fn((event: string, cb: (v: number) => void) => {
        if (event === "change") {
          callbacks.push(cb);
          motionValueCallback = cb;
        }
        return () => {};
      }),
      get: () => mv.get(),
    };
  },
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let NumberTicker: typeof import("@/components/ui/number-ticker").NumberTicker;

beforeEach(async () => {
  vi.clearAllMocks();
  motionValueCallback = null;
  const mod = await import("@/components/ui/number-ticker");
  NumberTicker = mod.NumberTicker;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("NumberTicker", () => {
  test("renders with default startValue", () => {
    render(<NumberTicker value={100} />);
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  test("renders with custom startValue", () => {
    render(<NumberTicker value={100} startValue={10} />);
    expect(screen.getByText("10")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(<NumberTicker value={100} className="my-ticker" />);
    const span = screen.getByText("0");
    expect(span.getAttribute("class")).toContain("my-ticker");
  });

  test("renders as a span element", () => {
    const { container } = render(<NumberTicker value={50} />);
    const span = container.querySelector("span");
    expect(span).toBeInTheDocument();
  });

  test("passes additional props", () => {
    render(<NumberTicker value={50} data-testid="ticker" />);
    expect(screen.getByTestId("ticker")).toBeInTheDocument();
  });

  test("applies tabular-nums class", () => {
    render(<NumberTicker value={50} />);
    const span = screen.getByText("0");
    expect(span.getAttribute("class")).toContain("tabular-nums");
  });

  test("applies tracking-wider class", () => {
    render(<NumberTicker value={50} />);
    const span = screen.getByText("0");
    expect(span.getAttribute("class")).toContain("tracking-wider");
  });

  test("renders with decimalPlaces prop", () => {
    render(<NumberTicker value={3.14} decimalPlaces={2} />);
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  test("renders with direction down", () => {
    render(<NumberTicker value={0} startValue={100} direction="down" />);
    expect(screen.getByText("100")).toBeInTheDocument();
  });

  test("updates text content when spring value changes", () => {
    render(<NumberTicker value={42} decimalPlaces={0} />);
    const span = screen.getByText("0");
    // Simulate spring value change
    if (motionValueCallback) {
      motionValueCallback(42);
    }
    expect(span.textContent).toBe("42");
  });

  test("formats numbers with decimal places on change", () => {
    render(<NumberTicker value={3.14} decimalPlaces={2} />);
    const span = screen.getByText("0");
    if (motionValueCallback) {
      motionValueCallback(3.14);
    }
    expect(span.textContent).toBe("3.14");
  });

  test("formats numbers with thousands separator", () => {
    render(<NumberTicker value={1000} decimalPlaces={0} />);
    const span = screen.getByText("0");
    if (motionValueCallback) {
      motionValueCallback(1000);
    }
    expect(span.textContent).toBe("1,000");
  });

  test("handles zero value", () => {
    render(<NumberTicker value={0} />);
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  test("handles negative values", () => {
    render(<NumberTicker value={-10} startValue={0} />);
    expect(screen.getByText("0")).toBeInTheDocument();
  });
});
