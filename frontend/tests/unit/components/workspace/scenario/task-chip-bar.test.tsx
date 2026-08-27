import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({ t: {} }),
}));

import { TaskChipBar } from "@/components/workspace/scenario/task-chip-bar";
import type { TaskChip } from "@/core/scenarios/types";

afterEach(() => {
  cleanup();
});

const chips: TaskChip[] = [
  {
    taskId: "task-1",
    label: "Chip One",
    skillName: "skill-1",
    promptTemplate: "tpl1",
  },
  {
    taskId: "task-2",
    label: "Chip Two",
    skillName: "skill-2",
    promptTemplate: "tpl2",
  },
  {
    taskId: "task-3",
    label: "Chip Three",
    skillName: "skill-3",
    promptTemplate: "tpl3",
  },
];

describe("TaskChipBar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("chips=[] → returns null", () => {
    const { container } = render(
      <TaskChipBar chips={[]} selectedTaskId={null} onSelect={vi.fn()} />,
    );
    expect(screen.queryByTestId("task-chip-bar")).not.toBeInTheDocument();
    expect(container.innerHTML).toBe("");
  });

  it("renders correct number of chips", () => {
    render(
      <TaskChipBar chips={chips} selectedTaskId={null} onSelect={vi.fn()} />,
    );
    expect(screen.getAllByRole("tab")).toHaveLength(3);
  });

  it("keeps same-skill tasks distinct without a duplicate-key warning", () => {
    const onSelect = vi.fn();
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);

    render(
      <TaskChipBar
        chips={[
          {
            taskId: "document-summary",
            label: "文档摘要",
            skillName: "summarize",
            promptTemplate: "document template",
          },
          {
            taskId: "meeting-minutes",
            label: "会议纪要",
            skillName: "summarize",
            promptTemplate: "meeting template",
          },
        ]}
        selectedTaskId={null}
        onSelect={onSelect}
      />,
    );

    expect(screen.getAllByRole("tab")).toHaveLength(2);
    expect(consoleError).not.toHaveBeenCalledWith(
      expect.stringContaining('unique "key"'),
    );
    consoleError.mockRestore();
  });

  it("selected chip has aria-selected=true", () => {
    render(
      <TaskChipBar chips={chips} selectedTaskId="task-2" onSelect={vi.fn()} />,
    );
    const tab2 = screen.getByRole("tab", { name: "Chip Two" });
    expect(tab2).toHaveAttribute("aria-selected", "true");
    expect(tab2).toHaveAttribute("data-state", "active");

    const tab1 = screen.getByRole("tab", { name: "Chip One" });
    expect(tab1).toHaveAttribute("aria-selected", "false");
  });

  it("clicks chip → onSelect(taskId) called", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <TaskChipBar chips={chips} selectedTaskId={null} onSelect={onSelect} />,
    );

    await user.click(screen.getByRole("tab", { name: "Chip Two" }));
    expect(onSelect).toHaveBeenCalledWith("task-2");
  });

  it("ArrowRight cycles to next chip", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <TaskChipBar chips={chips} selectedTaskId="task-1" onSelect={onSelect} />,
    );

    const tab = screen.getByRole("tab", { name: "Chip One" });
    tab.focus();
    await user.keyboard("{ArrowRight}");
    expect(onSelect).toHaveBeenCalledWith("task-2");
  });

  it("ArrowLeft cycles to previous chip", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <TaskChipBar chips={chips} selectedTaskId="task-1" onSelect={onSelect} />,
    );

    const tab = screen.getByRole("tab", { name: "Chip One" });
    tab.focus();
    await user.keyboard("{ArrowLeft}");
    expect(onSelect).toHaveBeenCalledWith("task-3");
  });

  it("clicks already selected chip → toggle off (onSelect called with taskId again)", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <TaskChipBar chips={chips} selectedTaskId="task-1" onSelect={onSelect} />,
    );

    await user.click(screen.getByRole("tab", { name: "Chip One" }));
    expect(onSelect).toHaveBeenCalledWith("task-1");
  });
});
