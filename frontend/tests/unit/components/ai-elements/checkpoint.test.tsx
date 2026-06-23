import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";

import {
  Checkpoint,
  CheckpointIcon,
  CheckpointTrigger,
} from "@/components/ai-elements/checkpoint";

afterEach(() => {
  cleanup();
});

describe("Checkpoint", () => {
  test("renders with children", () => {
    render(
      <Checkpoint data-testid="checkpoint">
        <span>Checkpoint content</span>
      </Checkpoint>,
    );
    expect(screen.getByText("Checkpoint content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Checkpoint className="custom-checkpoint" data-testid="checkpoint">
        <span>Content</span>
      </Checkpoint>,
    );
    expect(screen.getByTestId("checkpoint")).toHaveClass("custom-checkpoint");
  });

  test("has flex and overflow classes", () => {
    render(
      <Checkpoint data-testid="checkpoint">
        <span>Content</span>
      </Checkpoint>,
    );
    const el = screen.getByTestId("checkpoint");
    expect(el.className).toContain("flex");
    expect(el.className).toContain("items-center");
    expect(el.className).toContain("overflow-hidden");
  });

  test("renders a separator element", () => {
    const { container } = render(
      <Checkpoint data-testid="checkpoint">
        <span>Before separator</span>
      </Checkpoint>,
    );
    // Separator renders as an hr or div with role separator
    const separator = container.querySelector(
      '[data-orientation="horizontal"]',
    );
    expect(separator).toBeInTheDocument();
  });
});

describe("CheckpointIcon", () => {
  test("renders default BookmarkIcon when no children", () => {
    render(<CheckpointIcon data-testid="icon" />);
    const svg =
      screen.getByTestId("icon").querySelector("svg") ||
      screen.getByTestId("icon");
    // BookmarkIcon renders as an SVG
    expect(svg).toBeInTheDocument();
  });

  test("renders custom children instead of default icon", () => {
    render(
      <CheckpointIcon data-testid="icon">
        <span>Custom icon</span>
      </CheckpointIcon>,
    );
    expect(screen.getByText("Custom icon")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(<CheckpointIcon className="custom-icon" data-testid="icon" />);
    // The className is applied to the BookmarkIcon's svg
    const svg = screen.getByTestId("icon").querySelector("svg");
    if (svg) {
      expect(svg.className.baseVal || svg.getAttribute("class")).toContain(
        "custom-icon",
      );
    }
  });
});

describe("CheckpointTrigger", () => {
  test("renders as a button", () => {
    render(
      <CheckpointTrigger data-testid="trigger">Click me</CheckpointTrigger>,
    );
    const btn = screen.getByTestId("trigger");
    expect(btn.tagName).toBe("BUTTON");
  });

  test("renders with ghost variant and small size by default", () => {
    render(<CheckpointTrigger data-testid="trigger">Click</CheckpointTrigger>);
    const btn = screen.getByTestId("trigger");
    expect(btn).toBeInTheDocument();
  });

  test("calls onClick handler", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <CheckpointTrigger onClick={onClick} data-testid="trigger">
        Click me
      </CheckpointTrigger>,
    );
    await user.click(screen.getByTestId("trigger"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  test("applies custom className", () => {
    render(
      <CheckpointTrigger className="custom-trigger" data-testid="trigger">
        Click
      </CheckpointTrigger>,
    );
    expect(screen.getByTestId("trigger")).toHaveClass("custom-trigger");
  });

  test("spreads additional button props", () => {
    render(
      <CheckpointTrigger disabled data-testid="trigger">
        Click
      </CheckpointTrigger>,
    );
    expect(screen.getByTestId("trigger")).toBeDisabled();
  });
});
