import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { Input } from "@/components/ui/input";

afterEach(() => {
  cleanup();
});

describe("Input", () => {
  test("renders as an input element", () => {
    render(<Input data-testid="input-el" />);
    expect(screen.getByTestId("input-el").tagName).toBe("INPUT");
  });

  test("applies data-slot attribute", () => {
    render(<Input data-testid="input-slot" />);
    expect(screen.getByTestId("input-slot")).toHaveAttribute(
      "data-slot",
      "input",
    );
  });

  test("has type attribute as text by default in browser", () => {
    render(<Input data-testid="input-type" />);
    // HTML input defaults to type="text" even without explicit attribute
    const input = screen.getByTestId("input-type");
    expect(input.getAttribute("type")).toBeNull();
    // The browser default is still text
    expect(input).not.toHaveAttribute("type", "password");
  });

  test("applies custom type", () => {
    render(<Input type="password" data-testid="input-pw" />);
    expect(screen.getByTestId("input-pw")).toHaveAttribute("type", "password");
  });

  test("applies placeholder", () => {
    render(<Input placeholder="Enter email" data-testid="input-ph" />);
    expect(screen.getByTestId("input-ph")).toHaveAttribute(
      "placeholder",
      "Enter email",
    );
  });

  test("handles value changes", () => {
    render(<Input data-testid="input-val" />);
    const input = screen.getByTestId("input-val");
    fireEvent.change(input, { target: { value: "hello" } });
    expect(input).toHaveValue("hello");
  });

  test("can be disabled", () => {
    render(<Input disabled data-testid="input-disabled" />);
    expect(screen.getByTestId("input-disabled")).toBeDisabled();
  });

  test("applies custom className", () => {
    render(<Input className="custom-input" data-testid="input-custom" />);
    expect(screen.getByTestId("input-custom")).toHaveClass("custom-input");
  });

  test("forwards name attribute", () => {
    render(<Input name="email" data-testid="input-name" />);
    expect(screen.getByTestId("input-name")).toHaveAttribute("name", "email");
  });

  test("forwards id attribute", () => {
    render(<Input id="email-input" data-testid="input-id" />);
    expect(screen.getByTestId("input-id")).toHaveAttribute("id", "email-input");
  });

  test("handles focus and blur events", () => {
    const handleFocus = vi.fn();
    const handleBlur = vi.fn();
    render(
      <Input
        data-testid="input-events"
        onFocus={handleFocus}
        onBlur={handleBlur}
      />,
    );
    const input = screen.getByTestId("input-events");
    fireEvent.focus(input);
    expect(handleFocus).toHaveBeenCalledTimes(1);
    fireEvent.blur(input);
    expect(handleBlur).toHaveBeenCalledTimes(1);
  });
});
