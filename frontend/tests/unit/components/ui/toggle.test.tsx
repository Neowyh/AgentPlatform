import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { Toggle } from "@/components/ui/toggle";

afterEach(() => {
  cleanup();
});

describe("Toggle", () => {
  test("renders with text content", () => {
    render(<Toggle data-testid="toggle">Toggle me</Toggle>);
    expect(screen.getByText("Toggle me")).toBeInTheDocument();
  });

  test("renders as a button element", () => {
    render(<Toggle data-testid="toggle-el">T</Toggle>);
    expect(screen.getByTestId("toggle-el").tagName).toBe("BUTTON");
  });

  test("applies data-slot attribute", () => {
    render(<Toggle data-testid="toggle-slot">T</Toggle>);
    expect(screen.getByTestId("toggle-slot")).toHaveAttribute(
      "data-slot",
      "toggle",
    );
  });

  test("handles toggle press", () => {
    render(<Toggle data-testid="toggle-press">T</Toggle>);
    const toggle = screen.getByTestId("toggle-press");
    expect(toggle).toHaveAttribute("data-state", "off");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("data-state", "on");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("data-state", "off");
  });

  test("can be disabled", () => {
    render(
      <Toggle disabled data-testid="toggle-disabled">
        Disabled
      </Toggle>,
    );
    expect(screen.getByTestId("toggle-disabled")).toBeDisabled();
  });

  test("applies custom className", () => {
    render(
      <Toggle className="custom-toggle" data-testid="toggle-custom">
        T
      </Toggle>,
    );
    expect(screen.getByTestId("toggle-custom")).toHaveClass("custom-toggle");
  });

  test("applies default variant", () => {
    render(<Toggle data-testid="toggle-default">T</Toggle>);
    expect(screen.getByTestId("toggle-default").className).toContain(
      "bg-transparent",
    );
  });

  test("applies outline variant", () => {
    render(
      <Toggle variant="outline" data-testid="toggle-outline">
        T
      </Toggle>,
    );
    expect(screen.getByTestId("toggle-outline").className).toContain("border");
  });

  test("applies default size", () => {
    render(<Toggle data-testid="toggle-size-default">T</Toggle>);
    expect(screen.getByTestId("toggle-size-default").className).toContain(
      "h-9",
    );
  });

  test("applies sm size", () => {
    render(
      <Toggle size="sm" data-testid="toggle-size-sm">
        T
      </Toggle>,
    );
    expect(screen.getByTestId("toggle-size-sm").className).toContain("h-8");
  });

  test("applies lg size", () => {
    render(
      <Toggle size="lg" data-testid="toggle-size-lg">
        T
      </Toggle>,
    );
    expect(screen.getByTestId("toggle-size-lg").className).toContain("h-10");
  });

  test("calls onPressedChange when toggled", () => {
    const handlePressedChange = vi.fn();
    render(
      <Toggle
        onPressedChange={handlePressedChange}
        data-testid="toggle-callback"
      >
        T
      </Toggle>,
    );
    fireEvent.click(screen.getByTestId("toggle-callback"));
    expect(handlePressedChange).toHaveBeenCalledWith(true);
  });
});
