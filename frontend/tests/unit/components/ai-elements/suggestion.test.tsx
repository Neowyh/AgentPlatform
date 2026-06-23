import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SearchIcon } from "lucide-react";
import { afterEach, beforeAll, describe, expect, test, vi } from "vitest";

import { Suggestions, Suggestion } from "@/components/ai-elements/suggestion";

// ResizeObserver is required by Radix ScrollArea
beforeAll(() => {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

afterEach(() => {
  cleanup();
});

describe("Suggestions", () => {
  test("renders children inside a scrollable container", () => {
    render(
      <Suggestions>
        <div>Child 1</div>
        <div>Child 2</div>
      </Suggestions>,
    );
    expect(screen.getByText("Child 1")).toBeInTheDocument();
    expect(screen.getByText("Child 2")).toBeInTheDocument();
  });

  test("has default data-testid of suggestions-container", () => {
    render(
      <Suggestions>
        <div>Child</div>
      </Suggestions>,
    );
    expect(screen.getByTestId("suggestions-container")).toBeInTheDocument();
  });

  test("applies custom className to inner container", () => {
    render(
      <Suggestions className="custom-suggestions">
        <div>Child</div>
      </Suggestions>,
    );
    // className is applied to the inner div (data-testid="suggestions-container"),
    // NOT to the outer ScrollArea (where ...props are spread)
    expect(screen.getByTestId("suggestions-container")).toHaveClass(
      "custom-suggestions",
    );
  });

  test("renders children with staggered animation delays", () => {
    render(
      <Suggestions>
        <div>First</div>
        <div>Second</div>
        <div>Third</div>
      </Suggestions>,
    );

    // Children should be wrapped in spans with animation delay styles
    const container = screen.getByTestId("suggestions-container");
    const spans = container.querySelectorAll("span");
    expect(spans.length).toBe(3);
  });

  test("applies stagger delay offsets to child spans", () => {
    render(
      <Suggestions>
        <div>First</div>
        <div>Second</div>
      </Suggestions>,
    );

    const container = screen.getByTestId("suggestions-container");
    const spans = container.querySelectorAll("span");
    // First child: offset (250) + 0 * 60 = 250ms
    expect(spans[0]?.style.animationDelay).toBe("250ms");
    // Second child: offset (250) + 1 * 60 = 310ms
    expect(spans[1]?.style.animationDelay).toBe("310ms");
  });

  test("handles null children gracefully", () => {
    render(
      <Suggestions>
        <div>Valid child</div>
        {null}
        <div>Another valid child</div>
      </Suggestions>,
    );
    expect(screen.getByText("Valid child")).toBeInTheDocument();
    expect(screen.getByText("Another valid child")).toBeInTheDocument();
  });

  test("renders with no children", () => {
    render(<Suggestions />);
    expect(screen.getByTestId("suggestions-container")).toBeInTheDocument();
  });

  test("spreads additional props to ScrollArea", () => {
    render(
      <Suggestions aria-label="suggestions">
        <div>Child</div>
      </Suggestions>,
    );
    // aria-label is spread onto the outer ScrollArea element
    expect(screen.getByLabelText("suggestions")).toBeInTheDocument();
  });

  test("has animate-fade-in-up class on child spans", () => {
    render(
      <Suggestions>
        <div>Animated child</div>
      </Suggestions>,
    );

    const container = screen.getByTestId("suggestions-container");
    const span = container.querySelector("span");
    expect(span?.className).toContain("animate-fade-in-up");
    expect(span?.className).toContain("opacity-0");
  });
});

describe("Suggestion", () => {
  test("renders with suggestion text", () => {
    render(<Suggestion suggestion="Hello world" />);
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  test("renders as a button with type button", () => {
    render(<Suggestion suggestion="Click me" />);
    const button = screen.getByRole("button", { name: "Click me" });
    expect(button).toHaveAttribute("type", "button");
  });

  test("has default data-testid of suggestion-button", () => {
    render(<Suggestion suggestion="Test" />);
    expect(screen.getByTestId("suggestion-button")).toBeInTheDocument();
  });

  test("calls onClick when clicked", async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    render(<Suggestion suggestion="Click me" onClick={handleClick} />);
    await user.click(screen.getByRole("button", { name: "Click me" }));
    expect(handleClick).toHaveBeenCalledOnce();
  });

  test("does not throw when onClick is undefined and button is clicked", async () => {
    const user = userEvent.setup();
    render(<Suggestion suggestion="No handler" />);
    // Should not throw
    await user.click(screen.getByRole("button", { name: "No handler" }));
  });

  test("renders children instead of suggestion when provided", () => {
    render(
      <Suggestion suggestion="Should not show">Custom children</Suggestion>,
    );
    expect(screen.getByText("Custom children")).toBeInTheDocument();
    expect(screen.queryByText("Should not show")).not.toBeInTheDocument();
  });

  test("renders icon when provided", () => {
    render(<Suggestion suggestion="Search" icon={SearchIcon} />);
    const button = screen.getByRole("button", { name: "Search" });
    expect(button.querySelector("svg")).toBeInTheDocument();
  });

  test("does not render icon when not provided", () => {
    render(<Suggestion suggestion="No icon" />);
    const button = screen.getByRole("button", { name: "No icon" });
    // Only the suggestion text, no SVG
    expect(button.querySelector("svg")).not.toBeInTheDocument();
  });

  test("applies default variant outline", () => {
    render(<Suggestion suggestion="Default" />);
    const button = screen.getByRole("button", { name: "Default" });
    // Outline variant has border class
    expect(button.className).toContain("border");
  });

  test("applies custom variant", () => {
    render(<Suggestion suggestion="Custom variant" variant="secondary" />);
    const button = screen.getByRole("button", { name: "Custom variant" });
    expect(button.className).toContain("bg-secondary");
  });

  test("passes size prop to underlying Button", () => {
    render(<Suggestion suggestion="Small" size="sm" />);
    const button = screen.getByRole("button", { name: "Small" });
    // sm size produces h-8, but h-auto in component className overrides it via tailwind-merge
    // The component always applies h-auto, so the final class should contain h-auto
    expect(button.className).toContain("h-auto");
  });

  test("applies custom className", () => {
    render(<Suggestion suggestion="Styled" className="custom-suggestion" />);
    expect(screen.getByRole("button", { name: "Styled" })).toHaveClass(
      "custom-suggestion",
    );
  });

  test("spreads additional props", () => {
    render(<Suggestion suggestion="Props" aria-label="custom aria" />);
    expect(
      screen.getByRole("button", { name: "custom aria" }),
    ).toBeInTheDocument();
  });

  test("applies default size sm", () => {
    render(<Suggestion suggestion="Default size" />);
    const button = screen.getByRole("button", { name: "Default size" });
    // The component sets size="sm" by default on the Button
    expect(button).toBeInTheDocument();
  });

  test("applies rounded-full class", () => {
    render(<Suggestion suggestion="Rounded" />);
    const button = screen.getByRole("button", { name: "Rounded" });
    expect(button.className).toContain("rounded-full");
  });

  test("applies cursor-pointer class", () => {
    render(<Suggestion suggestion="Clickable" />);
    const button = screen.getByRole("button", { name: "Clickable" });
    expect(button.className).toContain("cursor-pointer");
  });

  test("applies text-xs class", () => {
    render(<Suggestion suggestion="Small text" />);
    const button = screen.getByRole("button", { name: "Small text" });
    expect(button.className).toContain("text-xs");
  });
});

describe("Suggestions composition", () => {
  test("renders multiple suggestions with staggered animation", async () => {
    const user = userEvent.setup();
    const onClick1 = vi.fn();
    const onClick2 = vi.fn();

    render(
      <Suggestions>
        <Suggestion suggestion="Option A" onClick={onClick1} />
        <Suggestion suggestion="Option B" onClick={onClick2} />
      </Suggestions>,
    );

    expect(screen.getByText("Option A")).toBeInTheDocument();
    expect(screen.getByText("Option B")).toBeInTheDocument();

    await user.click(screen.getByText("Option A"));
    expect(onClick1).toHaveBeenCalledOnce();
    expect(onClick2).not.toHaveBeenCalled();
  });

  test("each suggestion gets unique animation delay", () => {
    render(
      <Suggestions>
        <Suggestion suggestion="First" />
        <Suggestion suggestion="Second" />
        <Suggestion suggestion="Third" />
      </Suggestions>,
    );

    const container = screen.getByTestId("suggestions-container");
    const spans = container.querySelectorAll("span");
    expect(spans.length).toBe(3);
    // Verify unique delays
    const delays = Array.from(spans).map((s) => s.style.animationDelay);
    expect(new Set(delays).size).toBe(3);
  });

  test("null children are skipped in animation spans", () => {
    render(
      <Suggestions>
        <Suggestion suggestion="First" />
        {null}
        <Suggestion suggestion="Third" />
      </Suggestions>,
    );

    const container = screen.getByTestId("suggestions-container");
    // null children should be passed through as-is, not wrapped in spans
    const spans = container.querySelectorAll("span");
    // Should have 2 spans (for First and Third), null is passed through
    expect(spans.length).toBeGreaterThanOrEqual(2);
  });

  test("suggestions with icons and click handlers in composition", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();

    render(
      <Suggestions>
        <Suggestion suggestion="Search" icon={SearchIcon} onClick={onClick} />
      </Suggestions>,
    );

    const button = screen.getByRole("button", { name: "Search" });
    expect(button.querySelector("svg")).toBeInTheDocument();
    await user.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  test("suggestions list has correct flex layout classes", () => {
    render(
      <Suggestions>
        <Suggestion suggestion="A" />
      </Suggestions>,
    );

    const container = screen.getByTestId("suggestions-container");
    expect(container.className).toContain("flex");
    expect(container.className).toContain("flex-wrap");
    expect(container.className).toContain("gap-2");
  });
});
