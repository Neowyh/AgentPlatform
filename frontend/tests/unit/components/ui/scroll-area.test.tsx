import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";

afterEach(() => {
  cleanup();
});

describe("ScrollArea", () => {
  test("renders with children", () => {
    render(
      <ScrollArea data-testid="sa">
        <div>Scrollable content</div>
      </ScrollArea>,
    );
    expect(screen.getByTestId("sa")).toBeInTheDocument();
    expect(screen.getByText("Scrollable content")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <ScrollArea data-testid="sa-slot">
        <div>Content</div>
      </ScrollArea>,
    );
    expect(screen.getByTestId("sa-slot")).toHaveAttribute(
      "data-slot",
      "scroll-area",
    );
  });

  test("applies relative class", () => {
    render(
      <ScrollArea data-testid="sa-rel">
        <div>Content</div>
      </ScrollArea>,
    );
    expect(screen.getByTestId("sa-rel").className).toContain("relative");
  });

  test("applies custom className", () => {
    render(
      <ScrollArea className="custom-sa" data-testid="sa-custom">
        <div>Content</div>
      </ScrollArea>,
    );
    expect(screen.getByTestId("sa-custom")).toHaveClass("custom-sa");
  });

  test("renders a viewport", () => {
    const { container } = render(
      <ScrollArea>
        <div>Content</div>
      </ScrollArea>,
    );
    expect(
      container.querySelector("[data-slot='scroll-area-viewport']"),
    ).toBeInTheDocument();
  });
});
