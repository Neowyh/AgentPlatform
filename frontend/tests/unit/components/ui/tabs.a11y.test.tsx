import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

function TabsDemo() {
  return (
    <Tabs defaultValue="account">
      <TabsList>
        <TabsTrigger value="account">Account</TabsTrigger>
        <TabsTrigger value="password">Password</TabsTrigger>
      </TabsList>
      <TabsContent value="account">Account settings</TabsContent>
      <TabsContent value="password">Password settings</TabsContent>
    </Tabs>
  );
}

describe("Tabs accessibility", () => {
  it("tablist has tablist role", () => {
    render(<TabsDemo />);
    expect(screen.getByRole("tablist")).toBeInTheDocument();
  });

  it("tabs have tab role", () => {
    render(<TabsDemo />);
    expect(screen.getByRole("tab", { name: /account/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /password/i })).toBeInTheDocument();
  });

  it("active tab has aria-selected=true", () => {
    render(<TabsDemo />);
    expect(screen.getByRole("tab", { name: /account/i })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("inactive tab has aria-selected=false", () => {
    render(<TabsDemo />);
    expect(screen.getByRole("tab", { name: /password/i })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  it("active tab panel has role=tabpanel", () => {
    render(<TabsDemo />);
    expect(screen.getByRole("tabpanel")).toBeInTheDocument();
  });

  it("active tab panel has aria-labelledby pointing to tab", () => {
    render(<TabsDemo />);
    const tab = screen.getByRole("tab", { name: /account/i });
    const panel = screen.getByRole("tabpanel");
    expect(panel).toHaveAttribute("aria-labelledby", tab.id);
  });

  it("tab has aria-controls pointing to panel", () => {
    render(<TabsDemo />);
    const tab = screen.getByRole("tab", { name: /account/i });
    const panel = screen.getByRole("tabpanel");
    expect(tab).toHaveAttribute("aria-controls", panel.id);
  });

  it("switches tab on click", async () => {
    const user = userEvent.setup();
    render(<TabsDemo />);
    await user.click(screen.getByRole("tab", { name: /password/i }));
    expect(screen.getByRole("tab", { name: /password/i })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Password settings");
  });

  it("navigates between tabs with arrow keys", async () => {
    const user = userEvent.setup();
    render(<TabsDemo />);
    const accountTab = screen.getByRole("tab", { name: /account/i });
    accountTab.focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: /password/i })).toHaveFocus();
    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: /account/i })).toHaveFocus();
  });

  it("inactive panel is not visible", () => {
    render(<TabsDemo />);
    const panels = screen.getAllByRole("tabpanel");
    expect(panels).toHaveLength(1); // Only active panel rendered
  });
});
