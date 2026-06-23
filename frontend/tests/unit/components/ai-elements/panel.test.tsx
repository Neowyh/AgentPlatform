import { render, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@xyflow/react", () => ({
  Panel: ({ children, className, ...props }: any) => (
    <div data-testid="panel" className={className} {...props}>
      {children}
    </div>
  ),
}));

import { Panel } from "@/components/ai-elements/panel";

afterEach(() => {
  cleanup();
});

describe("Panel", () => {
  test("renders Panel component", () => {
    const { getByTestId } = render(<Panel />);
    expect(getByTestId("panel")).toBeInTheDocument();
  });

  test("renders children", () => {
    const { getByText } = render(
      <Panel>
        <span>Panel content</span>
      </Panel>,
    );
    expect(getByText("Panel content")).toBeInTheDocument();
  });

  test("applies className", () => {
    const { getByTestId } = render(<Panel className="custom-panel" />);
    const panel = getByTestId("panel");
    expect(panel.className).toContain("custom-panel");
  });
});
