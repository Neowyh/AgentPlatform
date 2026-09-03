import { render, screen, cleanup } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      scenarios: {
        daily: "日常办公",
        creative: "创意设计",
        professional: "专业任务",
      },
    },
  }),
}));

const mockGetPillsByScenario = vi.fn();
const mockGetChipsByPill = vi.fn();
vi.mock("@/core/scenarios/config", () => ({
  getPillsByScenario: (...args: unknown[]) => mockGetPillsByScenario(...args),
  getChipsByPill: (...args: unknown[]) => mockGetChipsByPill(...args),
}));

vi.mock("@/core/scenarios/types", () => ({}));

vi.mock("@/core/agents/hooks", () => ({
  useAgents: () => ({ agents: [] }),
}));

vi.mock("@/core/skills/hooks", () => ({
  useSkills: () => ({ skills: [] }),
}));

import { ScenarioCascadeBar } from "@/components/workspace/scenario/index";
import type {
  ChipSelection,
  PillSelection,
  ScenarioId,
} from "@/core/scenarios/types";

afterEach(() => {
  cleanup();
});

describe("ScenarioCascadeBar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetPillsByScenario.mockReturnValue([]);
    mockGetChipsByPill.mockReturnValue([]);
  });

  const defaultProps = {
    selectedScenario: null as ScenarioId | null,
    selectedPill: null as PillSelection,
    selectedChip: null as ChipSelection,
    onTogglePill: vi.fn(),
    onToggleChip: vi.fn(),
  };

  it("no selected scenario → no task entry is rendered", () => {
    render(<ScenarioCascadeBar {...defaultProps} />);
    expect(screen.getByTestId("scenario-cascade-bar")).toBeInTheDocument();
    expect(screen.queryByTestId("agent-pill-bar")).not.toBeInTheDocument();
    expect(screen.queryByTestId("task-chip-bar")).not.toBeInTheDocument();
  });

  it("selected scenario → Agent pill entry is rendered", () => {
    mockGetPillsByScenario.mockReturnValue([
      { agentSlug: "agent-a", label: "Agent A", chips: [] },
    ]);
    render(<ScenarioCascadeBar {...defaultProps} selectedScenario="daily" />);
    expect(screen.getByTestId("agent-pill-bar")).toBeInTheDocument();
    expect(screen.queryByTestId("task-chip-bar")).not.toBeInTheDocument();
  });

  it("selected Agent pill → replaces Agent entry with its Task pills", () => {
    mockGetPillsByScenario.mockReturnValue([
      { agentSlug: "agent-a", label: "Agent A", chips: [] },
    ]);
    mockGetChipsByPill.mockReturnValue([
      {
        taskId: "task-a",
        skillName: "s1",
        label: "Task A",
        promptTemplate: "t1",
      },
    ]);

    render(
      <ScenarioCascadeBar
        {...defaultProps}
        selectedScenario="daily"
        selectedPill={{ scenarioId: "daily", agentSlug: "agent-a" }}
      />,
    );

    expect(screen.queryByTestId("agent-pill-bar")).not.toBeInTheDocument();
    expect(screen.getByTestId("task-chip-bar")).toBeInTheDocument();
  });

  it("toggleChip passes through onToggleChip", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    mockGetPillsByScenario.mockReturnValue([
      {
        agentSlug: "agent-a",
        label: "Agent A",
        chips: [
          {
            taskId: "task-a",
            label: "Skill",
            skillName: "s1",
            promptTemplate: "t1",
          },
        ],
      },
    ]);
    mockGetChipsByPill.mockReturnValue([
      { taskId: "task-a", label: "Skill", skillName: "s1" },
    ]);
    const onToggleChip = vi.fn();

    render(
      <ScenarioCascadeBar
        {...defaultProps}
        selectedScenario="daily"
        selectedPill={{ scenarioId: "daily", agentSlug: "agent-a" }}
        onToggleChip={onToggleChip}
      />,
    );

    await userEvent.setup().click(screen.getByRole("tab", { name: "Skill" }));

    expect(onToggleChip).toHaveBeenCalledWith("task-a");
  });

  it("scenario switch → pills refresh", () => {
    mockGetPillsByScenario.mockReturnValue([
      { agentSlug: "agent-a", label: "Agent A", chips: [] },
    ]);

    const { rerender } = render(
      <ScenarioCascadeBar {...defaultProps} selectedScenario="daily" />,
    );

    expect(mockGetPillsByScenario).toHaveBeenCalledWith("daily");

    mockGetPillsByScenario.mockReturnValue([
      { agentSlug: "agent-x", label: "Agent X", chips: [] },
    ]);

    rerender(
      <ScenarioCascadeBar {...defaultProps} selectedScenario="creative" />,
    );

    expect(mockGetPillsByScenario).toHaveBeenCalledWith("creative");
  });

  it("container reserves a fixed task-entry row", () => {
    render(<ScenarioCascadeBar {...defaultProps} />);
    const container = screen.getByTestId("scenario-cascade-bar");
    expect(container.className).toContain("min-h-10");
  });
});
