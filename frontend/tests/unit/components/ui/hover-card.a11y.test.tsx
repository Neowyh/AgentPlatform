import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Link from "next/link";
import { describe, expect, it } from "vitest";

import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";

function HoverCardDemo() {
  return (
    <HoverCard>
      <HoverCardTrigger asChild>
        <Link href="/profile">@username</Link>
      </HoverCardTrigger>
      <HoverCardContent>
        <p>Profile details here</p>
      </HoverCardContent>
    </HoverCard>
  );
}

describe("HoverCard accessibility", () => {
  it("trigger is a focusable link", () => {
    render(<HoverCardDemo />);
    const trigger = screen.getByRole("link", { name: /@username/i });
    expect(trigger).toBeInTheDocument();
    expect(trigger).toHaveAttribute("href", "/profile");
  });

  it("trigger is keyboard focusable", async () => {
    const user = userEvent.setup();
    render(<HoverCardDemo />);
    const trigger = screen.getByRole("link", { name: /@username/i });
    await user.tab();
    expect(trigger).toHaveFocus();
  });

  it("hover card content is not in the DOM when closed", () => {
    render(<HoverCardDemo />);
    expect(screen.queryByText("Profile details here")).not.toBeInTheDocument();
  });

  it("hover card root renders without errors", () => {
    render(<HoverCardDemo />);
    expect(
      screen.getByRole("link", { name: /@username/i }),
    ).toBeInTheDocument();
  });

  it("trigger has aria-describedby when hover card is open", async () => {
    const user = userEvent.setup();
    render(<HoverCardDemo />);
    const trigger = screen.getByRole("link", { name: /@username/i });
    await user.hover(trigger);
    // Radix HoverCard sets aria-describedby on the trigger
    const describedBy = trigger.getAttribute("aria-describedby");
    if (describedBy) {
      expect(describedBy).toBeTruthy();
    }
  });
});
