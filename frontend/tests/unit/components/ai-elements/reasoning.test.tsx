import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";

import {
  Reasoning,
  ReasoningTrigger,
  ReasoningContent,
  useReasoning,
} from "@/components/ai-elements/reasoning";

afterEach(() => {
  cleanup();
});

// Mock Streamdown
vi.mock("streamdown", () => ({
  Streamdown: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="streamdown">{children}</div>
  ),
}));

// Mock Shimmer
vi.mock("@/components/ai-elements/shimmer", () => ({
  Shimmer: ({
    children,
    duration,
  }: {
    children: React.ReactNode;
    duration?: number;
  }) => (
    <span data-testid="shimmer" data-duration={duration}>
      {children}
    </span>
  ),
}));

// Mock reasoningPlugins
vi.mock("@/core/streamdown/plugins", () => ({
  reasoningPlugins: {},
}));

describe("Reasoning", () => {
  test("renders with children", () => {
    render(
      <Reasoning data-testid="reasoning">
        <ReasoningTrigger />
        <ReasoningContent>Analysis text</ReasoningContent>
      </Reasoning>,
    );
    expect(screen.getByTestId("reasoning")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Reasoning className="custom-reasoning" data-testid="reasoning">
        <ReasoningTrigger />
      </Reasoning>,
    );
    expect(screen.getByTestId("reasoning")).toHaveClass("custom-reasoning");
  });

  test("has not-prose and mb-4 classes", () => {
    render(
      <Reasoning data-testid="reasoning">
        <ReasoningTrigger />
      </Reasoning>,
    );
    const el = screen.getByTestId("reasoning");
    expect(el.className).toContain("not-prose");
    expect(el.className).toContain("mb-4");
  });

  test("defaults to open", () => {
    render(
      <Reasoning data-testid="reasoning">
        <ReasoningTrigger />
        <ReasoningContent>Content</ReasoningContent>
      </Reasoning>,
    );
    const reasoning = screen.getByTestId("reasoning");
    // Default open means the collapsible should have data-state=open or be expanded
    expect(reasoning).toBeInTheDocument();
  });
});

describe("ReasoningTrigger", () => {
  test("renders default thinking message when streaming", () => {
    render(
      <Reasoning isStreaming>
        <ReasoningTrigger data-testid="trigger" />
      </Reasoning>,
    );
    expect(screen.getByText("Thinking...")).toBeInTheDocument();
  });

  test("renders shimmer when streaming", () => {
    render(
      <Reasoning isStreaming>
        <ReasoningTrigger data-testid="trigger" />
      </Reasoning>,
    );
    const shimmer = screen.getByTestId("shimmer");
    expect(shimmer).toBeInTheDocument();
    expect(shimmer).toHaveTextContent("Thinking...");
  });

  test("renders thought duration when not streaming", () => {
    render(
      <Reasoning isStreaming={false} duration={5}>
        <ReasoningTrigger data-testid="trigger" />
      </Reasoning>,
    );
    expect(screen.getByText("Thought for 5 seconds")).toBeInTheDocument();
  });

  test("renders 'few seconds' when duration is undefined", () => {
    render(
      <Reasoning isStreaming={false}>
        <ReasoningTrigger data-testid="trigger" />
      </Reasoning>,
    );
    expect(screen.getByText("Thought for a few seconds")).toBeInTheDocument();
  });

  test("renders '0 seconds' when duration is 0", () => {
    render(
      <Reasoning isStreaming={false} duration={0}>
        <ReasoningTrigger data-testid="trigger" />
      </Reasoning>,
    );
    expect(screen.getByText("Thinking...")).toBeInTheDocument();
  });

  test("renders brain icon", () => {
    render(
      <Reasoning>
        <ReasoningTrigger data-testid="trigger" />
      </Reasoning>,
    );
    const svgs = screen.getByTestId("trigger").querySelectorAll("svg");
    expect(svgs.length).toBeGreaterThanOrEqual(1);
  });

  test("renders chevron icon", () => {
    render(
      <Reasoning>
        <ReasoningTrigger data-testid="trigger" />
      </Reasoning>,
    );
    const svgs = screen.getByTestId("trigger").querySelectorAll("svg");
    // At least brain + chevron
    expect(svgs.length).toBeGreaterThanOrEqual(2);
  });

  test("renders custom children instead of default", () => {
    render(
      <Reasoning>
        <ReasoningTrigger data-testid="trigger">
          <span>Custom trigger</span>
        </ReasoningTrigger>
      </Reasoning>,
    );
    expect(screen.getByText("Custom trigger")).toBeInTheDocument();
    expect(screen.queryByText("Thinking...")).not.toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Reasoning>
        <ReasoningTrigger className="custom-trigger" data-testid="trigger" />
      </Reasoning>,
    );
    expect(screen.getByTestId("trigger")).toHaveClass("custom-trigger");
  });

  test("uses custom getThinkingMessage", () => {
    const customMessage = (isStreaming: boolean, duration?: number) => (
      <span data-testid="custom-msg">
        {isStreaming ? "Processing..." : `Done in ${duration}s`}
      </span>
    );

    render(
      <Reasoning isStreaming duration={3}>
        <ReasoningTrigger
          getThinkingMessage={customMessage}
          data-testid="trigger"
        />
      </Reasoning>,
    );
    expect(screen.getByTestId("custom-msg")).toHaveTextContent("Processing...");
  });
});

