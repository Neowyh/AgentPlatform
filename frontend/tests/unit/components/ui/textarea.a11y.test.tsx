import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Textarea } from "@/components/ui/textarea";

describe("Textarea accessibility", () => {
  it("renders as textbox role", () => {
    render(<Textarea aria-label="Message" />);
    expect(
      screen.getByRole("textbox", { name: /message/i }),
    ).toBeInTheDocument();
  });

  it("has accessible name from aria-label", () => {
    render(<Textarea aria-label="Description" />);
    expect(screen.getByRole("textbox")).toHaveAccessibleName("Description");
  });

  it("can be focused via tab", async () => {
    const user = userEvent.setup();
    render(<Textarea aria-label="Notes" />);
    await user.tab();
    expect(screen.getByRole("textbox")).toHaveFocus();
  });

  it("accepts multiline text input", async () => {
    const user = userEvent.setup();
    render(<Textarea aria-label="Comment" />);
    const textarea = screen.getByRole("textbox");
    await user.type(textarea, "Line 1{Enter}Line 2");
    expect(textarea).toHaveValue("Line 1\nLine 2");
  });

  it("is not focusable when disabled", async () => {
    const user = userEvent.setup();
    render(<Textarea aria-label="Disabled" disabled />);
    await user.tab();
    expect(screen.getByRole("textbox")).not.toHaveFocus();
  });

  it("has aria-invalid when set", () => {
    render(<Textarea aria-label="Field" aria-invalid="true" />);
    expect(screen.getByRole("textbox")).toHaveAttribute("aria-invalid", "true");
  });

  it("supports placeholder as text alternative", () => {
    render(<Textarea placeholder="Type here..." />);
    expect(screen.getByPlaceholderText("Type here...")).toBeInTheDocument();
  });
});
