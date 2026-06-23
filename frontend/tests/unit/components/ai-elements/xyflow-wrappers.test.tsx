import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

// Mock @xyflow/react
vi.mock("@xyflow/react", () => ({
  ReactFlow: ({ children, ...props }: Record<string, unknown>) => (
    <div data-testid="reactflow" {...props}>
      {children as React.ReactNode}
    </div>
  ),
  Background: (props: Record<string, unknown>) => (
    <div data-testid="background" {...props} />
  ),
  Controls: ({ className, ...props }: Record<string, unknown>) => (
    <div data-testid="controls" className={className as string} {...props} />
  ),
  Panel: ({ className, ...props }: Record<string, unknown>) => (
    <div data-testid="panel" className={className as string} {...props} />
  ),
  NodeToolbar: ({ className, position, ...props }: Record<string, unknown>) => (
    <div
      data-testid="node-toolbar"
      className={className as string}
      data-position={position}
      {...props}
    />
  ),
  Position: { Left: "left", Right: "right", Top: "top", Bottom: "bottom" },
}));

import { Canvas } from "@/components/ai-elements/canvas";
import { Controls } from "@/components/ai-elements/controls";
import { Panel } from "@/components/ai-elements/panel";
import { Toolbar } from "@/components/ai-elements/toolbar";

afterEach(() => {
  cleanup();
});

describe("Canvas", () => {
  test("renders ReactFlow component", () => {
    render(
      <Canvas data-testid="canvas">
        <p>Canvas content</p>
      </Canvas>,
    );
    // data-testid is forwarded to ReactFlow mock, so it appears on the div
    expect(screen.getByTestId("canvas")).toBeInTheDocument();
    expect(screen.getByText("Canvas content")).toBeInTheDocument();
  });

  test("renders Background component", () => {
    render(
      <Canvas>
        <p>Content</p>
      </Canvas>,
    );
    expect(screen.getByTestId("background")).toBeInTheDocument();
  });

  test("passes additional props to ReactFlow", () => {
    render(
      <Canvas data-testid="canvas" id="my-canvas">
        <p>Content</p>
      </Canvas>,
    );
    expect(screen.getByTestId("canvas")).toHaveAttribute("id", "my-canvas");
  });

  test("renders children inside ReactFlow", () => {
    render(
      <Canvas>
        <div data-testid="child">Child element</div>
      </Canvas>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });
});

describe("Controls", () => {
  test("renders controls component", () => {
    render(<Controls data-testid="controls" />);
    expect(screen.getByTestId("controls")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(<Controls className="custom-controls" data-testid="controls" />);
    expect(screen.getByTestId("controls")).toHaveClass("custom-controls");
  });

  test("has overflow-hidden and rounded-md classes", () => {
    render(<Controls data-testid="controls" />);
    const el = screen.getByTestId("controls");
    expect(el.className).toContain("rounded-md");
    expect(el.className).toContain("border");
    expect(el.className).toContain("overflow-hidden");
  });
});

describe("Panel", () => {
  test("renders panel component", () => {
    render(
      <Panel data-testid="panel">
        <p>Panel content</p>
      </Panel>,
    );
    expect(screen.getByTestId("panel")).toBeInTheDocument();
    expect(screen.getByText("Panel content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Panel className="custom-panel" data-testid="panel">
        <p>Content</p>
      </Panel>,
    );
    expect(screen.getByTestId("panel")).toHaveClass("custom-panel");
  });

  test("has rounded-md and border classes", () => {
    render(
      <Panel data-testid="panel">
        <p>Content</p>
      </Panel>,
    );
    const el = screen.getByTestId("panel");
    expect(el.className).toContain("rounded-md");
    expect(el.className).toContain("border");
    expect(el.className).toContain("overflow-hidden");
  });
});

describe("Toolbar", () => {
  test("renders toolbar component", () => {
    render(
      <Toolbar data-testid="toolbar">
        <button>Action 1</button>
        <button>Action 2</button>
      </Toolbar>,
    );
    expect(screen.getByTestId("toolbar")).toBeInTheDocument();
    expect(screen.getByText("Action 1")).toBeInTheDocument();
    expect(screen.getByText("Action 2")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Toolbar className="custom-toolbar" data-testid="toolbar">
        <span>Content</span>
      </Toolbar>,
    );
    expect(screen.getByTestId("toolbar")).toHaveClass("custom-toolbar");
  });

  test("has border and rounded-sm classes", () => {
    render(
      <Toolbar data-testid="toolbar">
        <span>Content</span>
      </Toolbar>,
    );
    const el = screen.getByTestId("toolbar");
    expect(el.className).toContain("rounded-sm");
    expect(el.className).toContain("border");
    expect(el.className).toContain("flex");
    expect(el.className).toContain("items-center");
  });

  test("has gap-1 class", () => {
    render(
      <Toolbar data-testid="toolbar">
        <span>Content</span>
      </Toolbar>,
    );
    expect(screen.getByTestId("toolbar").className).toContain("gap-1");
  });
});
