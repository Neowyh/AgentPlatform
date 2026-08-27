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

const mockGetTemplateForChip = vi.fn();
vi.mock("@/core/scenarios/prompt-templates", () => ({
  getTemplateForChip: (...args: unknown[]) => mockGetTemplateForChip(...args),
}));

vi.mock("@/core/scenarios/types", () => ({}));

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
    mockGetTemplateForChip.mockReturnValue(undefined);
  });

  const defaultProps = {
    selectedScenario: null as ScenarioId | null,
    selectedPill: null as PillSelection,
    selectedChip: null as ChipSelection,
    onSelectScenario: vi.fn(),
    onTogglePill: vi.fn(),
    onToggleChip: vi.fn(),
    onInjectPrompt: vi.fn(),
  };

  it("no selected scenario → only ScenarioTabs rendered", () => {
    render(<ScenarioCascadeBar {...defaultProps} />);
    expect(screen.getByTestId("scenario-cascade-bar")).toBeInTheDocument();
    expect(screen.getByTestId("scenario-tabs")).toBeInTheDocument();
    expect(screen.queryByTestId("agent-or-skill-bar")).not.toBeInTheDocument();
  });

  it("selected scenario → AgentOrSkillBar rendered", () => {
    mockGetPillsByScenario.mockReturnValue([
      { agentSlug: "agent-a", label: "Agent A", chips: [] },
    ]);
    render(<ScenarioCascadeBar {...defaultProps} selectedScenario="daily" />);
    expect(screen.getByTestId("agent-or-skill-bar")).toBeInTheDocument();
  });

  it("onInjectPrompt calls getTemplateForChip result", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    mockGetPillsByScenario.mockReturnValue([
      {
        agentSlug: "agent-a",
        label: "Agent A",
        chips: [{ label: "Skill", skillName: "s1", promptTemplate: "t1" }],
      },
    ]);
    mockGetTemplateForChip.mockReturnValue({
      promptTemplate: "prompt from template",
    });
    const onInjectPrompt = vi.fn();
    const onToggleChip = vi.fn();

    render(
      <ScenarioCascadeBar
        {...defaultProps}
        selectedScenario="daily"
        selectedPill={{ scenarioId: "daily", agentSlug: "agent-a" }}
        onToggleChip={onToggleChip}
        onInjectPrompt={onInjectPrompt}
      />,
    );

    await userEvent.setup().click(screen.getByRole("tab", { name: "Skill" }));

    expect(onToggleChip).toHaveBeenCalledWith("daily", "agent-a", "s1");
    expect(mockGetTemplateForChip).toHaveBeenCalledWith(
      "daily",
      "agent-a",
      "s1",
    );
    expect(onInjectPrompt).toHaveBeenCalledWith("prompt from template");
  });

  it("getTemplateForChip returns undefined → onInjectPrompt not called", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    mockGetPillsByScenario.mockReturnValue([
      {
        agentSlug: "agent-a",
        label: "Agent A",
        chips: [{ label: "Skill", skillName: "s1", promptTemplate: "t1" }],
      },
    ]);
    mockGetTemplateForChip.mockReturnValue(undefined);
    const onInjectPrompt = vi.fn();

    render(
      <ScenarioCascadeBar
        {...defaultProps}
        selectedScenario="daily"
        selectedPill={{ scenarioId: "daily", agentSlug: "agent-a" }}
        onInjectPrompt={onInjectPrompt}
      />,
    );

    await userEvent.setup().click(screen.getByRole("tab", { name: "Skill" }));

    expect(onInjectPrompt).not.toHaveBeenCalled();
  });

  it("toggleChip passes through onToggleChip", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    mockGetPillsByScenario.mockReturnValue([
      {
        agentSlug: "agent-a",
        label: "Agent A",
        chips: [{ label: "Skill", skillName: "s1", promptTemplate: "t1" }],
      },
    ]);
    mockGetTemplateForChip.mockReturnValue(undefined);
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

    expect(onToggleChip).toHaveBeenCalledWith("daily", "agent-a", "s1");
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
});
