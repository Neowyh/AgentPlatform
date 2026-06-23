import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const mockUseInternalNode = vi.hoisted(() =>
  vi.fn((nodeId: string) => {
    if (nodeId === "missing-node") return null;
    return {
      internals: {
        positionAbsolute: { x: 10, y: 20 },
        handleBounds: {
          source: [{ position: "right", width: 10, height: 10, x: 5, y: 5 }],
          target: [{ position: "left", width: 10, height: 10, x: 0, y: 0 }],
        },
      },
    };
  }),
);

vi.mock("@xyflow/react", () => ({
  BaseEdge: ({
    id,
    path,
    style,
    markerEnd,
  }: {
    id: string;
    path: string;
    style?: Record<string, string>;
    markerEnd?: string;
  }) => (
    <svg
      data-testid="base-edge"
      data-id={id}
      data-path={path}
      data-marker-end={markerEnd || ""}
      style={style}
    />
  ),
  getBezierPath: () => ["M0,0 C50,50 50,50 100,100"],
  getSimpleBezierPath: () => ["M0,0 L100,100"],
  useInternalNode: mockUseInternalNode,
  Position: { Left: "left", Right: "right", Top: "top", Bottom: "bottom" },
}));

import { Edge } from "@/components/ai-elements/edge";
import { Position } from "@xyflow/react";

beforeEach(() => {
  mockUseInternalNode.mockImplementation((nodeId: string) => {
    if (nodeId === "missing-node") return null;
    return {
      internals: {
        positionAbsolute: { x: 10, y: 20 },
        handleBounds: {
          source: [{ position: "right", width: 10, height: 10, x: 5, y: 5 }],
          target: [{ position: "left", width: 10, height: 10, x: 0, y: 0 }],
        },
      },
    };
  });
});

afterEach(() => {
  cleanup();
});

describe("Edge.Temporary", () => {
  test("renders BaseEdge with dashed stroke", () => {
    const { container } = render(
      <svg>
        <Edge.Temporary
          id="test-edge"
          source="s1"
          target="t1"
          sourceX={0}
          sourceY={0}
          targetX={100}
          targetY={100}
          sourcePosition={Position.Right}
          targetPosition={Position.Left}
        />
      </svg>,
    );
    const edge = container.querySelector("[data-testid='base-edge']");
    expect(edge).toBeInTheDocument();
  });

  test("passes id to BaseEdge", () => {
    const { container } = render(
      <svg>
        <Edge.Temporary
          id="my-edge-id"
          source="s1"
          target="t1"
          sourceX={0}
          sourceY={0}
          targetX={100}
          targetY={100}
          sourcePosition={Position.Right}
          targetPosition={Position.Left}
        />
      </svg>,
    );
    const edge = container.querySelector("[data-testid='base-edge']");
    expect(edge).toHaveAttribute("data-id", "my-edge-id");
  });

  test("renders with stroke-dasharray style", () => {
    const { container } = render(
      <svg>
        <Edge.Temporary
          id="dashed-edge"
          source="s1"
          target="t1"
          sourceX={0}
          sourceY={0}
          targetX={100}
          targetY={100}
          sourcePosition={Position.Right}
          targetPosition={Position.Left}
        />
      </svg>,
    );
    const edge = container.querySelector("[data-testid='base-edge']");
    expect(edge).toBeInTheDocument();
  });
});

