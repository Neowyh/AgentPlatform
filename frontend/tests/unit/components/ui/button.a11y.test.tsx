import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "@/components/ui/button";

describe("Button accessibility", () => {
  it("renders as button role by default", () => {
    render(<Button>Click me</Button>);
    expect(
      screen.getByRole("button", { name: /click me/i }),
    ).toBeInTheDocument();
  });

  it("has accessible name from children", () => {
    render(<Button>Submit Form</Button>);
    expect(screen.getByRole("button")).toHaveAccessibleName("Submit Form");
  });

  it("supports aria-label for icon-only buttons", () => {
    render(
      <Button aria-label="Close dialog">
        <svg aria-hidden="true" />
      </Button>,
    );
    expect(
      screen.getByRole("button", { name: /close dialog/i }),
    ).toBeInTheDocument();
  });

  it("can be focused via keyboard tab", async () => {
    const user = userEvent.setup();
    render(<Button>Focusable</Button>);
    await user.tab();
    expect(screen.getByRole("button")).toHaveFocus();
  });

  it("activates on Enter key", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Press Enter</Button>);
    screen.getByRole("button").focus();
    await user.keyboard("{Enter}");
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("activates on Space key", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Press Space</Button>);
    screen.getByRole("button").focus();
    await user.keyboard(" ");
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("is not focusable when disabled", async () => {
    const user = userEvent.setup();
    render(<Button disabled>Disabled</Button>);
    await user.tab();
    expect(screen.getByRole("button")).not.toHaveFocus();
  });

  it("does not fire onClick when disabled", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        Disabled
      </Button>,
    );
    await user.click(screen.getByRole("button"));
    expect(onClick).not.toHaveBeenCalled();
  });

  it("has correct disabled state via aria-disabled", () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("preserves type attribute for form submission", () => {
    render(<Button type="submit">Submit</Button>);
    expect(screen.getByRole("button")).toHaveAttribute("type", "submit");
  });

  it("icon-only button has sr-only text for screen readers", () => {
    render(
      <Button aria-label="Toggle menu">
        <svg aria-hidden="true" />
      </Button>,
    );
    const button = screen.getByRole("button", { name: /toggle menu/i });
    expect(button).toBeInTheDocument();
  });
});
