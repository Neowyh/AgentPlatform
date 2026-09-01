import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const defaultAgents = [
  { name: "agent-1", description: "Agent 1 description", is_favorited: false },
  { name: "agent-2", description: "Agent 2 description", is_favorited: true },
];
let mockAgents = defaultAgents;

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

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({ t: { agents: { newAgent: "New Agent" } } }),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let ExpertList: typeof import("@/components/workspace/resources/expert-list").ExpertList;

beforeEach(async () => {
  vi.clearAllMocks();
  mockAgents = defaultAgents;
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

  test("keeps the new-agent action available for an empty catalog", () => {
    mockAgents = [];

    render(<ExpertList />);

    expect(screen.getByRole("link", { name: "New Agent" })).toHaveAttribute(
      "href",
      "/workspace/agents/new",
    );
  });
});
