import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

function ToggleGroupDemo() {
  return (
    <ToggleGroup type="single" defaultValue="left" aria-label="Text alignment">
      <ToggleGroupItem value="left" aria-label="Align left">
        Left
      </ToggleGroupItem>
      <ToggleGroupItem value="center" aria-label="Align center">
        Center
      </ToggleGroupItem>
      <ToggleGroupItem value="right" aria-label="Align right">
        Right
      </ToggleGroupItem>
    </ToggleGroup>
  );
}

describe("ToggleGroup accessibility", () => {
  it("group has group role", () => {
    render(<ToggleGroupDemo />);
    expect(screen.getByRole("group")).toBeInTheDocument();
  });

  it("group has accessible name from aria-label", () => {
    render(<ToggleGroupDemo />);
    expect(screen.getByRole("group")).toHaveAccessibleName("Text alignment");
  });

  it("items have radio role for single type", () => {
    render(<ToggleGroupDemo />);
    // Radix ToggleGroup type="single" renders items as radio buttons
    expect(
      screen.getByRole("radio", { name: /align left/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("radio", { name: /align center/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("radio", { name: /align right/i }),
    ).toBeInTheDocument();
  });

  it("selected item has aria-checked=true", () => {
    render(<ToggleGroupDemo />);
    const leftRadio = screen.getByRole("radio", { name: /align left/i });
    expect(leftRadio).toHaveAttribute("aria-checked", "true");
  });

  it("unselected items have aria-checked=false", () => {
    render(<ToggleGroupDemo />);
    const centerRadio = screen.getByRole("radio", { name: /align center/i });
    const rightRadio = screen.getByRole("radio", { name: /align right/i });
    expect(centerRadio).toHaveAttribute("aria-checked", "false");
    expect(rightRadio).toHaveAttribute("aria-checked", "false");
  });

  it("selection changes on click", async () => {
    const user = userEvent.setup();
    render(<ToggleGroupDemo />);
    await user.click(screen.getByRole("radio", { name: /align right/i }));
    expect(screen.getByRole("radio", { name: /align right/i })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByRole("radio", { name: /align left/i })).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("supports multiple selection type", () => {
    function MultiDemo() {
      return (
        <ToggleGroup type="multiple" aria-label="Formatting">
          <ToggleGroupItem value="bold" aria-label="Bold">
            B
          </ToggleGroupItem>
          <ToggleGroupItem value="italic" aria-label="Italic">
            I
          </ToggleGroupItem>
        </ToggleGroup>
      );
    }
    render(<MultiDemo />);
    expect(screen.getByRole("group")).toHaveAccessibleName("Formatting");
    // Multiple type renders items as buttons with aria-pressed
    expect(screen.getByRole("button", { name: /bold/i })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });
});
