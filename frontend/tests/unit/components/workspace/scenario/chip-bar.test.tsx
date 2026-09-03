import { render, screen, cleanup } from "@testing-library/react";
import { vi, describe, it, expect, afterEach } from "vitest";

vi.mock("@/components/workspace/tooltip", () => ({
  Tooltip: ({
    children,
    content,
  }: {
    children: React.ReactNode;
    content?: React.ReactNode;
  }) => (
    <div data-testid="tooltip">
      {children}
      <div data-testid="tooltip-content">{content}</div>
    </div>
  ),
}));

import { ChipBar } from "@/components/workspace/scenario/chip-bar";

afterEach(() => {
  cleanup();
});

describe("ChipBar descriptions", () => {
  it("wraps the item in a Tooltip carrying its description", () => {
    render(
      <ChipBar
        items={[{ id: "a", label: "Agent A", description: "Handles chats" }]}
        selectedId={null}
        onSelect={vi.fn()}
        variant="pill"
      />,
    );

    const tooltip = screen.getByTestId("tooltip");
    expect(screen.getByTestId("tooltip-content").textContent).toBe(
      "Handles chats",
    );
    expect(tooltip).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Agent A" })).toBeInTheDocument();
  });

  it("renders items without a description with no Tooltip", () => {
    render(
      <ChipBar
        items={[{ id: "a", label: "Agent A" }]}
        selectedId={null}
        onSelect={vi.fn()}
        variant="pill"
      />,
    );

    expect(screen.queryByTestId("tooltip")).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Agent A" })).toBeInTheDocument();
  });

  it("passes long descriptions through untruncated", () => {
    const longDescription = "简介".repeat(100);
    render(
      <ChipBar
        items={[{ id: "a", label: "Agent A", description: longDescription }]}
        selectedId={null}
        onSelect={vi.fn()}
        variant="pill"
      />,
    );

    expect(screen.getByTestId("tooltip-content").textContent).toBe(
      longDescription,
    );
  });
});
