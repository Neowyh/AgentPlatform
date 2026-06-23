import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/components/ai-elements/queue", () => ({
  QueueList: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <div data-testid="queue-list" className={className}>
      {children}
    </div>
  ),
  QueueItem: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="queue-item">{children}</div>
  ),
  QueueItemIndicator: ({
    className,
    completed,
  }: {
    className?: string;
    completed?: boolean;
  }) => (
    <div
      data-testid="queue-item-indicator"
      data-completed={completed}
      className={className}
    />
  ),
  QueueItemContent: ({
    children,
    className,
    completed,
  }: {
    children: React.ReactNode;
    className?: string;
    completed?: boolean;
  }) => (
    <div
      data-testid="queue-item-content"
      data-completed={completed}
      className={className}
    >
      {children}
    </div>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let TodoList: typeof import("@/components/workspace/todo-list").TodoList;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/workspace/todo-list");
  TodoList = mod.TodoList;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("TodoList", () => {
  const sampleTodos = [
    { content: "Task 1", status: "pending" as const },
    { content: "Task 2", status: "in_progress" as const },
    { content: "Task 3", status: "completed" as const },
  ];

  test("renders the todo list header", () => {
    render(<TodoList todos={sampleTodos} />);
    expect(screen.getByText("To-dos")).toBeInTheDocument();
  });

  test("renders all todo items", () => {
    render(<TodoList todos={sampleTodos} />);
    expect(screen.getByText("Task 1")).toBeInTheDocument();
    expect(screen.getByText("Task 2")).toBeInTheDocument();
    expect(screen.getByText("Task 3")).toBeInTheDocument();
  });

  test("starts collapsed by default", () => {
    render(<TodoList todos={sampleTodos} />);
    // The main content should have h-0 class when collapsed
    const main = document.querySelector("main");
    expect(main?.className).toContain("h-0");
  });

  test("toggles expansion on header click", async () => {
    const user = userEvent.setup();
    render(<TodoList todos={sampleTodos} />);

    // Click header to expand
    const header = screen.getByText("To-dos").closest("header")!;
    await user.click(header);

    // Should now be expanded (h-28)
    const main = document.querySelector("main");
    expect(main?.className).toContain("h-28");
  });

  test("toggles back to collapsed on second click", async () => {
    const user = userEvent.setup();
    render(<TodoList todos={sampleTodos} />);

    const header = screen.getByText("To-dos").closest("header")!;

    // Expand
    await user.click(header);
    expect(document.querySelector("main")?.className).toContain("h-28");

    // Collapse
    await user.click(header);
    expect(document.querySelector("main")?.className).toContain("h-0");
  });

  test("supports controlled collapsed prop", () => {
    const { rerender } = render(
      <TodoList todos={sampleTodos} collapsed={true} />,
    );
    expect(document.querySelector("main")?.className).toContain("h-0");

    rerender(<TodoList todos={sampleTodos} collapsed={false} />);
    expect(document.querySelector("main")?.className).toContain("h-28");
  });

  test("calls onToggle when controlled and header clicked", async () => {
    const onToggle = vi.fn();
    const user = userEvent.setup();
    render(
      <TodoList todos={sampleTodos} collapsed={true} onToggle={onToggle} />,
    );

    const header = screen.getByText("To-dos").closest("header")!;
    await user.click(header);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  test("applies hidden class when hidden prop is true", () => {
    const { container } = render(<TodoList todos={sampleTodos} hidden />);
    const wrapper = container.firstElementChild;
    expect(wrapper?.getAttribute("class")).toContain("opacity-0");
    expect(wrapper?.getAttribute("class")).toContain("pointer-events-none");
  });

  test("applies custom className", () => {
    const { container } = render(
      <TodoList todos={sampleTodos} className="my-class" />,
    );
    const wrapper = container.firstElementChild;
    expect(wrapper?.getAttribute("class")).toContain("my-class");
  });

  test("marks in_progress items with primary styling", () => {
    render(<TodoList todos={sampleTodos} />);
    const indicators = screen.getAllByTestId("queue-item-indicator");
    // second item is in_progress (index 1)
    expect(indicators[1]!.getAttribute("class")).toContain("bg-primary/70");
  });

  test("marks completed items correctly", () => {
    render(<TodoList todos={sampleTodos} />);
    const indicators = screen.getAllByTestId("queue-item-indicator");
    expect(indicators[0]!.getAttribute("data-completed")).toBe("false");
    expect(indicators[2]!.getAttribute("data-completed")).toBe("true");
  });

  test("renders empty list", () => {
    render(<TodoList todos={[]} />);
    expect(screen.getByText("To-dos")).toBeInTheDocument();
    expect(screen.queryAllByTestId("queue-item")).toHaveLength(0);
  });

  test("does not call onToggle in uncontrolled mode", async () => {
    const onToggle = vi.fn();
    const user = userEvent.setup();
    render(<TodoList todos={sampleTodos} onToggle={onToggle} />);

    const header = screen.getByText("To-dos").closest("header")!;
    await user.click(header);
    // In uncontrolled mode, onToggle is not called
    expect(onToggle).not.toHaveBeenCalled();
  });
});
