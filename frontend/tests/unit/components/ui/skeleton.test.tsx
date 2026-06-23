import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { Skeleton } from "@/components/ui/skeleton";

afterEach(() => {
  cleanup();
});

describe("Skeleton", () => {
  test("renders as a div element", () => {
    render(<Skeleton data-testid="skel-el" />);
    expect(screen.getByTestId("skel-el").tagName).toBe("DIV");
  });

  test("applies data-slot attribute", () => {
    render(<Skeleton data-testid="skel-slot" />);
    expect(screen.getByTestId("skel-slot")).toHaveAttribute(
      "data-slot",
      "skeleton",
    );
  });

  test("applies animate-pulse class", () => {
    render(<Skeleton data-testid="skel-pulse" />);
    expect(screen.getByTestId("skel-pulse").className).toContain(
      "animate-pulse",
    );
  });

  test("applies rounded-md class", () => {
    render(<Skeleton data-testid="skel-rounded" />);
    expect(screen.getByTestId("skel-rounded").className).toContain(
      "rounded-md",
    );
  });

  test("applies custom className", () => {
    render(<Skeleton className="custom-skel" data-testid="skel-custom" />);
    expect(screen.getByTestId("skel-custom")).toHaveClass("custom-skel");
  });

  test("forwards style props", () => {
    render(
      <Skeleton style={{ width: 100, height: 20 }} data-testid="skel-style" />,
    );
    const el = screen.getByTestId("skel-style");
    expect(el).toHaveStyle({ width: "100px", height: "20px" });
  });
});
