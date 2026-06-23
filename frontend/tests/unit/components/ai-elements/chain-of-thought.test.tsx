import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrainIcon, SearchIcon } from "lucide-react";
import { afterEach, describe, expect, test, vi } from "vitest";

import {
  ChainOfThought,
  ChainOfThoughtHeader,
  ChainOfThoughtStep,
  ChainOfThoughtSearchResults,
  ChainOfThoughtSearchResult,
  ChainOfThoughtContent,
  ChainOfThoughtImage,
} from "@/components/ai-elements/chain-of-thought";

afterEach(() => {
  cleanup();
});

describe("ChainOfThought", () => {
  test("renders children with data-testid", () => {
    render(
      <ChainOfThought data-testid="cot-test">
        <div>Child content</div>
      </ChainOfThought>,
    );
    expect(screen.getByTestId("cot-test")).toBeInTheDocument();
    expect(screen.getByText("Child content")).toBeInTheDocument();
  });

  test("has default data-testid of chain-of-thought", () => {
    render(
      <ChainOfThought>
        <div>Content</div>
      </ChainOfThought>,
    );
    expect(screen.getByTestId("chain-of-thought")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <ChainOfThought className="custom-cot" data-testid="cot-test">
        <div>Content</div>
      </ChainOfThought>,
    );
    expect(screen.getByTestId("cot-test")).toHaveClass("custom-cot");
  });

  test("applies not-prose class by default", () => {
    render(
      <ChainOfThought data-testid="cot-test">
        <div>Content</div>
      </ChainOfThought>,
    );
    expect(screen.getByTestId("cot-test")).toHaveClass("not-prose");
  });

  test("spreads additional div props", () => {
    render(
      <ChainOfThought aria-label="thinking" data-testid="cot-test">
        <div>Content</div>
      </ChainOfThought>,
    );
    expect(screen.getByTestId("cot-test")).toHaveAttribute(
      "aria-label",
      "thinking",
    );
  });
});

describe("ChainOfThoughtHeader", () => {
  test("renders default text 'Chain of Thought'", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtHeader />
      </ChainOfThought>,
    );
    expect(screen.getByText("Chain of Thought")).toBeInTheDocument();
  });

  test("renders custom children text", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtHeader>Thinking steps</ChainOfThoughtHeader>
      </ChainOfThought>,
    );
    expect(screen.getByText("Thinking steps")).toBeInTheDocument();
  });

  test("has data-testid chain-of-thought-trigger", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtHeader />
      </ChainOfThought>,
    );
    expect(screen.getByTestId("chain-of-thought-trigger")).toBeInTheDocument();
  });

  test("renders default brain icon", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtHeader />
      </ChainOfThought>,
    );
    // The trigger should contain an SVG (brain icon)
    const trigger = screen.getByTestId("chain-of-thought-trigger");
    expect(trigger.querySelector("svg")).toBeInTheDocument();
  });

  test("renders custom icon when provided", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtHeader icon={<SearchIcon data-testid="custom-icon" />} />
      </ChainOfThought>,
    );
    expect(screen.getByTestId("custom-icon")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtHeader className="custom-header" />
      </ChainOfThought>,
    );
    expect(screen.getByTestId("chain-of-thought-trigger")).toHaveClass(
      "custom-header",
    );
  });

  test("toggles open state on click", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();

    render(
      <ChainOfThought onOpenChange={onOpenChange}>
        <ChainOfThoughtHeader />
        <ChainOfThoughtContent>
          <div>Hidden content</div>
        </ChainOfThoughtContent>
      </ChainOfThought>,
    );

    const trigger = screen.getByTestId("chain-of-thought-trigger");
    await user.click(trigger);
    expect(onOpenChange).toHaveBeenCalledWith(true);
  });

  test("renders chevron icon that rotates when open", async () => {
    const user = userEvent.setup();

    render(
      <ChainOfThought>
        <ChainOfThoughtHeader />
        <ChainOfThoughtContent>
          <div>Content</div>
        </ChainOfThoughtContent>
      </ChainOfThought>,
    );

    const trigger = screen.getByTestId("chain-of-thought-trigger");
    // Initially closed - chevron should have rotate-0
    const chevron = trigger.querySelector("svg:last-child");
    expect(chevron).toBeInTheDocument();

    // Click to open
    await user.click(trigger);
    // Chevron should now have rotate-180 class
    expect(chevron?.getAttribute("class") || "").toContain("rotate-180");
  });
});

