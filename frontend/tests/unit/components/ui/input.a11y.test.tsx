import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Input } from "@/components/ui/input";

describe("Input accessibility", () => {
  it("renders as textbox role", () => {
    render(<Input aria-label="Email" />);
    expect(screen.getByRole("textbox", { name: /email/i })).toBeInTheDocument();
  });

  it("has accessible name from aria-label", () => {
    render(<Input aria-label="Search" />);
    expect(screen.getByRole("textbox")).toHaveAccessibleName("Search");
  });

  it("can be focused via tab", async () => {
    const user = userEvent.setup();
    render(<Input aria-label="Name" />);
    await user.tab();
    expect(screen.getByRole("textbox")).toHaveFocus();
  });

  it("accepts text input", async () => {
    const user = userEvent.setup();
    render(<Input aria-label="Name" />);
    await user.type(screen.getByRole("textbox"), "John");
    expect(screen.getByRole("textbox")).toHaveValue("John");
  });

  it("is not focusable when disabled", async () => {
    const user = userEvent.setup();
    render(<Input aria-label="Disabled" disabled />);
    await user.tab();
    expect(screen.getByRole("textbox")).not.toHaveFocus();
  });

  it("has aria-invalid when aria-invalid is set", () => {
    render(<Input aria-label="Field" aria-invalid="true" />);
    expect(screen.getByRole("textbox")).toHaveAttribute("aria-invalid", "true");
  });

  it("supports placeholder as text alternative", () => {
    render(<Input placeholder="Enter your name" />);
    expect(screen.getByPlaceholderText("Enter your name")).toBeInTheDocument();
  });

  it("password type renders as textbox with appropriate type", () => {
    render(<Input type="password" aria-label="Password" />);
    const input = screen.getByLabelText(/password/i);
    expect(input).toHaveAttribute("type", "password");
  });
});
