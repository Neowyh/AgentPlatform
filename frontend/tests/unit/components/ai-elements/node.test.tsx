import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

// Mock @xyflow/react
vi.mock("@xyflow/react", () => ({
  Handle: ({ position, type, ...props }: Record<string, unknown>) => (
    <div data-testid={`handle-${type}`} data-position={position} {...props} />
  ),
  Position: { Left: "left", Right: "right", Top: "top", Bottom: "bottom" },
  Card: ({ children, className, ...props }: Record<string, unknown>) => (
    <div className={className as string} data-testid="card" {...props}>
      {children as React.ReactNode}
    </div>
  ),
}));

import {
  Node,
  NodeHeader,
  NodeTitle,
  NodeDescription,
  NodeAction,
  NodeContent,
  NodeFooter,
} from "@/components/ai-elements/node";

afterEach(() => {
  cleanup();
});

describe("Node", () => {
  test("renders with children", () => {
    render(
      <Node handles={{ target: false, source: false }} data-testid="node">
        <p>Node content</p>
      </Node>,
    );
    expect(screen.getByTestId("node")).toBeInTheDocument();
    expect(screen.getByText("Node content")).toBeInTheDocument();
  });

  test("renders target handle when target=true", () => {
    render(
      <Node handles={{ target: true, source: false }} data-testid="node" />,
    );
    expect(screen.getByTestId("handle-target")).toBeInTheDocument();
    expect(screen.queryByTestId("handle-source")).not.toBeInTheDocument();
  });

  test("renders source handle when source=true", () => {
    render(
      <Node handles={{ target: false, source: true }} data-testid="node" />,
    );
    expect(screen.getByTestId("handle-source")).toBeInTheDocument();
    expect(screen.queryByTestId("handle-target")).not.toBeInTheDocument();
  });

  test("renders both handles when both true", () => {
    render(
      <Node handles={{ target: true, source: true }} data-testid="node" />,
    );
    expect(screen.getByTestId("handle-target")).toBeInTheDocument();
    expect(screen.getByTestId("handle-source")).toBeInTheDocument();
  });

  test("renders no handles when both false", () => {
    render(
      <Node handles={{ target: false, source: false }} data-testid="node" />,
    );
    expect(screen.queryByTestId("handle-target")).not.toBeInTheDocument();
    expect(screen.queryByTestId("handle-source")).not.toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Node
        handles={{ target: false, source: false }}
        className="custom-node"
        data-testid="node"
      />,
    );
    expect(screen.getByTestId("node")).toHaveClass("custom-node");
  });

  test("has rounded-md and border classes", () => {
    render(
      <Node handles={{ target: false, source: false }} data-testid="node" />,
    );
    const el = screen.getByTestId("node");
    expect(el.className).toContain("rounded-md");
    expect(el.className).toContain("border");
  });
});

describe("NodeHeader", () => {
  test("renders with children", () => {
    render(
      <NodeHeader data-testid="header">
        <span>Header content</span>
      </NodeHeader>,
    );
    expect(screen.getByText("Header content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <NodeHeader className="custom-header" data-testid="header">
        <span>Header</span>
      </NodeHeader>,
    );
    expect(screen.getByTestId("header")).toHaveClass("custom-header");
  });

  test("has border-b and rounded-t-md classes", () => {
    render(
      <NodeHeader data-testid="header">
        <span>Header</span>
      </NodeHeader>,
    );
    const el = screen.getByTestId("header");
    expect(el.className).toContain("border-b");
    expect(el.className).toContain("rounded-t-md");
  });
});

describe("NodeTitle", () => {
  test("renders children", () => {
    render(<NodeTitle data-testid="title">Node Title</NodeTitle>);
    expect(screen.getByText("Node Title")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <NodeTitle className="custom-title" data-testid="title">
        Title
      </NodeTitle>,
    );
    expect(screen.getByTestId("title")).toHaveClass("custom-title");
  });
});

describe("NodeDescription", () => {
  test("renders children", () => {
    render(
      <NodeDescription data-testid="desc">Node description</NodeDescription>,
    );
    expect(screen.getByText("Node description")).toBeInTheDocument();
  });
});

describe("NodeAction", () => {
  test("renders children", () => {
    render(
      <NodeAction data-testid="action">
        <button>Action</button>
      </NodeAction>,
    );
    expect(screen.getByText("Action")).toBeInTheDocument();
  });
});

describe("NodeContent", () => {
  test("renders children", () => {
    render(
      <NodeContent data-testid="content">
        <p>Content body</p>
      </NodeContent>,
    );
    expect(screen.getByText("Content body")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <NodeContent className="custom-content" data-testid="content">
        <span>Content</span>
      </NodeContent>,
    );
    expect(screen.getByTestId("content")).toHaveClass("custom-content");
  });

  test("has p-3 class", () => {
    render(
      <NodeContent data-testid="content">
        <span>Content</span>
      </NodeContent>,
    );
    expect(screen.getByTestId("content").className).toContain("p-3");
  });
});

describe("NodeFooter", () => {
  test("renders children", () => {
    render(
      <NodeFooter data-testid="footer">
        <span>Footer content</span>
      </NodeFooter>,
    );
    expect(screen.getByText("Footer content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <NodeFooter className="custom-footer" data-testid="footer">
        <span>Footer</span>
      </NodeFooter>,
    );
    expect(screen.getByTestId("footer")).toHaveClass("custom-footer");
  });

  test("has border-t and rounded-b-md classes", () => {
    render(
      <NodeFooter data-testid="footer">
        <span>Footer</span>
      </NodeFooter>,
    );
    const el = screen.getByTestId("footer");
    expect(el.className).toContain("border-t");
    expect(el.className).toContain("rounded-b-md");
  });
});

describe("Node composition", () => {
  test("renders a full node layout", () => {
    render(
      <Node handles={{ target: true, source: true }} data-testid="node">
        <NodeHeader>
          <NodeTitle>My Node</NodeTitle>
          <NodeDescription>A description</NodeDescription>
        </NodeHeader>
        <NodeContent>
          <p>Node body content</p>
        </NodeContent>
        <NodeFooter>
          <span>Footer info</span>
        </NodeFooter>
      </Node>,
    );

    expect(screen.getByText("My Node")).toBeInTheDocument();
    expect(screen.getByText("A description")).toBeInTheDocument();
    expect(screen.getByText("Node body content")).toBeInTheDocument();
    expect(screen.getByText("Footer info")).toBeInTheDocument();
    expect(screen.getByTestId("handle-target")).toBeInTheDocument();
    expect(screen.getByTestId("handle-source")).toBeInTheDocument();
  });
});
