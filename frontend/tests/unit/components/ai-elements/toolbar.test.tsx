import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@xyflow/react", () => ({
  NodeToolbar: ({
    children,
    className,
    position,
    ...props
  }: {
    children: React.ReactNode;
    className?: string;
    position?: number;
    [key: string]: unknown;
  }) => (
    <div
      data-testid="node-toolbar"
      data-position={position}
      className={className}
      {...props}
    >
      {children}
    </div>
  ),
  Position: {
    Bottom: 1,
    Top: 2,
    Left: 3,
    Right: 4,
  },
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let Toolbar: typeof import("@/components/ai-elements/toolbar").Toolbar;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/ai-elements/toolbar");
  Toolbar = mod.Toolbar;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("Toolbar", () => {
  test("renders children", () => {
    render(
      <Toolbar>
        <button>Action</button>
      </Toolbar>,
    );
    expect(screen.getByText("Action")).toBeInTheDocument();
  });

  test("renders NodeToolbar wrapper", () => {
    render(
      <Toolbar>
        <span>Content</span>
      </Toolbar>,
    );
    expect(screen.getByTestId("node-toolbar")).toBeInTheDocument();
  });

  test("sets position to Bottom", () => {
    render(
      <Toolbar>
        <span>Content</span>
      </Toolbar>,
    );
    expect(screen.getByTestId("node-toolbar")).toHaveAttribute(
      "data-position",
      "1",
    );
  });

  test("applies custom className", () => {
    render(
      <Toolbar className="my-toolbar">
        <span>Content</span>
      </Toolbar>,
    );
    const toolbar = screen.getByTestId("node-toolbar");
    expect(toolbar.getAttribute("class")).toContain("my-toolbar");
  });

  test("always includes default styling classes", () => {
    render(
      <Toolbar>
        <span>Content</span>
      </Toolbar>,
    );
    const toolbar = screen.getByTestId("node-toolbar");
    expect(toolbar.getAttribute("class")).toContain("bg-background");
    expect(toolbar.getAttribute("class")).toContain("rounded-sm");
    expect(toolbar.getAttribute("class")).toContain("border");
  });

  test("renders multiple children", () => {
    render(
      <Toolbar>
        <button>First</button>
        <button>Second</button>
      </Toolbar>,
    );
    expect(screen.getByText("First")).toBeInTheDocument();
    expect(screen.getByText("Second")).toBeInTheDocument();
  });

  test("passes additional props to NodeToolbar", () => {
    render(
      <Toolbar data-custom="test-value">
        <span>Content</span>
      </Toolbar>,
    );
    expect(screen.getByTestId("node-toolbar")).toHaveAttribute(
      "data-custom",
      "test-value",
    );
  });
});
