import { render, screen, cleanup } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({ t: {} }),
}));

vi.mock("@/core/scenarios/types", () => ({}));

import { AgentOrSkillBar } from "@/components/workspace/scenario/agent-or-skill-bar";
import type {
  AgentPill,
  ChipSelection,
  PillSelection,
  ScenarioId,
} from "@/core/scenarios/types";

afterEach(() => {
  cleanup();
});

const pills: AgentPill[] = [
  {
    agentSlug: "agent-a",
    label: "Agent A",
    chips: [
      { label: "Skill 1", skillName: "skill-1", promptTemplate: "t1" },
      { label: "Skill 2", skillName: "skill-2", promptTemplate: "t2" },
    ],
  },
  {
    agentSlug: "agent-b",
    label: "Agent B",
    chips: [],
  },
];

describe("AgentOrSkillBar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const defaultProps = {
    pills,
    selectedPill: null as PillSelection,
    selectedChip: null as ChipSelection,
    onTogglePill: vi.fn(),
    onToggleChip: vi.fn(),
    scenarioId: "daily" as ScenarioId,
  };

  it("renders AgentPillBar", () => {
    render(<AgentOrSkillBar {...defaultProps} />);
    expect(screen.getByTestId("agent-pill-bar")).toBeInTheDocument();
  });

  it("no selected pill → TaskChipBar not rendered", () => {
    render(<AgentOrSkillBar {...defaultProps} />);
    expect(screen.queryByTestId("task-chip-bar")).not.toBeInTheDocument();
  });

  it("selected pill with chips → renders divider + TaskChipBar", () => {
    render(
      <AgentOrSkillBar
        {...defaultProps}
        selectedPill={{ scenarioId: "daily", agentSlug: "agent-a" }}
      />,
    );
    expect(screen.getByTestId("agent-pill-bar")).toBeInTheDocument();
    expect(screen.getByTestId("task-chip-bar")).toBeInTheDocument();
  });

  it("selected pill with no chips → no divider, no TaskChipBar", () => {
    render(
      <AgentOrSkillBar
        {...defaultProps}
        selectedPill={{ scenarioId: "daily", agentSlug: "agent-b" }}
      />,
    );
    expect(screen.getByTestId("agent-pill-bar")).toBeInTheDocument();
    expect(screen.queryByTestId("task-chip-bar")).not.toBeInTheDocument();
  });

  it("onTogglePill is passed through", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const onTogglePill = vi.fn();
    render(<AgentOrSkillBar {...defaultProps} onTogglePill={onTogglePill} />);

    await userEvent.setup().click(screen.getByRole("tab", { name: "Agent A" }));
    expect(onTogglePill).toHaveBeenCalledWith("daily", "agent-a");
  });

  it("onToggleChip is passed through", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const onToggleChip = vi.fn();
    render(
      <AgentOrSkillBar
        {...defaultProps}
        selectedPill={{ scenarioId: "daily", agentSlug: "agent-a" }}
        onToggleChip={onToggleChip}
      />,
    );

    await userEvent.setup().click(screen.getByRole("tab", { name: "Skill 1" }));
    expect(onToggleChip).toHaveBeenCalledWith("daily", "agent-a", "skill-1");
  });
});
