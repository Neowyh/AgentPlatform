import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { StreamingIndicator } from "@/components/workspace/streaming-indicator";

describe("StreamingIndicator", () => {
  test("renders three dot elements", () => {
    render(<StreamingIndicator />);
    // The component renders a div containing 3 animated dot divs
    const container = document.querySelector(".flex");
    expect(container).toBeInTheDocument();
    const dots = container?.querySelectorAll(".rounded-full");
    expect(dots).toHaveLength(3);
  });

  test("applies default size classes (normal)", () => {
    const { container } = render(<StreamingIndicator />);
    const dots = container.querySelectorAll(".rounded-full");
    dots.forEach((dot) => {
      expect(dot.className).toContain("w-2");
      expect(dot.className).toContain("h-2");
      expect(dot.className).toContain("mx-1");
    });
  });

  test("applies small size classes when size='sm'", () => {
    const { container } = render(<StreamingIndicator size="sm" />);
    const dots = container.querySelectorAll(".rounded-full");
    dots.forEach((dot) => {
      expect(dot.className).toContain("w-1.5");
      expect(dot.className).toContain("h-1.5");
      expect(dot.className).toContain("mx-0.5");
    });
  });

  test("applies custom className", () => {
    render(<StreamingIndicator className="my-custom" />);
    const wrapper = document.querySelector(".my-custom");
    expect(wrapper).toBeInTheDocument();
  });

  test("has animation classes on dots", () => {
    const { container } = render(<StreamingIndicator />);
    const dots = container.querySelectorAll(".rounded-full");
    dots.forEach((dot) => {
      expect(dot.className).toContain("animate-bouncing");
    });
  });

  test("has staggered animation delays", () => {
    const { container } = render(<StreamingIndicator />);
    const dots = Array.from(container.querySelectorAll(".rounded-full"));
    // First dot has no delay
    expect(dots[0]?.className).not.toContain("animation-delay");
    // Second dot has 0.2s delay
    expect(dots[1]?.className).toContain("[animation-delay:0.2s]");
    // Third dot has 0.4s delay
    expect(dots[2]?.className).toContain("[animation-delay:0.4s]");
  });
});
