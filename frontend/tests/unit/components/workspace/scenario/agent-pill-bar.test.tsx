import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({ t: {} }),
}));

vi.mock("@/core/agents/hooks", () => ({
  useAgents: () => ({
    agents: [
      {
        slug: "fault-zeroing",
        name: "故障归零专家",
        description: "Full description",
        summary: "Short summary",
      },
      {
        slug: "summarize",
        name: "智能摘要专家",
        description: "Description only",
      },
    ],
  }),
}));

vi.mock("@/components/workspace/tooltip", () => ({
  Tooltip: ({
    children,
    content,
  }: {
    children: React.ReactNode;
    content?: React.ReactNode;
  }) => (
    <div data-testid="tooltip">
      {children}
      <div data-testid="tooltip-content">{content}</div>
    </div>
  ),
}));

import { AgentPillBar } from "@/components/workspace/scenario/agent-pill-bar";
import type { AgentPill } from "@/core/scenarios/types";

afterEach(() => {
  cleanup();
});

const pills: AgentPill[] = [
  { agentSlug: "agent-a", label: "Agent A", chips: [] },
  { agentSlug: "agent-b", label: "Agent B", chips: [] },
  { agentSlug: "agent-c", label: "Agent C", chips: [] },
];

describe("AgentPillBar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("pills=[] → returns null", () => {
    const { container } = render(
      <AgentPillBar pills={[]} selectedSlug={null} onSelect={vi.fn()} />,
    );
    expect(screen.queryByTestId("agent-pill-bar")).not.toBeInTheDocument();
    expect(container.innerHTML).toBe("");
  });

  it("renders correct number of pills", () => {
    render(
      <AgentPillBar pills={pills} selectedSlug={null} onSelect={vi.fn()} />,
    );
    expect(screen.getAllByRole("tab")).toHaveLength(3);
  });

  it("selected pill has aria-selected=true", () => {
    render(
      <AgentPillBar pills={pills} selectedSlug="agent-b" onSelect={vi.fn()} />,
    );
    const tabB = screen.getByRole("tab", { name: "Agent B" });
    expect(tabB).toHaveAttribute("aria-selected", "true");
    expect(tabB).toHaveAttribute("data-state", "active");

    const tabA = screen.getByRole("tab", { name: "Agent A" });
    expect(tabA).toHaveAttribute("aria-selected", "false");
  });

  it("clicks pill → onSelect(agentSlug) called", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <AgentPillBar pills={pills} selectedSlug={null} onSelect={onSelect} />,
    );

    await user.click(screen.getByRole("tab", { name: "Agent B" }));
    expect(onSelect).toHaveBeenCalledWith("agent-b");
  });

  it("ArrowRight cycles to next pill", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <AgentPillBar pills={pills} selectedSlug="agent-a" onSelect={onSelect} />,
    );

    const tab = screen.getByRole("tab", { name: "Agent A" });
    tab.focus();
    await user.keyboard("{ArrowRight}");
    expect(onSelect).toHaveBeenCalledWith("agent-b");
  });

  it("ArrowLeft cycles to previous pill", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <AgentPillBar pills={pills} selectedSlug="agent-a" onSelect={onSelect} />,
    );

    const tab = screen.getByRole("tab", { name: "Agent A" });
    tab.focus();
    await user.keyboard("{ArrowLeft}");
    expect(onSelect).toHaveBeenCalledWith("agent-c");
  });

  it("clicks already selected pill → toggle off (onSelect called with slug again)", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <AgentPillBar pills={pills} selectedSlug="agent-a" onSelect={onSelect} />,
    );

    await user.click(screen.getByRole("tab", { name: "Agent A" }));
    expect(onSelect).toHaveBeenCalledWith("agent-a");
  });
});

describe("AgentPillBar descriptions", () => {
  const describedPills: AgentPill[] = [
    { agentSlug: "fault-zeroing", label: "故障归零" },
    { agentSlug: "summarize", label: "智能摘要" },
    { agentSlug: "unknown-agent", label: "未知专家" },
  ];

  const contents = () =>
    screen.getAllByTestId("tooltip-content").map((node) => node.textContent);

  it("prefers the agent summary for the tooltip", () => {
    render(
      <AgentPillBar
        pills={describedPills}
        selectedSlug={null}
        onSelect={vi.fn()}
      />,
    );

    expect(contents()).toContain("Short summary");
  });

  it("falls back to the description when no summary exists", () => {
    render(
      <AgentPillBar
        pills={describedPills}
        selectedSlug={null}
        onSelect={vi.fn()}
      />,
    );

    expect(contents()).toContain("Description only");
  });

  it("renders unmatched agents with no tooltip", () => {
    render(
      <AgentPillBar
        pills={describedPills}
        selectedSlug={null}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getAllByTestId("tooltip")).toHaveLength(2);
    expect(screen.getByRole("tab", { name: "未知专家" })).toBeInTheDocument();
  });
});
