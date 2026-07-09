import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Toggle } from "@/components/ui/toggle";

describe("Toggle accessibility", () => {
  it("has button role", () => {
    render(<Toggle aria-label="Bold">B</Toggle>);
    expect(screen.getByRole("button", { name: /bold/i })).toBeInTheDocument();
  });

  it("unchecked state has aria-pressed=false", () => {
    render(<Toggle aria-label="Italic">I</Toggle>);
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "false");
  });

  it("pressed state has aria-pressed=true", () => {
    render(
      <Toggle aria-label="Italic" pressed>
        I
      </Toggle>,
    );
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "true");
  });

  it("toggles aria-pressed on click", async () => {
    const user = userEvent.setup();
    render(<Toggle aria-label="Underline">U</Toggle>);
    const button = screen.getByRole("button");
    expect(button).toHaveAttribute("aria-pressed", "false");
    await user.click(button);
    expect(button).toHaveAttribute("aria-pressed", "true");
    await user.click(button);
    expect(button).toHaveAttribute("aria-pressed", "false");
  });

  it("toggles with Space key", async () => {
    const user = userEvent.setup();
    render(<Toggle aria-label="Strikethrough">S</Toggle>);
    const button = screen.getByRole("button");
    button.focus();
    await user.keyboard(" ");
    expect(button).toHaveAttribute("aria-pressed", "true");
  });

  it("is not focusable when disabled", async () => {
    const user = userEvent.setup();
    render(
      <Toggle aria-label="Disabled" disabled>
        Off
      </Toggle>,
    );
    await user.tab();
    expect(screen.getByRole("button")).not.toHaveFocus();
  });

  it("does not toggle when disabled", async () => {
    const user = userEvent.setup();
    render(
      <Toggle aria-label="Disabled" disabled>
        Off
      </Toggle>,
    );
    await user.click(screen.getByRole("button"));
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "false");
  });
});
