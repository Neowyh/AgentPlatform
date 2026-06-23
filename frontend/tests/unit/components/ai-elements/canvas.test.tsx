import { render, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@xyflow/react", () => ({
  ReactFlow: ({ children, ...props }: any) => (
    <div data-testid="react-flow" data-props={JSON.stringify(props)}>
      {children}
    </div>
  ),
  Background: () => <div data-testid="background" />,
}));

import { Canvas } from "@/components/ai-elements/canvas";

afterEach(() => {
  cleanup();
});

describe("Canvas", () => {
  test("renders ReactFlow component", () => {
    const { getByTestId } = render(<Canvas />);
    expect(getByTestId("react-flow")).toBeInTheDocument();
  });

  test("renders Background inside ReactFlow", () => {
    const { getByTestId } = render(<Canvas />);
    expect(getByTestId("background")).toBeInTheDocument();
  });

  test("renders children inside ReactFlow", () => {
    const { getByText } = render(
      <Canvas>
        <div>Child content</div>
      </Canvas>,
    );
    expect(getByText("Child content")).toBeInTheDocument();
  });

  test("applies default ReactFlow props", () => {
    const { getByTestId } = render(<Canvas />);
    const flow = getByTestId("react-flow");
    const props = JSON.parse(flow.getAttribute("data-props") || "{}");
    expect(props.deleteKeyCode).toEqual(["Backspace", "Delete"]);
    expect(props.fitView).toBe(true);
    expect(props.panOnDrag).toBe(false);
    expect(props.panOnScroll).toBe(true);
  });
});
