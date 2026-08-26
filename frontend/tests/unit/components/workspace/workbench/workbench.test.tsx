import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import {
  AgentShowcase,
  SceneSuggestionCards,
  agentChatUrlWithPrompt,
} from "@/components/workspace/workbench";
import { RecentChatsCard } from "@/components/workspace/workbench/recent-chats-card";
import type { Agent } from "@/core/agents";
import type { AgentThread } from "@/core/threads/types";

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en",
    t: {
      workbench: {
        tryAsking: "Try asking",
        agentsTitle: "Pick an agent",
        recentChatsTitle: "Recent chats",
        viewAllAgents: "View all",
        emptyAgents: "No agents available yet",
        promptTemplate: "Hi, I'd like {name} to help me with: ",
      },
    },
  }),
}));

const mockAgents: Agent[] = [
  {
    name: "Researcher",
    description: "Finds facts fast",
    model: null,
    tool_groups: null,
    skills: null,
    visibility: "public",
    owner_id: null,
    department_id: null,
  },
];

vi.mock("@/core/agents", () => ({
  useAgents: () => ({ agents: mockAgentsData }),
}));

vi.mock("@/core/threads/hooks", () => ({
  useThreads: () => ({ data: mockThreadsData }),
}));

let mockAgentsData: Agent[] = mockAgents;
let mockThreadsData: AgentThread[] = [];

describe("SceneSuggestionCards", () => {
  beforeEach(() => {
    mockAgentsData = mockAgents;
  });

  test("renders a suggestion card per agent with prefilled chat link", () => {
    render(<SceneSuggestionCards />);

    const card = screen.getByTestId("workbench-suggestion-card");
    expect(card).toHaveAttribute(
      "href",
      expect.stringContaining("/workspace/agents/Researcher/chats/new?prompt="),
    );
    const href = card.getAttribute("href")!;
    expect(decodeURIComponent(href.split("prompt=")[1]!)).toBe(
      "Hi, I'd like Researcher to help me with: ",
    );
    expect(screen.getByText("Researcher")).toBeInTheDocument();
    expect(screen.getByText("Finds facts fast")).toBeInTheDocument();
  });

  test("renders nothing when no agents are available", () => {
    mockAgentsData = [];
    const { container } = render(<SceneSuggestionCards />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("AgentShowcase", () => {
  beforeEach(() => {
    mockAgentsData = mockAgents;
  });

  test("renders agent items and view-all link", () => {
    render(<AgentShowcase />);
    expect(screen.getByTestId("workbench-agent-item")).toBeInTheDocument();
    expect(screen.getByText("View all")).toHaveAttribute(
      "href",
      "/workspace/agents",
    );
  });

  test("renders empty state when no agents are available", () => {
    mockAgentsData = [];
    render(<AgentShowcase />);
    expect(screen.getByText("No agents available yet")).toBeInTheDocument();
  });
});

describe("RecentChatsCard", () => {
  beforeEach(() => {
    mockThreadsData = [];
  });

  test("renders recent thread links", () => {
    mockThreadsData = [
      {
        thread_id: "t1",
        values: { title: "My first chat", messages: [], artifacts: [] },
        metadata: {},
      },
      {
        thread_id: "t2",
        values: { messages: [], artifacts: [] },
        metadata: {},
      },
    ] as unknown as AgentThread[];
    render(<RecentChatsCard />);
    expect(screen.getByTestId("workbench-recent-chats").children.length).toBe(
      2,
    );
    expect(screen.getByText("My first chat")).toHaveAttribute(
      "href",
      "/workspace/chats/t1",
    );
  });

  test("renders nothing when there are no threads", () => {
    const { container } = render(<RecentChatsCard />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("agentChatUrlWithPrompt", () => {
  test("encodes agent identity and prompt", () => {
    const url = agentChatUrlWithPrompt(mockAgents[0]!, "hello world");
    expect(url).toBe(
      `/workspace/agents/Researcher/chats/new?prompt=${encodeURIComponent("hello world")}`,
    );
  });
});
