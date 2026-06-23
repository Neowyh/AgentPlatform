import { render, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { Connection as _Connection } from "@/components/ai-elements/connection";

// Cast to accept the subset of props the tests actually pass,
// since ConnectionLineComponentProps requires additional internal props.
const Connection = _Connection as React.ComponentType<Record<string, unknown>>;

afterEach(() => {
  cleanup();
});

describe("Connection", () => {
  test("renders an SVG g element", () => {
    const { container } = render(
      <svg>
        <Connection
          id="test-edge"
          fromX={0}
          fromY={0}
          toX={100}
          toY={100}
          sourceX={0}
          sourceY={0}
          targetX={100}
          targetY={100}
          sourcePosition="right"
          targetPosition="left"
          source="node1"
          target="node2"
          sourceHandleId={null}
          targetHandleId={null}
          data={undefined}
          style={{}}
          markerStart=""
          markerEnd=""
          isFocusable={false}
          selected={false}
          animated={false}
        />
      </svg>,
    );
    const g = container.querySelector("g");
    expect(g).toBeInTheDocument();
  });

  test("renders a path element with bezier curve", () => {
    const { container } = render(
      <svg>
        <Connection
          id="test-edge"
          fromX={10}
          fromY={20}
          toX={200}
          toY={300}
          sourceX={10}
          sourceY={20}
          targetX={200}
          targetY={300}
          sourcePosition="right"
          targetPosition="left"
          source="node1"
          target="node2"
          sourceHandleId={null}
          targetHandleId={null}
          data={undefined}
          style={{}}
          markerStart=""
          markerEnd=""
          isFocusable={false}
          selected={false}
          animated={false}
        />
      </svg>,
    );
    const path = container.querySelector("path");
    expect(path).toBeInTheDocument();
    expect(path).toHaveAttribute("fill", "none");
    expect(path).toHaveAttribute("stroke", "var(--color-ring)");
    expect(path?.getAttribute("d")).toContain("M10,20");
  });

  test("renders a circle at the target point", () => {
    const { container } = render(
      <svg>
        <Connection
          id="test-edge"
          fromX={0}
          fromY={0}
          toX={150}
          toY={250}
          sourceX={0}
          sourceY={0}
          targetX={150}
          targetY={250}
          sourcePosition="right"
          targetPosition="left"
          source="node1"
          target="node2"
          sourceHandleId={null}
          targetHandleId={null}
          data={undefined}
          style={{}}
          markerStart=""
          markerEnd=""
          isFocusable={false}
          selected={false}
          animated={false}
        />
      </svg>,
    );
    const circle = container.querySelector("circle");
    expect(circle).toBeInTheDocument();
    expect(circle).toHaveAttribute("cx", "150");
    expect(circle).toHaveAttribute("cy", "250");
    expect(circle).toHaveAttribute("r", "3");
  });

  test("path has animated class", () => {
    const { container } = render(
      <svg>
        <Connection
          id="test-edge"
          fromX={0}
          fromY={0}
          toX={100}
          toY={100}
          sourceX={0}
          sourceY={0}
          targetX={100}
          targetY={100}
          sourcePosition="right"
          targetPosition="left"
          source="node1"
          target="node2"
          sourceHandleId={null}
          targetHandleId={null}
          data={undefined}
          style={{}}
          markerStart=""
          markerEnd=""
          isFocusable={false}
          selected={false}
          animated={false}
        />
      </svg>,
    );
    const path = container.querySelector("path");
    expect(path?.getAttribute("class")).toContain("animated");
  });

  test("circle has white fill and ring stroke", () => {
    const { container } = render(
      <svg>
        <Connection
          id="test-edge"
          fromX={0}
          fromY={0}
          toX={100}
          toY={100}
          sourceX={0}
          sourceY={0}
          targetX={100}
          targetY={100}
          sourcePosition="right"
          targetPosition="left"
          source="node1"
          target="node2"
          sourceHandleId={null}
          targetHandleId={null}
          data={undefined}
          style={{}}
          markerStart=""
          markerEnd=""
          isFocusable={false}
          selected={false}
          animated={false}
        />
      </svg>,
    );
    const circle = container.querySelector("circle");
    expect(circle).toHaveAttribute("fill", "#fff");
    expect(circle).toHaveAttribute("stroke", "var(--color-ring)");
  });
});