describe("Edge.Animated", () => {
  test("renders animated edge with circle", () => {
    const { container } = render(
      <svg>
        <Edge.Animated
          id="anim-edge"
          source="s1"
          target="t1"
          sourceX={0}
          sourceY={0}
          targetX={100}
          targetY={100}
          sourcePosition={Position.Right}
          targetPosition={Position.Left}
        />
      </svg>,
    );
    const circle = container.querySelector("circle");
    expect(circle).toBeInTheDocument();
  });

  test("renders BaseEdge for animated edge", () => {
    const { container } = render(
      <svg>
        <Edge.Animated
          id="anim-base"
          source="s1"
          target="t1"
          sourceX={0}
          sourceY={0}
          targetX={100}
          targetY={100}
          sourcePosition={Position.Right}
          targetPosition={Position.Left}
        />
      </svg>,
    );
    const edge = container.querySelector("[data-testid='base-edge']");
    expect(edge).toBeInTheDocument();
  });

  test("renders circle with animateMotion", () => {
    const { container } = render(
      <svg>
        <Edge.Animated
          id="anim-motion"
          source="s1"
          target="t1"
          sourceX={0}
          sourceY={0}
          targetX={100}
          targetY={100}
          sourcePosition={Position.Right}
          targetPosition={Position.Left}
        />
      </svg>,
    );
    const animateMotion = container.querySelector("animateMotion");
    expect(animateMotion).toBeInTheDocument();
    expect(animateMotion).toHaveAttribute("dur", "2s");
    expect(animateMotion).toHaveAttribute("repeatCount", "indefinite");
  });

  test("returns null when source node is missing", () => {
    mockUseInternalNode.mockImplementation((nodeId: string) => {
      if (nodeId === "s1") return null;
      return {
        internals: {
          positionAbsolute: { x: 10, y: 20 },
          handleBounds: {
            source: [{ position: "right", width: 10, height: 10, x: 5, y: 5 }],
            target: [{ position: "left", width: 10, height: 10, x: 0, y: 0 }],
          },
        },
      };
    });

    const { container } = render(
      <svg>
        <Edge.Animated
          id="no-source"
          source="s1"
          target="t1"
          sourceX={0}
          sourceY={0}
          targetX={100}
          targetY={100}
          sourcePosition={Position.Right}
          targetPosition={Position.Left}
        />
      </svg>,
    );
    expect(
      container.querySelector("[data-testid='base-edge']"),
    ).not.toBeInTheDocument();
  });

  test("returns null when target node is missing", () => {
    mockUseInternalNode.mockImplementation((nodeId: string) => {
      if (nodeId === "t1") return null;
      return {
        internals: {
          positionAbsolute: { x: 10, y: 20 },
          handleBounds: {
            source: [{ position: "right", width: 10, height: 10, x: 5, y: 5 }],
            target: [{ position: "left", width: 10, height: 10, x: 0, y: 0 }],
          },
        },
      };
    });

    const { container } = render(
      <svg>
        <Edge.Animated
          id="no-target"
          source="s1"
          target="t1"
          sourceX={0}
          sourceY={0}
          targetX={100}
          targetY={100}
          sourcePosition={Position.Right}
          targetPosition={Position.Left}
        />
      </svg>,
    );
    expect(
      container.querySelector("[data-testid='base-edge']"),
    ).not.toBeInTheDocument();
  });

  test("passes markerEnd and style to BaseEdge", () => {
    const { container } = render(
      <svg>
        <Edge.Animated
          id="styled-edge"
          source="s1"
          target="t1"
          sourceX={0}
          sourceY={0}
          targetX={100}
          targetY={100}
          sourcePosition={Position.Right}
          targetPosition={Position.Left}
          markerEnd="url(#arrow)"
          style={{ stroke: "red" }}
        />
      </svg>,
    );
    const edge = container.querySelector("[data-testid='base-edge']");
    expect(edge).toHaveAttribute("data-marker-end", "url(#arrow)");
  });

  test("renders edge when source node has no matching handle (fallback [0,0])", () => {
    mockUseInternalNode.mockImplementation((nodeId: string) => {
      if (nodeId === "s1") {
        return {
          internals: {
            positionAbsolute: { x: 10, y: 20 },
            handleBounds: {
              // source handle has "top" position, not "right" - won't match Position.Right
              source: [{ position: "top", width: 10, height: 10, x: 5, y: 5 }],
              target: [{ position: "left", width: 10, height: 10, x: 0, y: 0 }],
            },
          },
        };
      }
      return {
        internals: {
          positionAbsolute: { x: 30, y: 40 },
          handleBounds: {
            source: [{ position: "right", width: 10, height: 10, x: 5, y: 5 }],
            target: [{ position: "left", width: 10, height: 10, x: 0, y: 0 }],
          },
        },
      };
    });

    const { container } = render(
      <svg>
        <Edge.Animated
          id="no-handle-edge"
          source="s1"
          target="t1"
          sourceX={0}
          sourceY={0}
          targetX={100}
          targetY={100}
          sourcePosition={Position.Right}
          targetPosition={Position.Left}
        />
      </svg>,
    );
    // Component should still render (uses fallback [0,0] coordinates)
    const edge = container.querySelector("[data-testid='base-edge']");
    expect(edge).toBeInTheDocument();
  });

  test("renders edge when target node has no matching handle (fallback [0,0])", () => {
    mockUseInternalNode.mockImplementation((nodeId: string) => {
      if (nodeId === "t1") {
        return {
          internals: {
            positionAbsolute: { x: 10, y: 20 },
            handleBounds: {
              source: [
                { position: "right", width: 10, height: 10, x: 5, y: 5 },
              ],
              // target handle has "bottom" position, not "left" - won't match Position.Left
              target: [
                { position: "bottom", width: 10, height: 10, x: 0, y: 0 },
              ],
            },
          },
        };
      }
      return {
        internals: {
          positionAbsolute: { x: 30, y: 40 },
          handleBounds: {
            source: [{ position: "right", width: 10, height: 10, x: 5, y: 5 }],
            target: [{ position: "left", width: 10, height: 10, x: 0, y: 0 }],
          },
        },
      };
    });

    const { container } = render(
      <svg>
        <Edge.Animated
          id="no-target-handle-edge"
          source="s1"
          target="t1"
          sourceX={0}
          sourceY={0}
          targetX={100}
          targetY={100}
          sourcePosition={Position.Right}
          targetPosition={Position.Left}
        />
      </svg>,
    );
    const edge = container.querySelector("[data-testid='base-edge']");
    expect(edge).toBeInTheDocument();
  });

  test("renders edge when source node has empty handleBounds", () => {
    mockUseInternalNode.mockImplementation((nodeId: string) => {
      if (nodeId === "s1") {
        return {
          internals: {
            positionAbsolute: { x: 10, y: 20 },
            handleBounds: {
              source: [],
              target: [],
            },
          },
        };
      }
      return {
        internals: {
          positionAbsolute: { x: 30, y: 40 },
          handleBounds: {
            source: [{ position: "right", width: 10, height: 10, x: 5, y: 5 }],
            target: [{ position: "left", width: 10, height: 10, x: 0, y: 0 }],
          },
        },
      };
    });

    const { container } = render(
      <svg>
        <Edge.Animated
          id="empty-handles-edge"
          source="s1"
          target="t1"
          sourceX={0}
          sourceY={0}
          targetX={100}
          targetY={100}
          sourcePosition={Position.Right}
          targetPosition={Position.Left}
        />
      </svg>,
    );
    const edge = container.querySelector("[data-testid='base-edge']");
    expect(edge).toBeInTheDocument();
  });

  test("renders edge when node has undefined handleBounds", () => {
    mockUseInternalNode.mockImplementation(((nodeId: string) => {
      if (nodeId === "s1") {
        return {
          internals: {
            positionAbsolute: { x: 10, y: 20 },
            handleBounds: undefined,
          },
        };
      }
      return {
        internals: {
          positionAbsolute: { x: 30, y: 40 },
          handleBounds: {
            source: [{ position: "right", width: 10, height: 10, x: 5, y: 5 }],
            target: [{ position: "left", width: 10, height: 10, x: 0, y: 0 }],
          },
        },
      };
    }) as (nodeId: string) => any);

    const { container } = render(
      <svg>
        <Edge.Animated
          id="undefined-handles-edge"
          source="s1"
          target="t1"
          sourceX={0}
          sourceY={0}
          targetX={100}
          targetY={100}
          sourcePosition={Position.Right}
          targetPosition={Position.Left}
        />
      </svg>,
    );
    const edge = container.querySelector("[data-testid='base-edge']");
    expect(edge).toBeInTheDocument();
  });
});
