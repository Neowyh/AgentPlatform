import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

function SelectDemo() {
  return (
    <Select defaultValue="apple">
      <SelectTrigger aria-label="Choose a fruit">
        <SelectValue placeholder="Select a fruit" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="apple">Apple</SelectItem>
        <SelectItem value="banana">Banana</SelectItem>
        <SelectItem value="cherry">Cherry</SelectItem>
      </SelectContent>
    </Select>
  );
}

describe("Select accessibility", () => {
  it("trigger has combobox role", () => {
    render(<SelectDemo />);
    expect(
      screen.getByRole("combobox", { name: /choose a fruit/i }),
    ).toBeInTheDocument();
  });

  it("trigger has combobox role with expanded state", () => {
    render(<SelectDemo />);
    const combobox = screen.getByRole("combobox");
    // Radix Select trigger should have combobox role and aria-expanded
    expect(combobox).toHaveAttribute("aria-expanded");
  });

  it("trigger has aria-expanded=false initially", () => {
    render(<SelectDemo />);
    expect(screen.getByRole("combobox")).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("items have option role when opened", async () => {
    const user = userEvent.setup();
    render(<SelectDemo />);
    await user.click(screen.getByRole("combobox"));
    expect(screen.getByRole("option", { name: /apple/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /banana/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /cherry/i })).toBeInTheDocument();
  });

  it("selected item has aria-selected=true", async () => {
    const user = userEvent.setup();
    render(<SelectDemo />);
    await user.click(screen.getByRole("combobox"));
    expect(screen.getByRole("option", { name: /apple/i })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("closes on Escape key", async () => {
    const user = userEvent.setup();
    render(<SelectDemo />);
    await user.click(screen.getByRole("combobox"));
    expect(screen.getByRole("listbox")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("trigger aria-expanded=true when open", async () => {
    const user = userEvent.setup();
    render(<SelectDemo />);
    const trigger = screen.getByRole("combobox");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
  });
});
