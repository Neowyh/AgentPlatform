import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: {
      subtasks: {
        completed: "Completed",
        failed: "Failed",
        in_progress: "In progress",
      },
    },
    changeLocale: vi.fn(),
  }),
}));

vi.mock("@/core/rehype", () => ({
  useRehypeSplitWordsIntoSpans: () => [],
}));

vi.mock("@/core/messages/utils", () => ({
  hasToolCalls: () => false,
}));

vi.mock("@/core/streamdown", () => ({
  streamdownPluginsWithWordAnimation: {},
}));

vi.mock("@/core/tasks/context", () => {
  let mockTask: any = null;
  return {
    useSubtask: () => mockTask,
    __setMockTask: (task: any) => {
      mockTask = task;
    },
  };
});

vi.mock("@/core/tools/utils", () => ({
  explainLastToolCall: () => "Running tool...",
}));

vi.mock("streamdown", () => ({
  Streamdown: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="streamdown">{children}</div>
  ),
}));

vi.mock("@/components/ai-elements/chain-of-thought", () => ({
  ChainOfThought: ({ children, className }: any) => (
    <div data-testid="chain-of-thought" className={className}>
      {children}
    </div>
  ),
  ChainOfThoughtContent: ({ children, className }: any) => (
    <div data-testid="chain-of-thought-content" className={className}>
      {children}
    </div>
  ),
  ChainOfThoughtStep: ({ children, label, icon, className }: any) => (
    <div data-testid="chain-of-thought-step" className={className}>
      {label}
      {children}
    </div>
  ),
}));

vi.mock("@/components/ai-elements/shimmer", () => ({
  Shimmer: ({ children }: any) => <span data-testid="shimmer">{children}</span>,
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, variant, className }: any) => (
    <button
      onClick={onClick}
      data-variant={variant}
      className={className}
      data-testid="button"
    >
      {children}
    </button>
  ),
}));

vi.mock("@/components/ui/shine-border", () => ({
  ShineBorder: () => <div data-testid="shine-border" />,
}));

vi.mock("@/components/workspace/flip-display", () => ({
  FlipDisplay: ({ children, uniqueKey }: any) => (
    <div data-testid="flip-display" data-key={uniqueKey}>
      {children}
    </div>
  ),
}));

vi.mock("@/components/workspace/citations/citation-link", () => ({
  CitationLink: ({ children }: any) => (
    <a data-testid="citation-link">{children}</a>
  ),
}));

vi.mock("@/components/workspace/messages/markdown-content", () => ({
  MarkdownContent: ({ content }: any) => (
    <div data-testid="markdown-content">{content}</div>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let SubtaskCard: typeof import("@/components/workspace/messages/subtask-card").SubtaskCard;
let __setMockTask: (task: any) => void;

beforeEach(async () => {
  vi.clearAllMocks();
  const contextModule = await import("@/core/tasks/context");
  __setMockTask = (contextModule as any).__setMockTask;
  const mod = await import("@/components/workspace/messages/subtask-card");
  SubtaskCard = mod.SubtaskCard;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("SubtaskCard", () => {
  test("renders in_progress status with shimmer", () => {
    __setMockTask({
      id: "task-1",
      status: "in_progress",
      description: "Running analysis...",
      prompt: "Analyze the data",
    });
    render(<SubtaskCard taskId="task-1" isLoading={true} />);
    expect(screen.getByText("Running analysis...")).toBeInTheDocument();
    expect(screen.getByTestId("shimmer")).toBeInTheDocument();
  });

  test("renders completed status", () => {
    __setMockTask({
      id: "task-1",
      status: "completed",
      description: "Done task",
      result: "Task completed successfully",
    });
    render(<SubtaskCard taskId="task-1" isLoading={false} />);
    expect(screen.getByText("Done task")).toBeInTheDocument();
    // Completed appears in both the step label and the status text
    const completedElements = screen.getAllByText("Completed");
    expect(completedElements.length).toBeGreaterThanOrEqual(1);
  });

  test("renders failed status", () => {
    __setMockTask({
      id: "task-1",
      status: "failed",
      description: "Failed task",
      error: "Something went wrong",
    });
    render(<SubtaskCard taskId="task-1" isLoading={false} />);
    expect(screen.getByText("Failed task")).toBeInTheDocument();
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  test("toggles collapsed state on button click", () => {
    __setMockTask({
      id: "task-1",
      status: "completed",
      description: "Task",
      result: "Result",
    });
    render(<SubtaskCard taskId="task-1" isLoading={false} />);

    // Initially collapsed, content should be visible in chain-of-thought-content
    expect(screen.getByTestId("chain-of-thought-content")).toBeInTheDocument();

    // Click to toggle
    fireEvent.click(screen.getByTestId("button"));

    // Should still render (just toggled state)
    expect(screen.getByTestId("chain-of-thought")).toBeInTheDocument();
  });

  test("renders in_progress status icon", () => {
    __setMockTask({
      id: "task-1",
      status: "in_progress",
      description: "Working...",
    });
    render(<SubtaskCard taskId="task-1" isLoading={true} />);
    expect(screen.getByTestId("chain-of-thought")).toBeInTheDocument();
  });

  test("renders shine border for in_progress", () => {
    __setMockTask({
      id: "task-1",
      status: "in_progress",
      description: "Working...",
    });
    render(<SubtaskCard taskId="task-1" isLoading={true} />);
    expect(screen.getByTestId("shine-border")).toBeInTheDocument();
  });

  test("does not render shine border for completed", () => {
    __setMockTask({
      id: "task-1",
      status: "completed",
      description: "Done",
    });
    render(<SubtaskCard taskId="task-1" isLoading={false} />);
    expect(screen.queryByTestId("shine-border")).not.toBeInTheDocument();
  });

  test("renders prompt when available", () => {
    __setMockTask({
      id: "task-1",
      status: "completed",
      description: "Task",
      prompt: "Please analyze",
      result: "Done",
    });
    render(<SubtaskCard taskId="task-1" isLoading={false} />);
    expect(screen.getByText("Please analyze")).toBeInTheDocument();
  });

  test("renders result for completed task", () => {
    __setMockTask({
      id: "task-1",
      status: "completed",
      description: "Task",
      result: "Analysis complete",
    });
    render(<SubtaskCard taskId="task-1" isLoading={false} />);
    expect(screen.getByText("Analysis complete")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    __setMockTask({
      id: "task-1",
      status: "completed",
      description: "Task",
    });
    render(
      <SubtaskCard taskId="task-1" isLoading={false} className="custom-card" />,
    );
    expect(screen.getByTestId("chain-of-thought")).toHaveClass("custom-card");
  });
});
