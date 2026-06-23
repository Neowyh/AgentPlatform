import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { Button } from "@/components/ui/button";

afterEach(() => {
  cleanup();
});

describe("Button", () => {
  test("renders with text content", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText("Click me")).toBeInTheDocument();
  });

  test("renders as a button element", () => {
    render(<Button data-testid="btn-el">Test</Button>);
    expect(screen.getByTestId("btn-el").tagName).toBe("BUTTON");
  });

  test("applies data-slot attribute", () => {
    render(<Button data-testid="btn-slot">Test</Button>);
    expect(screen.getByTestId("btn-slot")).toHaveAttribute(
      "data-slot",
      "button",
    );
  });

  test("applies default variant and size", () => {
    render(<Button data-testid="btn-default">Default</Button>);
    const btn = screen.getByTestId("btn-default");
    expect(btn).toHaveAttribute("data-variant", "default");
    expect(btn).toHaveAttribute("data-size", "default");
  });

  test("applies destructive variant", () => {
    render(
      <Button variant="destructive" data-testid="btn-destructive">
        Delete
      </Button>,
    );
    expect(screen.getByTestId("btn-destructive")).toHaveAttribute(
      "data-variant",
      "destructive",
    );
  });

  test("applies outline variant", () => {
    render(
      <Button variant="outline" data-testid="btn-outline">
        Outline
      </Button>,
    );
    expect(screen.getByTestId("btn-outline")).toHaveAttribute(
      "data-variant",
      "outline",
    );
  });

  test("applies secondary variant", () => {
    render(
      <Button variant="secondary" data-testid="btn-secondary">
        Secondary
      </Button>,
    );
    expect(screen.getByTestId("btn-secondary")).toHaveAttribute(
      "data-variant",
      "secondary",
    );
  });

  test("applies ghost variant", () => {
    render(
      <Button variant="ghost" data-testid="btn-ghost">
        Ghost
      </Button>,
    );
    expect(screen.getByTestId("btn-ghost")).toHaveAttribute(
      "data-variant",
      "ghost",
    );
  });

  test("applies link variant", () => {
    render(
      <Button variant="link" data-testid="btn-link">
        Link
      </Button>,
    );
    expect(screen.getByTestId("btn-link")).toHaveAttribute(
      "data-variant",
      "link",
    );
  });

  test("applies sm size", () => {
    render(
      <Button size="sm" data-testid="btn-sm">
        Small
      </Button>,
    );
    expect(screen.getByTestId("btn-sm")).toHaveAttribute("data-size", "sm");
  });

  test("applies lg size", () => {
    render(
      <Button size="lg" data-testid="btn-lg">
        Large
      </Button>,
    );
    expect(screen.getByTestId("btn-lg")).toHaveAttribute("data-size", "lg");
  });

  test("applies icon size", () => {
    render(
      <Button size="icon" data-testid="btn-icon">
        <span>+</span>
      </Button>,
    );
    expect(screen.getByTestId("btn-icon")).toHaveAttribute("data-size", "icon");
  });

  test("handles click events", () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click</Button>);
    fireEvent.click(screen.getByText("Click"));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  test("can be disabled", () => {
    const handleClick = vi.fn();
    render(
      <Button disabled onClick={handleClick}>
        Disabled
      </Button>,
    );
    const btn = screen.getByText("Disabled");
    expect(btn).toBeDisabled();
    fireEvent.click(btn);
    expect(handleClick).not.toHaveBeenCalled();
  });

  test("applies custom className", () => {
    render(
      <Button className="custom-btn" data-testid="btn-custom">
        Custom
      </Button>,
    );
    expect(screen.getByTestId("btn-custom")).toHaveClass("custom-btn");
  });

  test("forwards type attribute", () => {
    render(
      <Button type="submit" data-testid="btn-submit">
        Submit
      </Button>,
    );
    expect(screen.getByTestId("btn-submit")).toHaveAttribute("type", "submit");
  });

  test("renders as child element when asChild is true", () => {
    render(
      <Button asChild>
        {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- test uses raw <a> to verify asChild behavior */}
        <a href="/link" data-testid="btn-aschild">
          Link Button
        </a>
      </Button>,
    );
    const link = screen.getByTestId("btn-aschild");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "/link");
    expect(link).toHaveAttribute("data-slot", "button");
  });
});
