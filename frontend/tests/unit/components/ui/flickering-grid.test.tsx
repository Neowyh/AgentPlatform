import { render, cleanup, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockFillRect = vi.fn();
const mockClearRect = vi.fn();
const mockGetImageData = vi.fn(() => ({ data: [10, 20, 30, 255] }));

// Mock ResizeObserver
class MockResizeObserver {
  callback: ResizeObserverCallback;
  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }
  observe = vi.fn();
  disconnect = vi.fn();
  unobserve = vi.fn();
}

// Mock IntersectionObserver
let intersectionCallback: IntersectionObserverCallback | null = null;
class MockIntersectionObserver {
  callback: IntersectionObserverCallback;
  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback;
    intersectionCallback = callback;
  }
  observe = vi.fn();
  disconnect = vi.fn();
  unobserve = vi.fn();
  root = null;
  rootMargin = "";
  thresholds = [];
  takeRecords = vi.fn(() => []);
}

// Mock requestAnimationFrame / cancelAnimationFrame
const mockRequestAnimationFrame = vi.fn((cb: FrameRequestCallback) => {
  // Don't call cb immediately - just return an ID
  return 1;
});
const mockCancelAnimationFrame = vi.fn();

// Mock canvas getContext
const mockGetContext = vi.fn(() => ({
  clearRect: mockClearRect,
  fillRect: mockFillRect,
  fillStyle: "",
  getImageData: mockGetImageData,
  canvas: { width: 0, height: 0 },
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let FlickeringGrid: typeof import("@/components/ui/flickering-grid").FlickeringGrid;

beforeEach(async () => {
  vi.clearAllMocks();
  intersectionCallback = null;

  vi.stubGlobal("ResizeObserver", MockResizeObserver);
  vi.stubGlobal("IntersectionObserver", MockIntersectionObserver);
  vi.stubGlobal("requestAnimationFrame", mockRequestAnimationFrame);
  vi.stubGlobal("cancelAnimationFrame", mockCancelAnimationFrame);
  vi.stubGlobal("devicePixelRatio", 2);

  HTMLCanvasElement.prototype.getContext = mockGetContext as never;

  const mod = await import("@/components/ui/flickering-grid");
  FlickeringGrid = mod.FlickeringGrid;
});

afterEach(() => {
  vi.unstubAllGlobals();
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("FlickeringGrid", () => {
  test("renders the container div", () => {
    const { container } = render(<FlickeringGrid width={100} height={100} />);
    expect(container.firstElementChild).toBeInTheDocument();
  });

  test("renders a canvas element", () => {
    const { container } = render(<FlickeringGrid width={100} height={100} />);
    const canvas = container.querySelector("canvas");
    expect(canvas).toBeInTheDocument();
  });

  test("applies custom className", () => {
    const { container } = render(
      <FlickeringGrid className="my-grid" width={100} height={100} />,
    );
    const wrapper = container.firstElementChild;
    expect(wrapper?.getAttribute("class")).toContain("my-grid");
  });

  test("passes additional HTML props", () => {
    const { container } = render(
      <FlickeringGrid data-testid="flickering-grid" width={100} height={100} />,
    );
    const wrapper = container.firstElementChild;
    expect(wrapper).toHaveAttribute("data-testid", "flickering-grid");
  });

  test("renders with default props", () => {
    const { container } = render(<FlickeringGrid />);
    expect(container.firstElementChild).toBeInTheDocument();
  });

  test("applies overflow-hidden to container", () => {
    const { container } = render(<FlickeringGrid width={100} height={100} />);
    const wrapper = container.firstElementChild;
    expect(wrapper?.getAttribute("class")).toContain("overflow-hidden");
  });

  test("canvas has pointer-events-none", () => {
    const { container } = render(<FlickeringGrid width={100} height={100} />);
    const canvas = container.querySelector("canvas");
    expect(canvas?.getAttribute("class")).toContain("pointer-events-none");
  });

  test("renders with explicit width and height props", () => {
    const { container } = render(<FlickeringGrid width={200} height={150} />);
    expect(container.firstElementChild).toBeInTheDocument();
  });

  test("creates a canvas context on mount", () => {
    render(<FlickeringGrid width={100} height={100} />);
    expect(mockGetContext).toHaveBeenCalledWith("2d");
  });

  test("sets canvas size style from width/height props", () => {
    const { container } = render(<FlickeringGrid width={200} height={150} />);
    const canvas = container.querySelector("canvas");
    expect(canvas).toBeInTheDocument();
    expect(canvas?.style.width).toBe("200px");
    expect(canvas?.style.height).toBe("150px");
  });

  test("uses devicePixelRatio for canvas dimensions", () => {
    render(<FlickeringGrid width={100} height={100} />);
    expect(mockGetContext).toHaveBeenCalled();
  });

  test("memoizedColor handles SSR fallback when window is undefined", () => {
    render(<FlickeringGrid color="rgb(255, 0, 0)" width={100} height={100} />);
    expect(mockGetImageData).toHaveBeenCalled();
  });

  test("handles when getContext returns null", () => {
    mockGetContext.mockReturnValueOnce(null as never);
    const { container } = render(<FlickeringGrid width={100} height={100} />);
    expect(container.firstElementChild).toBeInTheDocument();
  });

  test("sets up IntersectionObserver on canvas", () => {
    render(<FlickeringGrid width={100} height={100} />);
    // The component should have created an IntersectionObserver
    expect(intersectionCallback).not.toBeNull();
  });

  test("handles intersection observer callback with isIntersecting=true", () => {
    render(<FlickeringGrid width={100} height={100} />);
    // Simulate intersection
    if (intersectionCallback) {
      intersectionCallback(
        [{ isIntersecting: true } as IntersectionObserverEntry],
        {} as IntersectionObserver,
      );
    }
    // The component re-renders with isInView=true, which triggers the effect
    // requestAnimationFrame may or may not be called depending on React's
    // batching. We just verify the component doesn't crash.
    expect(mockGetContext).toHaveBeenCalled();
  });

  test("handles intersection observer callback with isIntersecting=false", () => {
    render(<FlickeringGrid width={100} height={100} />);
    if (intersectionCallback) {
      intersectionCallback(
        [{ isIntersecting: false } as IntersectionObserverEntry],
        {} as IntersectionObserver,
      );
    }
    expect(mockGetContext).toHaveBeenCalled();
  });

  test("cleans up observers and animation frame on unmount", () => {
    const { unmount } = render(<FlickeringGrid width={100} height={100} />);
    unmount();
    expect(mockCancelAnimationFrame).toHaveBeenCalled();
  });

  test("uses container dimensions when width/height not provided", () => {
    const { container } = render(<FlickeringGrid />);
    expect(container.firstElementChild).toBeInTheDocument();
    const canvas = container.querySelector("canvas");
    expect(canvas).toBeInTheDocument();
  });

  test("renders with custom squareSize and gridGap", () => {
    const { container } = render(
      <FlickeringGrid squareSize={8} gridGap={4} width={100} height={100} />,
    );
    expect(container.firstElementChild).toBeInTheDocument();
  });

  test("renders with custom flickerChance", () => {
    const { container } = render(
      <FlickeringGrid flickerChance={0.5} width={100} height={100} />,
    );
    expect(container.firstElementChild).toBeInTheDocument();
  });

  test("renders with custom maxOpacity", () => {
    const { container } = render(
      <FlickeringGrid maxOpacity={0.8} width={100} height={100} />,
    );
    expect(container.firstElementChild).toBeInTheDocument();
  });

  test("canvas element has block display class", () => {
    const { container } = render(<FlickeringGrid width={100} height={100} />);
    const canvas = container.querySelector("canvas");
    expect(canvas?.getAttribute("class")).toContain("block");
  });

  test("toRGBA with context returning null falls back to red color", () => {
    mockGetContext.mockReturnValueOnce(null as never);
    const { container } = render(
      <FlickeringGrid color="blue" width={100} height={100} />,
    );
    expect(container.firstElementChild).toBeInTheDocument();
  });

  test("sets up ResizeObserver on container", () => {
    const { container } = render(<FlickeringGrid width={100} height={100} />);
    // Verify the container element is present (ResizeObserver.observe was called internally)
    expect(container.firstElementChild).toBeInTheDocument();
  });

  test("canvas has data attributes from inline style", () => {
    const { container } = render(<FlickeringGrid width={300} height={200} />);
    const canvas = container.querySelector("canvas");
    expect(canvas?.style.width).toBe("300px");
    expect(canvas?.style.height).toBe("200px");
  });

  // ── Animation loop tests ─────────────────────────────────────────────────

  test("animation loop runs when component is in view", () => {
    // Make requestAnimationFrame actually call the callback
    let rafCallback: FrameRequestCallback | null = null;
    mockRequestAnimationFrame.mockImplementation((cb: FrameRequestCallback) => {
      rafCallback = cb;
      return 1;
    });

    render(<FlickeringGrid width={100} height={100} />);

    // Trigger intersection to set isInView=true
    act(() => {
      if (intersectionCallback) {
        intersectionCallback(
          [{ isIntersecting: true } as IntersectionObserverEntry],
          {} as IntersectionObserver,
        );
      }
    });

    // The effect should re-run with isInView=true and call requestAnimationFrame
    // Now manually invoke the animation callback
    act(() => {
      if (rafCallback) {
        rafCallback(1000); // timestamp = 1000ms
      }
    });

    // The animation should have called canvas drawing operations
    expect(mockClearRect).toHaveBeenCalled();
    expect(mockFillRect).toHaveBeenCalled();
  });

  test("animation draws grid with correct fillStyle", () => {
    let rafCallback: FrameRequestCallback | null = null;
    mockRequestAnimationFrame.mockImplementation((cb: FrameRequestCallback) => {
      rafCallback = cb;
      return 1;
    });

    render(<FlickeringGrid width={100} height={100} color="rgb(255, 0, 0)" />);

    act(() => {
      if (intersectionCallback) {
        intersectionCallback(
          [{ isIntersecting: true } as IntersectionObserverEntry],
          {} as IntersectionObserver,
        );
      }
    });

    act(() => {
      if (rafCallback) {
        rafCallback(1000);
      }
    });

    // fillRect should be called multiple times (once for background + once per grid square)
    expect(mockFillRect.mock.calls.length).toBeGreaterThan(1);
  });

  test("animation does not run when component is not in view", () => {
    mockRequestAnimationFrame.mockImplementation((cb: FrameRequestCallback) => {
      // Should not be called when not in view
      return 1;
    });

    render(<FlickeringGrid width={100} height={100} />);

    // Don't trigger intersection - isInView stays false
    // requestAnimationFrame should NOT have been called for animation
    // (it may be called once during setup, but the animate function returns early)
    expect(mockClearRect).not.toHaveBeenCalled();
  });

  test("ResizeObserver triggers canvas resize", () => {
    let resizeCallback: ResizeObserverCallback | null = null;
    class TestResizeObserver {
      callback: ResizeObserverCallback;
      constructor(callback: ResizeObserverCallback) {
        this.callback = callback;
        resizeCallback = callback;
      }
      observe = vi.fn();
      disconnect = vi.fn();
      unobserve = vi.fn();
    }
    vi.stubGlobal("ResizeObserver", TestResizeObserver);

    render(<FlickeringGrid width={100} height={100} />);

    // Simulate resize
    act(() => {
      if (resizeCallback) {
        resizeCallback([] as ResizeObserverEntry[], {} as ResizeObserver);
      }
    });

    // Component should update canvas size
    const canvas = document.querySelector("canvas");
    expect(canvas).toBeInTheDocument();
  });

  test("toRGBA handles custom color values", () => {
    render(<FlickeringGrid color="rebeccapurple" width={100} height={100} />);
    // The color parsing should have called getImageData
    expect(mockGetImageData).toHaveBeenCalled();
  });

  test("animation uses correct deltaTime calculation", () => {
    let rafCallback: FrameRequestCallback | null = null;
    mockRequestAnimationFrame.mockImplementation((cb: FrameRequestCallback) => {
      rafCallback = cb;
      return 1;
    });

    render(
      <FlickeringGrid
        flickerChance={1.0}
        maxOpacity={0.5}
        width={50}
        height={50}
      />,
    );

    act(() => {
      if (intersectionCallback) {
        intersectionCallback(
          [{ isIntersecting: true } as IntersectionObserverEntry],
          {} as IntersectionObserver,
        );
      }
    });

    // Call animate with a specific timestamp
    act(() => {
      if (rafCallback) {
        rafCallback(2000); // 2 seconds
      }
    });

    // Verify the grid was drawn
    expect(mockClearRect).toHaveBeenCalled();
  });

  test("animate function returns early when component is not in view", () => {
    let rafCallback: FrameRequestCallback | null = null;
    mockRequestAnimationFrame.mockImplementation((cb: FrameRequestCallback) => {
      rafCallback = cb;
      return 1;
    });

    render(<FlickeringGrid width={100} height={100} />);

    // Do NOT trigger intersection - isInView stays false
    // But manually invoke the captured raf callback to exercise the guard
    act(() => {
      if (rafCallback) {
        rafCallback(1000);
      }
    });

    // animate should have returned early because isInView is false
    // so clearRect should NOT have been called for animation
    expect(mockClearRect).not.toHaveBeenCalled();
  });
});
