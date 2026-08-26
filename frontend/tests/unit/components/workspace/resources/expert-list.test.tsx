import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockAgents = [
  { name: "agent-1", description: "Agent 1 description", is_favorited: false },
  { name: "agent-2", description: "Agent 2 description", is_favorited: true },
];

vi.mock("@/core/agents", () => ({
  useAgents: () => ({
    agents: mockAgents,
    isLoading: false,
  }),
}));

vi.mock("@/components/workspace/agents/agent-card", () => ({
  AgentCard: ({ agent }: { agent: { name: string } }) => (
    <div data-testid="agent-card">{agent.name}</div>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let ExpertList: typeof import("@/components/workspace/resources/expert-list").ExpertList;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/workspace/resources/expert-list");
  ExpertList = mod.ExpertList;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("ExpertList", () => {
  test("displays list of experts (agents)", () => {
    render(<ExpertList />);
    expect(screen.getByText("agent-1")).toBeInTheDocument();
    expect(screen.getByText("agent-2")).toBeInTheDocument();
  });

  test("renders agent cards", () => {
    render(<ExpertList />);
    const cards = screen.getAllByTestId("agent-card");
    expect(cards).toHaveLength(2);
  });
});
