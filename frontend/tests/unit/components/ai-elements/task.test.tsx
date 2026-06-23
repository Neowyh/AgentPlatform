import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test } from "vitest";

import {
  Task,
  TaskTrigger,
  TaskContent,
  TaskItem,
  TaskItemFile,
} from "@/components/ai-elements/task";

afterEach(() => {
  cleanup();
});

describe("Task", () => {
  test("renders with children", () => {
    render(
      <Task data-testid="task">
        <p>Task content</p>
      </Task>,
    );
    expect(screen.getByTestId("task")).toBeInTheDocument();
    expect(screen.getByText("Task content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Task className="custom-task" data-testid="task">
        <p>Content</p>
      </Task>,
    );
    expect(screen.getByTestId("task")).toHaveClass("custom-task");
  });

  test("defaults to open", () => {
    render(
      <Task data-testid="task">
        <TaskTrigger title="Search task" />
        <TaskContent>
          <p>Search results</p>
        </TaskContent>
      </Task>,
    );
    // Content should be visible when defaultOpen is true (default)
    expect(screen.getByText("Search results")).toBeInTheDocument();
  });
});

describe("TaskTrigger", () => {
  test("renders with title text", () => {
    render(
      <Task>
        <TaskTrigger title="Find files" data-testid="trigger" />
      </Task>,
    );
    expect(screen.getByText("Find files")).toBeInTheDocument();
  });

  test("renders search icon by default", () => {
    render(
      <Task>
        <TaskTrigger title="Search" data-testid="trigger" />
      </Task>,
    );
    const trigger = screen.getByTestId("trigger");
    const svg = trigger.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  test("renders chevron icon", () => {
    render(
      <Task>
        <TaskTrigger title="Toggle" data-testid="trigger" />
      </Task>,
    );
    // Should have at least 2 SVGs: SearchIcon and ChevronDownIcon
    const svgs = screen.getByTestId("trigger").querySelectorAll("svg");
    expect(svgs.length).toBeGreaterThanOrEqual(2);
  });

  test("renders custom children instead of default", () => {
    render(
      <Task>
        <TaskTrigger title="Hidden title" data-testid="trigger">
          <span>Custom trigger</span>
        </TaskTrigger>
      </Task>,
    );
    expect(screen.getByText("Custom trigger")).toBeInTheDocument();
    expect(screen.queryByText("Hidden title")).not.toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Task>
        <TaskTrigger
          title="Test"
          className="custom-trigger"
          data-testid="trigger"
        />
        ,
      </Task>,
    );
    expect(screen.getByTestId("trigger")).toHaveClass("custom-trigger");
  });
});

describe("TaskContent", () => {
  test("renders children", () => {
    render(
      <Task defaultOpen>
        <TaskContent data-testid="content">
          <p>Task details</p>
        </TaskContent>
      </Task>,
    );
    expect(screen.getByText("Task details")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Task defaultOpen>
        <TaskContent className="custom-content" data-testid="content">
          <p>Content</p>
        </TaskContent>
      </Task>,
    );
    expect(screen.getByTestId("content")).toHaveClass("custom-content");
  });

  test("has animation and outline classes", () => {
    render(
      <Task defaultOpen>
        <TaskContent data-testid="content">
          <p>Items</p>
        </TaskContent>
      </Task>,
    );
    const content = screen.getByTestId("content");
    expect(content.className).toContain("outline-none");
    expect(content.className).toContain("animate-in");
    expect(content.className).toContain("animate-out");
  });
});

describe("TaskItem", () => {
  test("renders with children", () => {
    render(
      <TaskItem data-testid="item">
        <span>Task item text</span>
      </TaskItem>,
    );
    expect(screen.getByText("Task item text")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <TaskItem className="custom-item" data-testid="item">
        <span>Item</span>
      </TaskItem>,
    );
    expect(screen.getByTestId("item")).toHaveClass("custom-item");
  });

  test("has text-sm class", () => {
    render(
      <TaskItem data-testid="item">
        <span>Item</span>
      </TaskItem>,
    );
    expect(screen.getByTestId("item").className).toContain("text-sm");
  });
});

describe("TaskItemFile", () => {
  test("renders with children", () => {
    render(
      <TaskItemFile data-testid="file">
        <span>file.tsx</span>
      </TaskItemFile>,
    );
    expect(screen.getByText("file.tsx")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <TaskItemFile className="custom-file" data-testid="file">
        <span>File</span>
      </TaskItemFile>,
    );
    expect(screen.getByTestId("file")).toHaveClass("custom-file");
  });

  test("has inline-flex and border classes", () => {
    render(
      <TaskItemFile data-testid="file">
        <span>File</span>
      </TaskItemFile>,
    );
    const el = screen.getByTestId("file");
    expect(el.className).toContain("inline-flex");
    expect(el.className).toContain("border");
    expect(el.className).toContain("rounded-md");
  });
});

describe("Task composition", () => {
  test("renders a full task with trigger and content", async () => {
    const user = userEvent.setup();
    render(
      <Task data-testid="task">
        <TaskTrigger title="Search for files" data-testid="trigger" />
        <TaskContent data-testid="content">
          <TaskItem data-testid="item1">
            <TaskItemFile>
              <span>index.tsx</span>
            </TaskItemFile>
          </TaskItem>
          <TaskItem data-testid="item2">
            <TaskItemFile>
              <span>app.tsx</span>
            </TaskItemFile>
          </TaskItem>
        </TaskContent>
      </Task>,
    );

    // Content is visible by default
    expect(screen.getByText("index.tsx")).toBeInTheDocument();
    expect(screen.getByText("app.tsx")).toBeInTheDocument();
  });

  test("toggle task content via trigger click", async () => {
    const user = userEvent.setup();
    render(
      <Task data-testid="task">
        <TaskTrigger title="Toggle task" data-testid="trigger" />
        <TaskContent data-testid="content">
          <p>Hidden content</p>
        </TaskContent>
      </Task>,
    );

    // Content should be visible initially (defaultOpen=true)
    expect(screen.getByText("Hidden content")).toBeInTheDocument();

    // Click trigger to collapse
    await user.click(screen.getByTestId("trigger"));

    // Content should be hidden after toggle
    // Note: Collapsible animation might keep the element in DOM briefly
    // so we check for the data-state attribute
    const content = screen.getByTestId("content");
    expect(content).toHaveAttribute("data-state", "closed");
  });
});
