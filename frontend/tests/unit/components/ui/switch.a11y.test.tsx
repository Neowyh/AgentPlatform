import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Switch } from "@/components/ui/switch";

describe("Switch accessibility", () => {
  it("renders as switch role", () => {
    render(<Switch aria-label="Dark mode" />);
    expect(screen.getByRole("switch")).toBeInTheDocument();
  });

  it("has accessible name from aria-label", () => {
    render(<Switch aria-label="Enable notifications" />);
    expect(screen.getByRole("switch")).toHaveAccessibleName(
      "Enable notifications",
    );
  });

  it("unchecked state has aria-checked=false", () => {
    render(<Switch aria-label="Toggle" />);
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "false");
  });

  it("checked state has aria-checked=true", () => {
    render(<Switch aria-label="Toggle" defaultChecked />);
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
  });

  it("toggles on click", async () => {
    const user = userEvent.setup();
    render(<Switch aria-label="Toggle" />);
    const toggle = screen.getByRole("switch");
    expect(toggle).toHaveAttribute("aria-checked", "false");
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "true");
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "false");
  });

  it("toggles with Space key", async () => {
    const user = userEvent.setup();
    render(<Switch aria-label="Toggle" />);
    const toggle = screen.getByRole("switch");
    toggle.focus();
    await user.keyboard(" ");
    expect(toggle).toHaveAttribute("aria-checked", "true");
  });

  it("is not focusable when disabled", async () => {
    const user = userEvent.setup();
    render(<Switch aria-label="Toggle" disabled />);
    await user.tab();
    expect(screen.getByRole("switch")).not.toHaveFocus();
  });

  it("does not toggle when disabled", async () => {
    const user = userEvent.setup();
    render(<Switch aria-label="Toggle" disabled />);
    await user.click(screen.getByRole("switch"));
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "false");
  });
});
