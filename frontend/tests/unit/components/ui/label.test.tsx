import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { Label } from "@/components/ui/label";

afterEach(() => {
  cleanup();
});

describe("Label", () => {
  test("renders with text content", () => {
    render(<Label>Email</Label>);
    expect(screen.getByText("Email")).toBeInTheDocument();
  });

  test("renders as a label element", () => {
    render(<Label data-testid="label-element">Name</Label>);
    expect(screen.getByTestId("label-element").tagName).toBe("LABEL");
  });

  test("applies data-slot attribute", () => {
    render(<Label data-testid="label-slot">Slot Test</Label>);
    expect(screen.getByTestId("label-slot")).toHaveAttribute(
      "data-slot",
      "label",
    );
  });

  test("forwards htmlFor prop", () => {
    render(
      <Label htmlFor="email-input" data-testid="label-for">
        Email Input
      </Label>,
    );
    expect(screen.getByTestId("label-for")).toHaveAttribute(
      "for",
      "email-input",
    );
  });

  test("applies custom className", () => {
    render(
      <Label className="custom-class" data-testid="label-custom">
        Custom Label
      </Label>,
    );
    expect(screen.getByTestId("label-custom")).toHaveClass("custom-class");
  });

  test("applies default styling classes", () => {
    render(<Label data-testid="label-styles">Styled Label</Label>);
    const label = screen.getByTestId("label-styles");
    expect(label.className).toContain("text-sm");
    expect(label.className).toContain("font-medium");
  });
});
