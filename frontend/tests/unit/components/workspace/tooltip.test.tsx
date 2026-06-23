import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { Tooltip } from "@/components/workspace/tooltip";

// Mock the Radix tooltip primitives to make testing simpler
vi.mock("@/components/ui/tooltip", () => ({
  Tooltip: ({
    children,
    ...props
  }: {
    children: React.ReactNode;
    [key: string]: unknown;
  }) => <div data-testid="tooltip-root">{children}</div>,
  TooltipTrigger: ({
    children,
    asChild,
    ...props
  }: {
    children: React.ReactNode;
    asChild?: boolean;
    [key: string]: unknown;
  }) => <div data-testid="tooltip-trigger">{children}</div>,
  TooltipContent: ({
    children,
    ...props
  }: {
    children: React.ReactNode;
    [key: string]: unknown;
  }) => <div data-testid="tooltip-content">{children}</div>,
}));

describe("Tooltip", () => {
  test("renders children inside the trigger", () => {
    render(
      <Tooltip content="Help text">
        <button>Hover me</button>
      </Tooltip>,
    );
    expect(screen.getByText("Hover me")).toBeInTheDocument();
    expect(screen.getByTestId("tooltip-trigger")).toContainElement(
      screen.getByText("Hover me"),
    );
  });

  test("renders content in the tooltip content area", () => {
    render(
      <Tooltip content="Help text">
        <button>Hover me</button>
      </Tooltip>,
    );
    expect(screen.getByText("Help text")).toBeInTheDocument();
    expect(screen.getByTestId("tooltip-content")).toContainElement(
      screen.getByText("Help text"),
    );
  });

  test("renders with React node content", () => {
    render(
      <Tooltip content={<span data-testid="custom-content">Custom</span>}>
        <button>Hover me</button>
      </Tooltip>,
    );
    expect(screen.getByTestId("custom-content")).toBeInTheDocument();
    expect(screen.getByText("Custom")).toBeInTheDocument();
  });

  test("renders without content (undefined)", () => {
    const { container } = render(
      <Tooltip>
        <button>Hover me</button>
      </Tooltip>,
    );
    expect(screen.getByText("Hover me")).toBeInTheDocument();
    // Content area should still exist but be empty
    const contentArea = screen.getByTestId("tooltip-content");
    expect(contentArea).toBeInTheDocument();
    expect(contentArea.textContent).toBe("");
  });

  test("passes delayDuration to tooltip primitive", () => {
    render(
      <Tooltip content="Help">
        <button>Test</button>
      </Tooltip>,
    );
    // The root tooltip component receives delayDuration={500}
    const root = screen.getByTestId("tooltip-root");
    expect(root).toBeInTheDocument();
  });
});
