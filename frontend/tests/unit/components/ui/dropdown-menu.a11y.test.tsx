import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function DropdownDemo() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger>Options</DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuItem>Edit</DropdownMenuItem>
        <DropdownMenuItem>Duplicate</DropdownMenuItem>
        <DropdownMenuItem variant="destructive">Delete</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

describe("DropdownMenu accessibility", () => {
  it("trigger has button role", () => {
    render(<DropdownDemo />);
    expect(screen.getByRole("button", { name: /options/i })).toHaveRole(
      "button",
    );
  });

  it("trigger has aria-haspopup", () => {
    render(<DropdownDemo />);
    expect(screen.getByRole("button", { name: /options/i })).toHaveAttribute(
      "aria-haspopup",
      "menu",
    );
  });

  it("items have menuitem role when opened", async () => {
    const user = userEvent.setup();
    render(<DropdownDemo />);
    await user.click(screen.getByRole("button", { name: /options/i }));
    expect(screen.getByRole("menuitem", { name: /edit/i })).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: /duplicate/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: /delete/i }),
    ).toBeInTheDocument();
  });

  it("closes on Escape key", async () => {
    const user = userEvent.setup();
    render(<DropdownDemo />);
    await user.click(screen.getByRole("button", { name: /options/i }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("items are keyboard navigable", async () => {
    const user = userEvent.setup();
    render(<DropdownDemo />);
    await user.click(screen.getByRole("button", { name: /options/i }));
    await user.keyboard("{ArrowDown}");
    // Focus should be on first item
    expect(screen.getByRole("menuitem", { name: /edit/i })).toHaveFocus();
  });

  it("trigger aria-expanded changes on open/close", async () => {
    const user = userEvent.setup();
    render(<DropdownDemo />);
    const trigger = screen.getByRole("button", { name: /options/i });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    await user.keyboard("{Escape}");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });
});
