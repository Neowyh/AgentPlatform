import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

function TooltipDemo() {
  return (
    <Tooltip>
      <TooltipTrigger>Hover me</TooltipTrigger>
      <TooltipContent>Helpful tooltip text</TooltipContent>
    </Tooltip>
  );
}

describe("Tooltip accessibility", () => {
  it("trigger is focusable", async () => {
    render(<TooltipDemo />);
    const trigger = screen.getByRole("button", { name: /hover me/i });
    trigger.focus();
    expect(trigger).toHaveFocus();
  });

  it("tooltip content has role=tooltip when open", async () => {
    const user = userEvent.setup();
    render(<TooltipDemo />);
    await user.hover(screen.getByRole("button", { name: /hover me/i }));
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
  });

  it("tooltip content contains the provided text", async () => {
    const user = userEvent.setup();
    render(<TooltipDemo />);
    await user.hover(screen.getByRole("button", { name: /hover me/i }));
    expect(screen.getByRole("tooltip")).toHaveTextContent(
      "Helpful tooltip text",
    );
  });

  it("trigger has aria-describedby pointing to tooltip when open", async () => {
    const user = userEvent.setup();
    render(<TooltipDemo />);
    const trigger = screen.getByRole("button", { name: /hover me/i });
    await user.hover(trigger);
    const tooltip = screen.getByRole("tooltip");
    expect(trigger).toHaveAttribute("aria-describedby", tooltip.id);
  });

  it("tooltip is hidden (not visible) when not hovered", () => {
    const { container } = render(<TooltipDemo />);
    const tooltip = container.querySelector("[role='tooltip']");
    if (tooltip) {
      // Radix keeps tooltip in DOM but hides it when closed
      expect(tooltip).not.toBeVisible();
    }
  });

  it("tooltip becomes hidden after mouse leaves trigger", async () => {
    const user = userEvent.setup();
    const { container } = render(<TooltipDemo />);
    const trigger = screen.getByRole("button", { name: /hover me/i });
    await user.hover(trigger);
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
    await user.unhover(trigger);
    const tooltip = container.querySelector("[role='tooltip']");
    if (tooltip) {
      expect(tooltip).not.toBeVisible();
    }
  });
});