describe("ChainOfThoughtStep", () => {
  test("renders with label", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtStep label="Step 1" />
      </ChainOfThought>,
    );
    expect(screen.getByText("Step 1")).toBeInTheDocument();
  });

  test("has data-testid chain-of-thought-step", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtStep label="Step 1" />
      </ChainOfThought>,
    );
    expect(screen.getByTestId("chain-of-thought-step")).toBeInTheDocument();
  });

  test("renders with description when provided", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtStep
          label="Searching"
          description="Looking for relevant documents"
        />
      </ChainOfThought>,
    );
    expect(screen.getByText("Searching")).toBeInTheDocument();
    expect(
      screen.getByText("Looking for relevant documents"),
    ).toBeInTheDocument();
  });

  test("does not render description when not provided", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtStep label="No desc step" />
      </ChainOfThought>,
    );
    expect(screen.getByText("No desc step")).toBeInTheDocument();
    // Should not have a description div
    const step = screen.getByTestId("chain-of-thought-step");
    const descDiv = step.querySelector(".text-muted-foreground.text-xs");
    expect(descDiv).not.toBeInTheDocument();
  });

  test("renders default dot icon", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtStep label="Default icon" />
      </ChainOfThought>,
    );
    const step = screen.getByTestId("chain-of-thought-step");
    expect(step.querySelector("svg")).toBeInTheDocument();
  });

  test("renders custom LucideIcon component", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtStep icon={SearchIcon} label="Searching" />
      </ChainOfThought>,
    );
    const step = screen.getByTestId("chain-of-thought-step");
    expect(step.querySelector("svg")).toBeInTheDocument();
  });

  test("renders custom ReactElement icon", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtStep
          icon={<BrainIcon data-testid="custom-brain" />}
          label="Thinking"
        />
      </ChainOfThought>,
    );
    expect(screen.getByTestId("custom-brain")).toBeInTheDocument();
  });

  test("applies complete status style", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtStep label="Done" status="complete" />
      </ChainOfThought>,
    );
    const step = screen.getByTestId("chain-of-thought-step");
    expect(step.className).toContain("text-muted-foreground");
  });

  test("applies active status style", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtStep label="Active" status="active" />
      </ChainOfThought>,
    );
    const step = screen.getByTestId("chain-of-thought-step");
    expect(step.className).toContain("text-foreground");
  });

  test("applies pending status style", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtStep label="Pending" status="pending" />
      </ChainOfThought>,
    );
    const step = screen.getByTestId("chain-of-thought-step");
    expect(step.className).toContain("text-muted-foreground/50");
  });

  test("defaults to complete status", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtStep label="Default status" />
      </ChainOfThought>,
    );
    const step = screen.getByTestId("chain-of-thought-step");
    expect(step.className).toContain("text-muted-foreground");
  });

  test("renders children content", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtStep label="With children">
          <div>Step child content</div>
        </ChainOfThoughtStep>
      </ChainOfThought>,
    );
    expect(screen.getByText("Step child content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtStep className="custom-step" label="Styled" />
      </ChainOfThought>,
    );
    expect(screen.getByTestId("chain-of-thought-step")).toHaveClass(
      "custom-step",
    );
  });
});

describe("ChainOfThoughtSearchResults", () => {
  test("renders children", () => {
    render(
      <ChainOfThoughtSearchResults>
        <span>Result 1</span>
        <span>Result 2</span>
      </ChainOfThoughtSearchResults>,
    );
    expect(screen.getByText("Result 1")).toBeInTheDocument();
    expect(screen.getByText("Result 2")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <ChainOfThoughtSearchResults
        className="custom-results"
        data-testid="results-test"
      >
        <span>Result</span>
      </ChainOfThoughtSearchResults>,
    );
    expect(screen.getByTestId("results-test")).toHaveClass("custom-results");
  });

  test("applies flex-wrap layout classes", () => {
    render(
      <ChainOfThoughtSearchResults data-testid="results-test">
        <span>Result</span>
      </ChainOfThoughtSearchResults>,
    );
    const el = screen.getByTestId("results-test");
    expect(el.className).toContain("flex");
    expect(el.className).toContain("flex-wrap");
  });
});

describe("ChainOfThoughtSearchResult", () => {
  test("renders children text", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtSearchResult>Search term</ChainOfThoughtSearchResult>
      </ChainOfThought>,
    );
    expect(screen.getByText("Search term")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtSearchResult
          className="custom-result"
          data-testid="result-test"
        >
          Term
        </ChainOfThoughtSearchResult>
      </ChainOfThought>,
    );
    expect(screen.getByTestId("result-test")).toHaveClass("custom-result");
  });

  test("renders as a badge with secondary variant", () => {
    render(
      <ChainOfThought>
        <ChainOfThoughtSearchResult>Badge content</ChainOfThoughtSearchResult>
      </ChainOfThought>,
    );
    const badge = screen.getByText("Badge content");
    expect(badge.className).toContain("bg-secondary");
  });
});

