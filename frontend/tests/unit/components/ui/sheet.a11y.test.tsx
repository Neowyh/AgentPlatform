import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Link from "next/link";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

function SheetDemo() {
  const [open, setOpen] = useState(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger>Open Sheet</SheetTrigger>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Navigation</SheetTitle>
          <SheetDescription>Main site navigation</SheetDescription>
        </SheetHeader>
        <nav>
          <ul>
            <li>
              <Link href="/">Home</Link>
            </li>
            <li>
              <Link href="/about">About</Link>
            </li>
          </ul>
        </nav>
        <SheetClose>Close</SheetClose>
      </SheetContent>
    </Sheet>
  );
}

describe("Sheet accessibility", () => {
  it("trigger has button role", () => {
    render(<SheetDemo />);
    expect(
      screen.getByRole("button", { name: /open sheet/i }),
    ).toBeInTheDocument();
  });

  it("content has dialog role when open", async () => {
    const user = userEvent.setup();
    render(<SheetDemo />);
    await user.click(screen.getByRole("button", { name: /open sheet/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("dialog has accessible name from SheetTitle", async () => {
    const user = userEvent.setup();
    render(<SheetDemo />);
    await user.click(screen.getByRole("button", { name: /open sheet/i }));
    expect(screen.getByRole("dialog")).toHaveAccessibleName("Navigation");
  });

  it("dialog has accessible description from SheetDescription", async () => {
    const user = userEvent.setup();
    render(<SheetDemo />);
    await user.click(screen.getByRole("button", { name: /open sheet/i }));
    expect(screen.getByRole("dialog")).toHaveAccessibleDescription(
      "Main site navigation",
    );
  });

  it("closes on Escape key", async () => {
    const user = userEvent.setup();
    render(<SheetDemo />);
    await user.click(screen.getByRole("button", { name: /open sheet/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("close button has sr-only accessible name", async () => {
    const user = userEvent.setup();
    render(<SheetDemo />);
    await user.click(screen.getByRole("button", { name: /open sheet/i }));
    // SheetContent has a built-in close button with sr-only "Close" text
    const dialog = screen.getByRole("dialog");
    const closeButtons = dialog.querySelectorAll("button");
    expect(closeButtons.length).toBeGreaterThan(0);
    // At least one button should have "Close" text (sr-only)
    const hasClose = Array.from(closeButtons).some((btn) =>
      btn.textContent?.includes("Close"),
    );
    expect(hasClose).toBe(true);
  });

  it("content inside sheet is accessible", async () => {
    const user = userEvent.setup();
    render(<SheetDemo />);
    await user.click(screen.getByRole("button", { name: /open sheet/i }));
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /home/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /about/i })).toBeInTheDocument();
  });
});
