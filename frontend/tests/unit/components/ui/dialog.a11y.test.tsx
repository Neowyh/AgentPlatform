import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

function DialogDemo() {
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger>Open Dialog</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Confirm Action</DialogTitle>
          <DialogDescription>
            Are you sure you want to proceed?
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose>Cancel</DialogClose>
          <button type="button">Confirm</button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

describe("Dialog accessibility", () => {
  it("trigger has button role", () => {
    render(<DialogDemo />);
    expect(screen.getByRole("button", { name: /open dialog/i })).toHaveRole(
      "button",
    );
  });

  it("dialog content has dialog role when open", async () => {
    const user = userEvent.setup();
    render(<DialogDemo />);
    await user.click(screen.getByRole("button", { name: /open dialog/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("dialog has accessible name from DialogTitle", async () => {
    const user = userEvent.setup();
    render(<DialogDemo />);
    await user.click(screen.getByRole("button", { name: /open dialog/i }));
    expect(screen.getByRole("dialog")).toHaveAccessibleName("Confirm Action");
  });

  it("dialog has accessible description from DialogDescription", async () => {
    const user = userEvent.setup();
    render(<DialogDemo />);
    await user.click(screen.getByRole("button", { name: /open dialog/i }));
    expect(screen.getByRole("dialog")).toHaveAccessibleDescription(
      "Are you sure you want to proceed?",
    );
  });

  it("close button has accessible name", async () => {
    const user = userEvent.setup();
    render(<DialogDemo />);
    await user.click(screen.getByRole("button", { name: /open dialog/i }));
    expect(screen.getByRole("button", { name: /close/i })).toBeInTheDocument();
  });

  it("closes on Escape key", async () => {
    const user = userEvent.setup();
    render(<DialogDemo />);
    await user.click(screen.getByRole("button", { name: /open dialog/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes on Cancel button click", async () => {
    const user = userEvent.setup();
    render(<DialogDemo />);
    await user.click(screen.getByRole("button", { name: /open dialog/i }));
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("focus is trapped within dialog", async () => {
    const user = userEvent.setup();
    render(<DialogDemo />);
    await user.click(screen.getByRole("button", { name: /open dialog/i }));
    // Focus should be inside the dialog
    const dialog = screen.getByRole("dialog");
    expect(dialog).toContainElement(document.activeElement);
  });
});
