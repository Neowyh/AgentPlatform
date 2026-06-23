import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { Progress } from "@/components/ui/progress";

afterEach(() => {
  cleanup();
});

describe("Progress", () => {
  test("renders the progress bar", () => {
    render(<Progress value={50} data-testid="progress" />);
    expect(screen.getByTestId("progress")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<Progress value={50} data-testid="progress-slot" />);
    expect(screen.getByTestId("progress-slot")).toHaveAttribute(
      "data-slot",
      "progress",
    );
  });

  test("renders the indicator", () => {
    const { container } = render(<Progress value={50} />);
    expect(
      container.querySelector("[data-slot='progress-indicator']"),
    ).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Progress
        value={50}
        className="custom-prog"
        data-testid="progress-custom"
      />,
    );
    expect(screen.getByTestId("progress-custom")).toHaveClass("custom-prog");
  });

  test("has role progressbar", () => {
    render(<Progress value={75} data-testid="progress-role" />);
    expect(screen.getByTestId("progress-role")).toHaveAttribute(
      "role",
      "progressbar",
    );
  });

  test("renders the progress indicator with correct transform", () => {
    const { container } = render(<Progress value={60} />);
    const indicator = container.querySelector(
      "[data-slot='progress-indicator']",
    );
    expect(indicator).toBeInTheDocument();
    expect(indicator).toHaveStyle({ transform: "translateX(-40%)" });
  });
});
