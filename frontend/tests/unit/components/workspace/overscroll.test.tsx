import { render, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { Overscroll } from "@/components/workspace/overscroll";

describe("Overscroll", () => {
  beforeEach(() => {
    // Reset styles before each test
    document.documentElement.style.overflow = "";
    document.documentElement.style.overscrollBehavior = "";
  });

  afterEach(() => {
    cleanup();
    document.documentElement.style.overflow = "";
    document.documentElement.style.overscrollBehavior = "";
  });

  test("renders nothing (returns null)", () => {
    const { container } = render(<Overscroll behavior="none" />);
    expect(container.firstChild).toBeNull();
  });

  test("sets overflow to 'hidden' by default", () => {
    render(<Overscroll behavior="contain" />);
    expect(document.documentElement.style.overflow).toBe("hidden");
  });

  test("sets custom overflow when provided", () => {
    render(<Overscroll behavior="contain" overflow="auto" />);
    expect(document.documentElement.style.overflow).toBe("auto");
  });

  test("sets scroll overflow", () => {
    render(<Overscroll behavior="contain" overflow="scroll" />);
    expect(document.documentElement.style.overflow).toBe("scroll");
  });

  test("sets overscrollBehavior to 'none'", () => {
    render(<Overscroll behavior="none" />);
    expect(document.documentElement.style.overscrollBehavior).toBe("none");
  });

  test("sets overscrollBehavior to 'contain'", () => {
    render(<Overscroll behavior="contain" />);
    expect(document.documentElement.style.overscrollBehavior).toBe("contain");
  });

  test("sets overscrollBehavior to 'auto'", () => {
    render(<Overscroll behavior="auto" />);
    expect(document.documentElement.style.overscrollBehavior).toBe("auto");
  });

  test("updates styles when behavior changes", () => {
    const { rerender } = render(<Overscroll behavior="none" />);
    expect(document.documentElement.style.overscrollBehavior).toBe("none");

    rerender(<Overscroll behavior="contain" />);
    expect(document.documentElement.style.overscrollBehavior).toBe("contain");
  });

  test("updates overflow when overflow prop changes", () => {
    const { rerender } = render(
      <Overscroll behavior="none" overflow="hidden" />,
    );
    expect(document.documentElement.style.overflow).toBe("hidden");

    rerender(<Overscroll behavior="none" overflow="auto" />);
    expect(document.documentElement.style.overflow).toBe("auto");
  });
});
