import { render, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@xyflow/react", () => ({
  Controls: ({ children, className, ...props }: any) => (
    <div data-testid="controls" className={className} {...props}>
      {children}
    </div>
  ),
}));

import { Controls } from "@/components/ai-elements/controls";

afterEach(() => {
  cleanup();
});

describe("Controls", () => {
  test("renders Controls component", () => {
    const { getByTestId } = render(<Controls />);
    expect(getByTestId("controls")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    const { getByTestId } = render(<Controls className="custom-controls" />);
    const controls = getByTestId("controls");
    expect(controls.className).toContain("custom-controls");
  });
});