describe("ChainOfThoughtContent", () => {
  test("renders children when open", () => {
    render(
      <ChainOfThought defaultOpen>
        <ChainOfThoughtContent>
          <div>Expanded content</div>
        </ChainOfThoughtContent>
      </ChainOfThought>,
    );
    expect(screen.getByText("Expanded content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <ChainOfThought defaultOpen>
        <ChainOfThoughtContent
          className="custom-content"
          data-testid="content-test"
        >
          <div>Content</div>
        </ChainOfThoughtContent>
      </ChainOfThought>,
    );
    expect(screen.getByTestId("content-test")).toHaveClass("custom-content");
  });
});

describe("ChainOfThoughtImage", () => {
  test("renders children in a container", () => {
    render(
      <ChainOfThoughtImage>
        <img src="test.jpg" alt="Test" />
      </ChainOfThoughtImage>,
    );
    expect(screen.getByAltText("Test")).toBeInTheDocument();
  });

  test("renders caption when provided", () => {
    render(
      <ChainOfThoughtImage caption="Image caption">
        <img src="test.jpg" alt="Test" />
      </ChainOfThoughtImage>,
    );
    expect(screen.getByText("Image caption")).toBeInTheDocument();
  });

  test("does not render caption when not provided", () => {
    render(
      <ChainOfThoughtImage>
        <img src="test.jpg" alt="Test" />
      </ChainOfThoughtImage>,
    );
    expect(screen.queryByText(/caption/)).not.toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <ChainOfThoughtImage className="custom-image" data-testid="image-test">
        <img src="test.jpg" alt="Test" />
      </ChainOfThoughtImage>,
    );
    expect(screen.getByTestId("image-test")).toHaveClass("custom-image");
  });

  test("spreads additional props", () => {
    render(
      <ChainOfThoughtImage aria-label="thought image" data-testid="image-test">
        <img src="test.jpg" alt="Test" />
      </ChainOfThoughtImage>,
    );
    expect(screen.getByTestId("image-test")).toHaveAttribute(
      "aria-label",
      "thought image",
    );
  });
});

