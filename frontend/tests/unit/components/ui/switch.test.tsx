import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { Switch } from "@/components/ui/switch";

afterEach(() => {
  cleanup();
});

describe("Switch", () => {
  test("renders a switch element", () => {
    render(<Switch data-testid="switch" />);
    expect(screen.getByTestId("switch")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<Switch data-testid="switch-slot" />);
    expect(screen.getByTestId("switch-slot")).toHaveAttribute(
      "data-slot",
      "switch",
    );
  });

  test("defaults to unchecked state", () => {
    render(<Switch data-testid="switch-unchecked" />);
    expect(screen.getByTestId("switch-unchecked")).toHaveAttribute(
      "data-state",
      "unchecked",
    );
  });

  test("can be checked by default", () => {
    render(<Switch checked data-testid="switch-checked" />);
    expect(screen.getByTestId("switch-checked")).toHaveAttribute(
      "data-state",
      "checked",
    );
  });

  test("toggles on click", () => {
    render(<Switch data-testid="switch-toggle" />);
    const sw = screen.getByTestId("switch-toggle");
    expect(sw).toHaveAttribute("data-state", "unchecked");
    fireEvent.click(sw);
    expect(sw).toHaveAttribute("data-state", "checked");
    fireEvent.click(sw);
    expect(sw).toHaveAttribute("data-state", "unchecked");
  });

  test("can be disabled", () => {
    render(<Switch disabled data-testid="switch-disabled" />);
    expect(screen.getByTestId("switch-disabled")).toBeDisabled();
  });

  test("calls onCheckedChange when toggled", () => {
    const handleCheckedChange = vi.fn();
    render(
      <Switch
        onCheckedChange={handleCheckedChange}
        data-testid="switch-callback"
      />,
    );
    fireEvent.click(screen.getByTestId("switch-callback"));
    expect(handleCheckedChange).toHaveBeenCalledWith(true);
  });

  test("applies custom className", () => {
    render(<Switch className="custom-switch" data-testid="switch-custom" />);
    expect(screen.getByTestId("switch-custom")).toHaveClass("custom-switch");
  });

  test("renders thumb element", () => {
    render(<Switch data-testid="switch-parent" />);
    const thumb = screen
      .getByTestId("switch-parent")
      .querySelector("[data-slot='switch-thumb']");
    expect(thumb).toBeInTheDocument();
  });
});
