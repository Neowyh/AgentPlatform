import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

function CollapsibleDemo() {
  return (
    <Collapsible>
      <CollapsibleTrigger>Toggle section</CollapsibleTrigger>
      <CollapsibleContent>
        <p>Hidden content goes here</p>
      </CollapsibleContent>
    </Collapsible>
  );
}

describe("Collapsible accessibility", () => {
  it("trigger has button role", () => {
    render(<CollapsibleDemo />);
    expect(
      screen.getByRole("button", { name: /toggle section/i }),
    ).toBeInTheDocument();
  });

  it("trigger has aria-expanded=false when closed", () => {
    render(<CollapsibleDemo />);
    expect(screen.getByRole("button")).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("content is not visible when closed", () => {
    render(<CollapsibleDemo />);
    expect(
      screen.queryByText("Hidden content goes here"),
    ).not.toBeInTheDocument();
  });

  it("toggles aria-expanded on click", async () => {
    const user = userEvent.setup();
    render(<CollapsibleDemo />);
    const trigger = screen.getByRole("button");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
  });

  it("content becomes visible when expanded", async () => {
    const user = userEvent.setup();
    render(<CollapsibleDemo />);
    expect(
      screen.queryByText("Hidden content goes here"),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button"));
    expect(screen.getByText("Hidden content goes here")).toBeInTheDocument();
  });

  it("content is hidden again after second click", async () => {
    const user = userEvent.setup();
    render(<CollapsibleDemo />);
    const trigger = screen.getByRole("button");
    await user.click(trigger);
    expect(screen.getByText("Hidden content goes here")).toBeInTheDocument();
    await user.click(trigger);
    expect(
      screen.queryByText("Hidden content goes here"),
    ).not.toBeInTheDocument();
  });
});
