import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { Textarea } from "@/components/ui/textarea";

afterEach(() => {
  cleanup();
});

describe("Textarea", () => {
  test("renders as a textarea element", () => {
    render(<Textarea data-testid="textarea-el" />);
    expect(screen.getByTestId("textarea-el").tagName).toBe("TEXTAREA");
  });

  test("applies data-slot attribute", () => {
    render(<Textarea data-testid="textarea-slot" />);
    expect(screen.getByTestId("textarea-slot")).toHaveAttribute(
      "data-slot",
      "textarea",
    );
  });

  test("applies placeholder", () => {
    render(<Textarea placeholder="Enter text" data-testid="textarea-ph" />);
    expect(screen.getByTestId("textarea-ph")).toHaveAttribute(
      "placeholder",
      "Enter text",
    );
  });

  test("handles value changes", () => {
    render(<Textarea data-testid="textarea-val" />);
    const textarea = screen.getByTestId("textarea-val");
    fireEvent.change(textarea, { target: { value: "some text" } });
    expect(textarea).toHaveValue("some text");
  });

  test("can be disabled", () => {
    render(<Textarea disabled data-testid="textarea-disabled" />);
    expect(screen.getByTestId("textarea-disabled")).toBeDisabled();
  });

  test("applies custom className", () => {
    render(<Textarea className="custom-ta" data-testid="textarea-custom" />);
    expect(screen.getByTestId("textarea-custom")).toHaveClass("custom-ta");
  });

  test("forwards name attribute", () => {
    render(<Textarea name="message" data-testid="textarea-name" />);
    expect(screen.getByTestId("textarea-name")).toHaveAttribute(
      "name",
      "message",
    );
  });

  test("forwards id attribute", () => {
    render(<Textarea id="msg-input" data-testid="textarea-id" />);
    expect(screen.getByTestId("textarea-id")).toHaveAttribute(
      "id",
      "msg-input",
    );
  });

  test("handles focus and blur events", () => {
    const handleFocus = vi.fn();
    const handleBlur = vi.fn();
    render(
      <Textarea
        data-testid="textarea-events"
        onFocus={handleFocus}
        onBlur={handleBlur}
      />,
    );
    const ta = screen.getByTestId("textarea-events");
    fireEvent.focus(ta);
    expect(handleFocus).toHaveBeenCalledTimes(1);
    fireEvent.blur(ta);
    expect(handleBlur).toHaveBeenCalledTimes(1);
  });
});
