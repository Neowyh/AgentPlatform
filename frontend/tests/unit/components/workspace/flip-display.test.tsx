import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { FlipDisplay } from "@/components/workspace/flip-display";

afterEach(() => {
  cleanup();
});

describe("FlipDisplay", () => {
  test("renders children content", () => {
    render(
      <FlipDisplay uniqueKey="key1">
        <span>Hello World</span>
      </FlipDisplay>,
    );
    expect(screen.getByText("Hello World")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    const { container } = render(
      <FlipDisplay uniqueKey="key1" className="my-class">
        <span>Content</span>
      </FlipDisplay>,
    );
    const wrapper = container.firstElementChild;
    expect(wrapper).toHaveAttribute(
      "class",
      expect.stringContaining("my-class"),
    );
  });

  test("always includes overflow-hidden class", () => {
    const { container } = render(
      <FlipDisplay uniqueKey="key1">
        <span>Content</span>
      </FlipDisplay>,
    );
    const wrapper = container.firstElementChild;
    expect(wrapper).toHaveAttribute(
      "class",
      expect.stringContaining("overflow-hidden"),
    );
  });

  test("renders with different uniqueKeys", () => {
    const { unmount } = render(
      <FlipDisplay uniqueKey="key1">
        <span>First</span>
      </FlipDisplay>,
    );
    expect(screen.getByText("First")).toBeInTheDocument();
    unmount();

    render(
      <FlipDisplay uniqueKey="key2">
        <span>Second</span>
      </FlipDisplay>,
    );
    expect(screen.getByText("Second")).toBeInTheDocument();
  });

  test("renders multiple children", () => {
    render(
      <FlipDisplay uniqueKey="key1">
        <span>Child 1</span>
        <span>Child 2</span>
      </FlipDisplay>,
    );
    expect(screen.getByText("Child 1")).toBeInTheDocument();
    expect(screen.getByText("Child 2")).toBeInTheDocument();
  });

  test("renders with string children", () => {
    render(<FlipDisplay uniqueKey="key1">Plain text</FlipDisplay>);
    expect(screen.getByText("Plain text")).toBeInTheDocument();
  });

  test("applies relative class by default", () => {
    const { container } = render(
      <FlipDisplay uniqueKey="key1">
        <span>Content</span>
      </FlipDisplay>,
    );
    const wrapper = container.firstElementChild;
    expect(wrapper).toHaveAttribute(
      "class",
      expect.stringContaining("relative"),
    );
  });

  test("merges custom className with default classes", () => {
    const { container } = render(
      <FlipDisplay uniqueKey="key1" className="custom-extra">
        <span>Content</span>
      </FlipDisplay>,
    );
    const wrapper = container.firstElementChild;
    const classes = wrapper?.getAttribute("class") ?? "";
    expect(classes).toContain("relative");
    expect(classes).toContain("overflow-hidden");
    expect(classes).toContain("custom-extra");
  });
});
