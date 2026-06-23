import { renderHook, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { useIsMobile } from "@/hooks/use-mobile";

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

type Listener = (ev: MediaQueryListEvent) => void;

/**
 * Create a minimal mock of `window.matchMedia`.
 * Returns the mock MediaQueryList so tests can inspect listeners and fire
 * "change" events manually.
 */
function createMatchMediaMock() {
  const listeners = new Set<Listener>();

  const mql: MediaQueryList = {
    matches: false,
    media: "",
    onchange: null,
    addEventListener: vi.fn((type: string, listener: EventListener) => {
      if (type === "change") listeners.add(listener as Listener);
    }),
    removeEventListener: vi.fn((type: string, listener: EventListener) => {
      if (type === "change") listeners.delete(listener as Listener);
    }),
    dispatchEvent: vi.fn((event: Event) => {
      listeners.forEach((l) => l(event as MediaQueryListEvent));
      return true;
    }),
    addListener: vi.fn(),
    removeListener: vi.fn(),
  };

  return { mql, listeners };
}

/**
 * Fire a synthetic "change" event on the given mock MediaQueryList.
 */
function fireChangeEvent(mql: MediaQueryList) {
  const event = new Event("change") as MediaQueryListEvent;
  mql.dispatchEvent(event);
}

// ---------------------------------------------------------------------------
// tests
// ---------------------------------------------------------------------------

describe("useIsMobile", () => {
  let mql: MediaQueryList;
  let listeners: Set<Listener>;

  beforeEach(() => {
    ({ mql, listeners } = createMatchMediaMock());

    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue(mql));

    // Default: desktop width
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 1024,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  // -----------------------------------------------------------------------
  // initial state
  // -----------------------------------------------------------------------

  it("returns false on first render (state is initially undefined)", () => {
    const { result } = renderHook(() => useIsMobile());

    // Before the effect runs the hook returns `!!undefined` which is `false`.
    // After the effect runs with innerWidth=1024 it is still `false`.
    expect(result.current).toBe(false);
  });

  // -----------------------------------------------------------------------
  // matchMedia query
  // -----------------------------------------------------------------------

  it("calls window.matchMedia with the correct breakpoint query", () => {
    renderHook(() => useIsMobile());

    expect(window.matchMedia).toHaveBeenCalledWith("(max-width: 767px)");
  });

  // -----------------------------------------------------------------------
  // desktop width (>= 768)
  // -----------------------------------------------------------------------

  it("returns false when innerWidth is at the breakpoint (768)", () => {
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 768,
    });

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);
  });

  it("returns false when innerWidth is greater than the breakpoint", () => {
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 1920,
    });

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);
  });

  // -----------------------------------------------------------------------
  // mobile width (< 768)
  // -----------------------------------------------------------------------

  it("returns true when innerWidth is below the breakpoint", () => {
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 375,
    });

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(true);
  });

  it("returns true when innerWidth is just below the breakpoint (767)", () => {
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 767,
    });

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(true);
  });

  // -----------------------------------------------------------------------
  // reacting to viewport changes via matchMedia "change" event
  // -----------------------------------------------------------------------

  it("updates to true when viewport shrinks below the breakpoint", () => {
    // Start at desktop width
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 1024,
    });

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);

    // Simulate the browser resizing to mobile width
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 500,
    });

    act(() => {
      fireChangeEvent(mql);
    });

    expect(result.current).toBe(true);
  });

  it("updates to false when viewport grows above the breakpoint", () => {
    // Start at mobile width
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 500,
    });

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(true);

    // Simulate the browser resizing to desktop width
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 1200,
    });

    act(() => {
      fireChangeEvent(mql);
    });

    expect(result.current).toBe(false);
  });

  it("toggles correctly across multiple change events", () => {
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 1024,
    });

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);

    // Shrink to mobile
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 600,
    });
    act(() => fireChangeEvent(mql));
    expect(result.current).toBe(true);

    // Grow back to desktop
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 900,
    });
    act(() => fireChangeEvent(mql));
    expect(result.current).toBe(false);

    // Shrink again
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 320,
    });
    act(() => fireChangeEvent(mql));
    expect(result.current).toBe(true);
  });

  // -----------------------------------------------------------------------
  // event listener registration & cleanup
  // -----------------------------------------------------------------------

  it("registers a change event listener on mount", () => {
    renderHook(() => useIsMobile());

    expect(mql.addEventListener).toHaveBeenCalledWith(
      "change",
      expect.any(Function),
    );
    expect(listeners.size).toBe(1);
  });

  it("removes the change event listener on unmount", () => {
    const { unmount } = renderHook(() => useIsMobile());

    expect(listeners.size).toBe(1);

    unmount();

    expect(mql.removeEventListener).toHaveBeenCalledWith(
      "change",
      expect.any(Function),
    );
    expect(listeners.size).toBe(0);
  });

  it("does not leave stale listeners after unmount", () => {
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 500,
    });

    const { result, unmount } = renderHook(() => useIsMobile());
    expect(result.current).toBe(true);

    unmount();

    // Changing innerWidth and firing the event should have no effect
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 2000,
    });
    act(() => fireChangeEvent(mql));

    // The hook no longer tracks state; result stays at its last value.
    expect(result.current).toBe(true);
  });

  // -----------------------------------------------------------------------
  // boolean coercion
  // -----------------------------------------------------------------------

  it("always returns a boolean (double-negation of state)", () => {
    const { result } = renderHook(() => useIsMobile());
    expect(typeof result.current).toBe("boolean");
  });
});
