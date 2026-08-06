import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { importAgent } from "@/core/agents/api";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockPush = vi.fn();
const mockRefetch = vi.fn();
let mockAgents: unknown[] = [];
let mockIsLoading = false;

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      agents: {
        title: "Agents",
        description: "Manage your agents",
        newAgent: "New Agent",
        emptyTitle: "No agents yet",
        emptyDescription: "Create your first agent",
        importSuccess: "Agent imported",
      },
      common: {
        loading: "Loading...",
        import: "Import",
        favoritesOnly: "Favorites",
        showAll: "Show All",
      },
      workspace: { adminPanel: "Admin Panel" },
    },
  }),
}));

vi.mock("@/core/agents", () => ({
  useAgents: () => ({
    agents: mockAgents,
    isLoading: mockIsLoading,
    refetch: mockRefetch,
  }),
}));

vi.mock("@/core/agents/api", () => ({
  importAgent: vi.fn(),
}));

vi.mock("@/components/workspace/agents/agent-card", () => ({
  AgentCard: ({ agent }: { agent: { name: string } }) => (
    <div data-testid="agent-card">{agent.name}</div>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let AgentGallery: typeof import("@/components/workspace/agents/agent-gallery").AgentGallery;

beforeEach(async () => {
  vi.clearAllMocks();
  mockAgents = [];
  mockIsLoading = false;
  const mod = await import("@/components/workspace/agents/agent-gallery");
  AgentGallery = mod.AgentGallery;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("AgentGallery", () => {
  test("renders the page title", () => {
    render(<AgentGallery />);
    expect(screen.getByText("Agents")).toBeInTheDocument();
  });

  test("renders the page description", () => {
    render(<AgentGallery />);
    expect(screen.getByText("Manage your agents")).toBeInTheDocument();
  });

  test("renders new agent button", () => {
    render(<AgentGallery />);
    const buttons = screen.getAllByText("New Agent");
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });

  test("renders import button", () => {
    render(<AgentGallery />);
    expect(screen.getByText("Import")).toBeInTheDocument();
  });

  test("shows empty state when no agents", () => {
    render(<AgentGallery />);
    expect(screen.getByText("No agents yet")).toBeInTheDocument();
    expect(screen.getByText("Create your first agent")).toBeInTheDocument();
  });

  test("navigates to new agent page when new button clicked", async () => {
    const user = userEvent.setup();
    render(<AgentGallery />);
    const newButtons = screen.getAllByText("New Agent");
    await user.click(newButtons[0]!);
    expect(mockPush).toHaveBeenCalledWith("/workspace/agents/new");
  });

  test("shows loading state", () => {
    mockIsLoading = true;
    mockAgents = [];
    render(<AgentGallery />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  test("renders agent cards when agents exist", () => {
    mockAgents = [
      { name: "Agent 1", description: "First agent" },
      { name: "Agent 2", description: "Second agent" },
    ];
    render(<AgentGallery />);
    expect(screen.getByText("Agent 1")).toBeInTheDocument();
    expect(screen.getByText("Agent 2")).toBeInTheDocument();
    const cards = screen.getAllByTestId("agent-card");
    expect(cards).toHaveLength(2);
  });

  test("has file input for import", () => {
    render(<AgentGallery />);
    const fileInput = document.querySelector('input[type="file"]');
    expect(fileInput).toBeInTheDocument();
    expect(fileInput).toHaveAttribute("accept", ".zip");
  });

  test("filters agents by search text", async () => {
    const user = userEvent.setup();
    mockAgents = [
      { name: "Writer", description: "Draft documents" },
      { name: "Researcher", description: "Find references" },
    ];
    render(<AgentGallery />);

    await user.type(screen.getByPlaceholderText("Agents..."), "references");

    expect(screen.queryByText("Writer")).not.toBeInTheDocument();
    expect(screen.getByText("Researcher")).toBeInTheDocument();
  });

  test("filters agents to favorites and toggles back to all", async () => {
    const user = userEvent.setup();
    mockAgents = [
      { name: "Favorite Agent", description: "", is_favorited: true },
      { name: "Regular Agent", description: "", is_favorited: false },
    ];
    render(<AgentGallery />);

    await user.click(screen.getByRole("button", { name: /Favorites/ }));
    expect(screen.getByText("Favorite Agent")).toBeInTheDocument();
    expect(screen.queryByText("Regular Agent")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Show All/ }));
    expect(screen.getByText("Regular Agent")).toBeInTheDocument();
  });

  test("imports an agent file and refreshes the list", async () => {
    vi.mocked(importAgent).mockResolvedValue({ success: true } as never);
    const user = userEvent.setup();
    render(<AgentGallery />);
    const file = new File(["zip"], "agent.zip", { type: "application/zip" });

    await user.upload(document.querySelector('input[type="file"]')!, file);

    expect(importAgent).toHaveBeenCalledWith(file);
    expect(toast.success).toHaveBeenCalledWith("Agent imported");
    expect(mockRefetch).toHaveBeenCalled();
  });

  test("shows import errors and clears the input", async () => {
    vi.mocked(importAgent).mockRejectedValue(new Error("Import failed"));
    const user = userEvent.setup();
    render(<AgentGallery />);
    const input =
      document.querySelector<HTMLInputElement>('input[type="file"]');
    const file = new File(["zip"], "agent.zip", { type: "application/zip" });

    if (!input) {
      throw new Error("Expected agent import input");
    }

    await user.upload(input, file);

    expect(toast.error).toHaveBeenCalledWith("Import failed");
    expect(input.value).toBe("");
  });

  test("ignores import change without a selected file", async () => {
    render(<AgentGallery />);
    const input = document.querySelector('input[type="file"]')!;

    input.dispatchEvent(new Event("change", { bubbles: true }));

    expect(importAgent).not.toHaveBeenCalled();
  });
});
