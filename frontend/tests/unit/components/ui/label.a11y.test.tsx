import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

describe("Label accessibility", () => {
  it("renders as label element", () => {
    render(<Label htmlFor="test-input">Name</Label>);
    const label = screen.getByText("Name");
    expect(label.tagName).toBe("LABEL");
  });

  it("associates with input via htmlFor", () => {
    render(
      <>
        <Label htmlFor="email">Email</Label>
        <Input id="email" />
      </>,
    );
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
  });

  it("provides accessible name to associated input", () => {
    render(
      <>
        <Label htmlFor="password">Password</Label>
        <Input id="password" type="password" />
      </>,
    );
    expect(screen.getByLabelText("Password")).toHaveAttribute(
      "type",
      "password",
    );
  });

  it("label has correct htmlFor attribute", () => {
    render(
      <>
        <Label htmlFor="focus-test">Focus me</Label>
        <Input id="focus-test" />
      </>,
    );
    const label = screen.getByText("Focus me");
    expect(label).toHaveAttribute("for", "focus-test");
  });
});
