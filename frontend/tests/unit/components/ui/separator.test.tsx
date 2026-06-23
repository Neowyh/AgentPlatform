import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { Separator } from "@/components/ui/separator";

afterEach(() => {
  cleanup();
});

describe("Separator", () => {
  test("renders a separator element", () => {
    render(<Separator data-testid="sep" />);
    expect(screen.getByTestId("sep")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<Separator data-testid="sep-slot" />);
    expect(screen.getByTestId("sep-slot")).toHaveAttribute(
      "data-slot",
      "separator",
    );
  });

  test("defaults to horizontal orientation", () => {
    render(<Separator data-testid="sep-h" />);
    expect(screen.getByTestId("sep-h")).toHaveAttribute(
      "data-orientation",
      "horizontal",
    );
  });

  test("applies vertical orientation", () => {
    render(<Separator orientation="vertical" data-testid="sep-v" />);
    expect(screen.getByTestId("sep-v")).toHaveAttribute(
      "data-orientation",
      "vertical",
    );
  });

  test("is decorative by default", () => {
    render(<Separator data-testid="sep-dec" />);
    // decorative separator has no semantic role (aria-hidden is not used)
    const sep = screen.getByTestId("sep-dec");
    expect(sep).not.toHaveAttribute("role", "separator");
  });

  test("applies custom className", () => {
    render(<Separator className="custom-sep" data-testid="sep-custom" />);
    expect(screen.getByTestId("sep-custom")).toHaveClass("custom-sep");
  });
});
