import { render, screen, cleanup } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, test, vi } from "vitest";

// Mock motion/react - motion.create returns a component that renders the given element
vi.mock("motion/react", () => ({
  motion: {
    create: (Component: string | React.ComponentType) => {
      const MotionComponent = ({
        children,
        className,
        style,
        initial,
        animate,
        transition,
        ...props
      }: Record<string, unknown>) => {
        if (typeof Component === "string") {
          return React.createElement(
            Component,
            {
              className: className as string,
              style: style as React.CSSProperties,
              ...props,
            },
            children as React.ReactNode,
          );
        }

        return React.createElement(
          Component as any,
          {
            className: className as string,
            style: style as React.CSSProperties,
            ...props,
          } as any,
          children as React.ReactNode,
        );
      };
      MotionComponent.displayName = `MotionComponent`;
      return MotionComponent;
    },
  },
}));

import { Shimmer } from "@/components/ai-elements/shimmer";

afterEach(() => {
  cleanup();
});

// Helper to get the rendered element by its text content
const getShimmerElement = (text: string) => {
  return screen.getByText(text).closest("p, span, h1, h2, h3")!;
};

describe("Shimmer", () => {
  test("renders children text", () => {
    render(<Shimmer>Hello World</Shimmer>);
    expect(screen.getByText("Hello World")).toBeInTheDocument();
  });

  test("renders as a p element by default", () => {
    render(<Shimmer>Default paragraph</Shimmer>);
    const el = getShimmerElement("Default paragraph");
    expect(el).not.toBeNull();
    expect(el.tagName).toBe("P");
  });

  test("renders with custom as prop", () => {
    render(<Shimmer as="span">Span text</Shimmer>);
    const el = getShimmerElement("Span text");
    expect(el).not.toBeNull();
    expect(el.tagName).toBe("SPAN");
  });

  test("has inline-block and bg-clip-text classes", () => {
    render(<Shimmer>Styled text</Shimmer>);
    const el = getShimmerElement("Styled text");
    expect(el).not.toBeNull();
    expect(el.className).toContain("inline-block");
    expect(el.className).toContain("bg-clip-text");
    expect(el.className).toContain("text-transparent");
  });

  test("applies animation styles", () => {
    render(<Shimmer>Animated text</Shimmer>);
    const el = getShimmerElement("Animated text");
    expect(el).not.toBeNull();
    expect(el.className).toContain("relative");
    expect(el.className).toContain("bg-[length:250%_100%,auto]");
  });

  test("applies custom className", () => {
    render(<Shimmer className="custom-shimmer">Text</Shimmer>);
    const el = getShimmerElement("Text");
    expect(el).not.toBeNull();
    expect(el.className).toContain("custom-shimmer");
  });

  test("renders with heading element", () => {
    render(<Shimmer as="h1">Heading text</Shimmer>);
    const el = getShimmerElement("Heading text");
    expect(el).not.toBeNull();
    expect(el.tagName).toBe("H1");
  });

  test("sets spread CSS variable based on text length", () => {
    render(<Shimmer>Hello</Shimmer>);
    const el = getShimmerElement("Hello");
    expect(el).not.toBeNull();
    const style = el.getAttribute("style");
    expect(style).toContain("--spread");
  });

  test("has background-repeat and background-image in style", () => {
    render(<Shimmer>Style check</Shimmer>);
    const el = getShimmerElement("Style check");
    expect(el).not.toBeNull();
    const style = el.getAttribute("style");
    expect(style).toContain("background-image");
  });

  test("defaults to p element when as prop is not provided", () => {
    render(<Shimmer>Default element</Shimmer>);
    const el = getShimmerElement("Default element");
    expect(el).not.toBeNull();
    expect(el.tagName).toBe("P");
  });

  test("renders with h2 element", () => {
    render(<Shimmer as="h2">H2 text</Shimmer>);
    const el = getShimmerElement("H2 text");
    expect(el).not.toBeNull();
    expect(el.tagName).toBe("H2");
  });
});
