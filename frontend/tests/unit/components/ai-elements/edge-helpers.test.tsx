import { render, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

// Mock setup
vi.mock("@xyflow/react", () => ({
  BaseEdge: ({
    id,
    path,
    className,
    style,
    markerEnd,
  }: {
    id: string;
    path: string;
    className?: string;
    style?: React.CSSProperties;
    markerEnd?: string;
  }) => (
    <svg>
      <path
        data-testid="base-edge"
        data-id={id}
        data-path={path}
        data-classname={className}
        data-marker-end={markerEnd}
        style={style}
      />
    </svg>
  ),
  getBezierPath: vi.fn(() => ["M 0 0 L 100 100"]),
  getSimpleBezierPath: vi.fn(() => ["M 0 0 L 50 50"]),
  Position: { Left: "left", Right: "right", Top: "top", Bottom: "bottom" },
  useInternalNode: vi.fn(() => ({
    internals: {
      positionAbsolute: { x: 0, y: 0 },
      handleBounds: {
        source: [
          {
            position: "right",
            x: 0,
            y: 0,
            width: 10,
            height: 10,
          },
        ],
        target: [
          {
            position: "left",
            x: 0,
            y: 0,
            width: 10,
            height: 10,
          },
        ],
      },
    },
  })),
}));

import { getBezierPath, getSimpleBezierPath } from "@xyflow/react";

import { Edge } from "@/components/ai-elements/edge";
import { Position } from "@xyflow/react";

const EDGE_SELECTOR = `[data-testid="base-edge"]`;

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Edge.Temporary", () => {
  test("renders BaseEdge", () => {
    const { container } = render(
      <svg>
        <Edge.Temporary
          id="temp-edge"
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
    const edge = container.querySelector(EDGE_SELECTOR);
    expect(edge).toBeTruthy();
    expect(edge?.getAttribute("data-id")).toBe("temp-edge");
  });

  test("uses getSimpleBezierPath for path computation", () => {
    render(
      <svg>
        <Edge.Temporary
          id="temp-edge"
          source="s1"
          target="t1"
          sourceX={10}
          sourceY={20}
          targetX={30}
          targetY={40}
          sourcePosition={Position.Right}
          targetPosition={Position.Left}
        />
      </svg>,
    );
    expect(getSimpleBezierPath).toHaveBeenCalled();
    const edge = document.querySelector(EDGE_SELECTOR);
    expect(edge?.getAttribute("data-path")).toBe("M 0 0 L 50 50");
  });

  test("applies stroke-ring className", () => {
    const { container } = render(
      <svg>
        <Edge.Temporary
          id="temp-edge"
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
    const edge = container.querySelector(EDGE_SELECTOR);
    expect(edge?.getAttribute("data-classname")).toContain("stroke-ring");
  });

  test("applies dashed stroke style", () => {
    const { container } = render(
      <svg>
        <Edge.Temporary
          id="temp-edge"
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
    const edge = container.querySelector(EDGE_SELECTOR);
    const style = edge?.getAttribute("style");
    expect(style).toContain("stroke-dasharray");
  });
});

describe("Edge.Animated", () => {
  test("renders BaseEdge and animated circle when source/target nodes exist", () => {
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
    const edge = container.querySelector(EDGE_SELECTOR);
    expect(edge).toBeTruthy();
    expect(edge?.getAttribute("data-id")).toBe("anim-edge");
    const circle = container.querySelector("circle");
    expect(circle).toBeTruthy();
  });

  test("uses getBezierPath for path computation", () => {
    render(
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
    expect(getBezierPath).toHaveBeenCalled();
    const edge = document.querySelector(EDGE_SELECTOR);
    expect(edge?.getAttribute("data-path")).toBe("M 0 0 L 100 100");
  });

  test("renders animateMotion element inside circle", () => {
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
    const animate = container.querySelector("animateMotion");
    expect(animate).toBeTruthy();
    expect(animate?.getAttribute("dur")).toBe("2s");
    expect(animate?.getAttribute("repeatCount")).toBe("indefinite");
  });

  test("passes markerEnd to BaseEdge", () => {
    render(
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
          markerEnd="url(#arrow)"
        />
      </svg>,
    );
    const edge = document.querySelector(EDGE_SELECTOR);
    expect(edge?.getAttribute("data-marker-end")).toBe("url(#arrow)");
  });

  test("returns null when source node is not found", async () => {
    const { useInternalNode } = await import("@xyflow/react");
    vi.mocked(useInternalNode).mockImplementation((id: string) => {
      if (id === "s1") return null;
      return {
        internals: {
          positionAbsolute: { x: 0, y: 0 },
          handleBounds: {
            source: [
              {
                position: "right",
                x: 0,
                y: 0,
                width: 10,
                height: 10,
              },
            ],
            target: [
              {
                position: "left",
                x: 0,
                y: 0,
                width: 10,
                height: 10,
              },
            ],
          },
        },
      } as any;
    });

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
    expect(container.querySelector(EDGE_SELECTOR)).toBeNull();
    vi.mocked(useInternalNode).mockImplementation(
      () =>
        ({
          internals: {
            positionAbsolute: { x: 0, y: 0 },
            handleBounds: {
              source: [
                {
                  position: "right",
                  x: 0,
                  y: 0,
                  width: 10,
                  height: 10,
                },
              ],
              target: [
                {
                  position: "left",
                  x: 0,
                  y: 0,
                  width: 10,
                  height: 10,
                },
              ],
            },
          },
        }) as any,
    );
  });

  test("returns null when target node is not found", async () => {
    const { useInternalNode } = await import("@xyflow/react");
    vi.mocked(useInternalNode).mockImplementation((id: string) => {
      if (id === "t1") return null;
      return {
        internals: {
          positionAbsolute: { x: 0, y: 0 },
          handleBounds: {
            source: [
              {
                position: "right",
                x: 0,
                y: 0,
                width: 10,
                height: 10,
              },
            ],
            target: [
              {
                position: "left",
                x: 0,
                y: 0,
                width: 10,
                height: 10,
              },
            ],
          },
        },
      } as any;
    });

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
    expect(container.querySelector(EDGE_SELECTOR)).toBeNull();
    vi.mocked(useInternalNode).mockImplementation(
      () =>
        ({
          internals: {
            positionAbsolute: { x: 0, y: 0 },
            handleBounds: {
              source: [
                {
                  position: "right",
                  x: 0,
                  y: 0,
                  width: 10,
                  height: 10,
                },
              ],
              target: [
                {
                  position: "left",
                  x: 0,
                  y: 0,
                  width: 10,
                  height: 10,
                },
              ],
            },
          },
        }) as any,
    );
  });

  test("returns null when both source and target nodes are not found", async () => {
    const { useInternalNode } = await import("@xyflow/react");
    vi.mocked(useInternalNode).mockReturnValue(null as any);

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
    expect(container.querySelector(EDGE_SELECTOR)).toBeNull();
    vi.mocked(useInternalNode).mockImplementation(
      () =>
        ({
          internals: {
            positionAbsolute: { x: 0, y: 0 },
            handleBounds: {
              source: [
                {
                  position: "right",
                  x: 0,
                  y: 0,
                  width: 10,
                  height: 10,
                },
              ],
              target: [
                {
                  position: "left",
                  x: 0,
                  y: 0,
                  width: 10,
                  height: 10,
                },
              ],
            },
          },
        }) as any,
    );
  });
});
