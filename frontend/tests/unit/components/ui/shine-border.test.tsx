import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { ShineBorder } from "@/components/ui/shine-border";

afterEach(() => {
  cleanup();
});

describe("ShineBorder", () => {
  test("renders a div element", () => {
    render(<ShineBorder data-testid="sb" />);
    expect(screen.getByTestId("sb").tagName).toBe("DIV");
  });

  test("applies custom className", () => {
    render(<ShineBorder className="custom-shine" data-testid="sb-custom" />);
    expect(screen.getByTestId("sb-custom")).toHaveClass("custom-shine");
  });

  test("applies absolute positioning class", () => {
    render(<ShineBorder data-testid="sb-pos" />);
    expect(screen.getByTestId("sb-pos").className).toContain("absolute");
  });

  test("applies inset-0 class", () => {
    render(<ShineBorder data-testid="sb-inset" />);
    expect(screen.getByTestId("sb-inset").className).toContain("inset-0");
  });

  test("applies animate-shine class", () => {
    render(<ShineBorder data-testid="sb-anim" />);
    expect(screen.getByTestId("sb-anim").className).toContain("animate-shine");
  });

  test("accepts custom style props", () => {
    render(<ShineBorder style={{ zIndex: 10 }} data-testid="sb-style" />);
    expect(screen.getByTestId("sb-style")).toHaveStyle({ zIndex: 10 });
  });
});