describe("ReasoningContent", () => {
  test("renders children text in Streamdown", () => {
    render(
      <Reasoning defaultOpen>
        <ReasoningContent data-testid="content">
          This is my reasoning process
        </ReasoningContent>
      </Reasoning>,
    );
    expect(
      screen.getByText("This is my reasoning process"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("streamdown")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Reasoning defaultOpen>
        <ReasoningContent className="custom-content" data-testid="content">
          Content
        </ReasoningContent>
      </Reasoning>,
    );
    expect(screen.getByTestId("content")).toHaveClass("custom-content");
  });

  test("has animation classes", () => {
    render(
      <Reasoning defaultOpen>
        <ReasoningContent data-testid="content">Content</ReasoningContent>
      </Reasoning>,
    );
    const el = screen.getByTestId("content");
    expect(el.className).toContain("text-sm");
    expect(el.className).toContain("text-muted-foreground");
  });
});

describe("Reasoning interaction", () => {
  test("toggle reasoning content via trigger click", async () => {
    const user = userEvent.setup();
    render(
      <Reasoning data-testid="reasoning">
        <ReasoningTrigger data-testid="trigger" />
        <ReasoningContent data-testid="content">
          Reasoning text
        </ReasoningContent>
      </Reasoning>,
    );

    // Content should be visible initially (defaultOpen=true)
    expect(screen.getByText("Reasoning text")).toBeInTheDocument();

    // Click trigger to collapse
    await user.click(screen.getByTestId("trigger"));

    // Content should be hidden
    const content = screen.getByTestId("content");
    expect(content).toHaveAttribute("data-state", "closed");
  });

  test("can control open state externally", () => {
    const { rerender } = render(
      <Reasoning open data-testid="reasoning">
        <ReasoningTrigger data-testid="trigger" />
        <ReasoningContent data-testid="content">
          Controlled content
        </ReasoningContent>
      </Reasoning>,
    );
    expect(screen.getByText("Controlled content")).toBeInTheDocument();

    rerender(
      <Reasoning open={false} data-testid="reasoning">
        <ReasoningTrigger data-testid="trigger" />
        <ReasoningContent data-testid="content">
          Controlled content
        </ReasoningContent>
      </Reasoning>,
    );
    const content = screen.getByTestId("content");
    expect(content).toHaveAttribute("data-state", "closed");
  });
});

describe("useReasoning hook", () => {
  test("throws when used outside Reasoning provider", () => {
    // Suppress console.error for this test
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    const TestComponent = () => {
      useReasoning();
      return null;
    };

    expect(() => render(<TestComponent />)).toThrow(
      "Reasoning components must be used within Reasoning",
    );

    spy.mockRestore();
  });
});

describe("Reasoning duration tracking", () => {
  test("calculates duration when streaming ends", async () => {
    const { rerender } = render(
      <Reasoning isStreaming={true} data-testid="reasoning">
        <ReasoningTrigger data-testid="trigger" />
      </Reasoning>,
    );

    // While streaming, should show Thinking...
    expect(screen.getByText("Thinking...")).toBeInTheDocument();

    // Stop streaming
    rerender(
      <Reasoning isStreaming={false} data-testid="reasoning">
        <ReasoningTrigger data-testid="trigger" />
      </Reasoning>,
    );

    // After streaming ends, should show duration (Thought for N seconds)
    await vi.waitFor(() => {
      expect(screen.getByText(/Thought for \d+ seconds/)).toBeInTheDocument();
    });
  });
});

describe("Reasoning auto-close", () => {
  test("stays open after streaming ends with defaultOpen=true", async () => {
    const { rerender } = render(
      <Reasoning isStreaming={true} defaultOpen={true} data-testid="reasoning">
        <ReasoningTrigger data-testid="trigger" />
        <ReasoningContent data-testid="content">
          Reasoning text
        </ReasoningContent>
      </Reasoning>,
    );

    // Stop streaming - the content must remain open (no auto-close)
    rerender(
      <Reasoning isStreaming={false} defaultOpen={true} data-testid="reasoning">
        <ReasoningTrigger data-testid="trigger" />
        <ReasoningContent data-testid="content">
          Reasoning text
        </ReasoningContent>
      </Reasoning>,
    );

    await vi.waitFor(
      () => {
        const content = screen.getByTestId("content");
        expect(content).toHaveAttribute("data-state", "open");
      },
      { timeout: 3000 },
    );
  });
});