describe("ChainOfThought composition", () => {
  test("renders full chain of thought with all sub-components", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();

    render(
      <ChainOfThought defaultOpen onOpenChange={onOpenChange}>
        <ChainOfThoughtHeader>Research steps</ChainOfThoughtHeader>
        <ChainOfThoughtContent>
          <ChainOfThoughtStep
            label="Searching"
            description="Looking for information"
            status="complete"
          />
          <ChainOfThoughtStep label="Analyzing" status="active" />
          <ChainOfThoughtStep label="Writing" status="pending" />
          <ChainOfThoughtSearchResults>
            <ChainOfThoughtSearchResult>Result 1</ChainOfThoughtSearchResult>
            <ChainOfThoughtSearchResult>Result 2</ChainOfThoughtSearchResult>
          </ChainOfThoughtSearchResults>
          <ChainOfThoughtImage caption="Analysis chart">
            <img src="chart.png" alt="Chart" />
          </ChainOfThoughtImage>
        </ChainOfThoughtContent>
      </ChainOfThought>,
    );

    expect(screen.getByText("Research steps")).toBeInTheDocument();
    expect(screen.getByText("Searching")).toBeInTheDocument();
    expect(screen.getByText("Looking for information")).toBeInTheDocument();
    expect(screen.getByText("Analyzing")).toBeInTheDocument();
    expect(screen.getByText("Writing")).toBeInTheDocument();
    expect(screen.getByText("Result 1")).toBeInTheDocument();
    expect(screen.getByText("Result 2")).toBeInTheDocument();
    expect(screen.getByText("Analysis chart")).toBeInTheDocument();
    expect(screen.getByAltText("Chart")).toBeInTheDocument();

    // Toggle closed
    await user.click(screen.getByTestId("chain-of-thought-trigger"));
    expect(onOpenChange).toHaveBeenCalled();
  });

  test("controlled open state", () => {
    const { rerender } = render(
      <ChainOfThought open={false}>
        <ChainOfThoughtHeader />
        <ChainOfThoughtContent>
          <div>Controlled content</div>
        </ChainOfThoughtContent>
      </ChainOfThought>,
    );

    // Content should be hidden when open=false
    rerender(
      <ChainOfThought open={true}>
        <ChainOfThoughtHeader />
        <ChainOfThoughtContent>
          <div>Controlled content</div>
        </ChainOfThoughtContent>
      </ChainOfThought>,
    );
    expect(screen.getByText("Controlled content")).toBeInTheDocument();
  });

  test("context error when using sub-components outside ChainOfThought", () => {
    // Suppress console.error for expected error
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => {
      render(<ChainOfThoughtHeader />);
    }).toThrow("ChainOfThought components must be used within ChainOfThought");

    consoleSpy.mockRestore();
  });

  test("context error when using ChainOfThoughtContent outside ChainOfThought", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => {
      render(
        <ChainOfThoughtContent>
          <div>Orphan content</div>
        </ChainOfThoughtContent>,
      );
    }).toThrow("ChainOfThought components must be used within ChainOfThought");

    consoleSpy.mockRestore();
  });

  test("ChainOfThoughtStep renders standalone without context", () => {
    // ChainOfThoughtStep is a standalone component that does not require context
    render(<ChainOfThoughtStep label="Standalone step" />);
    expect(screen.getByText("Standalone step")).toBeInTheDocument();
  });

  test("renders multiple steps with different statuses", () => {
    render(
      <ChainOfThought defaultOpen>
        <ChainOfThoughtContent>
          <ChainOfThoughtStep label="Step 1" status="complete" />
          <ChainOfThoughtStep label="Step 2" status="active" />
          <ChainOfThoughtStep label="Step 3" status="pending" />
        </ChainOfThoughtContent>
      </ChainOfThought>,
    );

    const steps = screen.getAllByTestId("chain-of-thought-step");
    expect(steps).toHaveLength(3);
    expect(steps[0]).toHaveClass("text-muted-foreground");
    expect(steps[1]).toHaveClass("text-foreground");
    expect(steps[2]).toHaveClass("text-muted-foreground/50");
  });

  test("renders multiple search results", () => {
    render(
      <ChainOfThought defaultOpen>
        <ChainOfThoughtContent>
          <ChainOfThoughtSearchResults>
            <ChainOfThoughtSearchResult>Result A</ChainOfThoughtSearchResult>
            <ChainOfThoughtSearchResult>Result B</ChainOfThoughtSearchResult>
            <ChainOfThoughtSearchResult>Result C</ChainOfThoughtSearchResult>
          </ChainOfThoughtSearchResults>
        </ChainOfThoughtContent>
      </ChainOfThought>,
    );

    expect(screen.getByText("Result A")).toBeInTheDocument();
    expect(screen.getByText("Result B")).toBeInTheDocument();
    expect(screen.getByText("Result C")).toBeInTheDocument();
  });

  test("step with both description and children", () => {
    render(
      <ChainOfThought defaultOpen>
        <ChainOfThoughtContent>
          <ChainOfThoughtStep label="Complex step" description="Detailed info">
            <div>Extra child content</div>
          </ChainOfThoughtStep>
        </ChainOfThoughtContent>
      </ChainOfThought>,
    );

    expect(screen.getByText("Complex step")).toBeInTheDocument();
    expect(screen.getByText("Detailed info")).toBeInTheDocument();
    expect(screen.getByText("Extra child content")).toBeInTheDocument();
  });

  test("image component renders caption as paragraph", () => {
    render(
      <ChainOfThoughtImage caption="Test caption">
        <img src="test.png" alt="Test" />
      </ChainOfThoughtImage>,
    );

    const caption = screen.getByText("Test caption");
    expect(caption.tagName).toBe("P");
    expect(caption).toHaveClass("text-muted-foreground");
    expect(caption).toHaveClass("text-xs");
  });

  test("controlled open=false hides content", () => {
    render(
      <ChainOfThought open={false}>
        <ChainOfThoughtHeader />
        <ChainOfThoughtContent>
          <div>Hidden when closed</div>
        </ChainOfThoughtContent>
      </ChainOfThought>,
    );

    // Content is rendered in DOM but hidden via collapsible
    expect(screen.getByTestId("chain-of-thought")).toBeInTheDocument();
  });

  test("defaultOpen=true shows content initially", () => {
    render(
      <ChainOfThought defaultOpen>
        <ChainOfThoughtHeader />
        <ChainOfThoughtContent>
          <div>Visible on mount</div>
        </ChainOfThoughtContent>
      </ChainOfThought>,
    );

    expect(screen.getByText("Visible on mount")).toBeInTheDocument();
  });
});
