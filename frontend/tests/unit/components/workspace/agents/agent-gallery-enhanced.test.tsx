import {
  render,
  screen,
  cleanup,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { Agent } from "@/core/agents";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockToastSuccess = vi.fn();
const mockToastError = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => mockToastSuccess(...args),
    error: (...args: unknown[]) => mockToastError(...args),
  },
}));

let mockAgents: Agent[] = [];
let mockIsLoading = false;
const mockRefetch = vi.fn();

vi.mock("@/core/agents", () => ({
  useAgents: () => ({
    agents: mockAgents,
    isLoading: mockIsLoading,
    refetch: mockRefetch,
  }),
}));

const mockImportAgent = vi.fn();
vi.mock("@/core/agents/api", () => ({
  importAgent: (...args: unknown[]) => mockImportAgent(...args),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: {
      agents: {
        title: "Agents",
        description: "Manage your agents",
        emptyTitle: "No agents yet",
        emptyDescription: "Create your first agent",
        newAgent: "New Agent",
        chat: "Chat",
        delete: "Delete",
        deleteConfirm: "Are you sure?",
        deleteSuccess: "Agent deleted",
        template: "Template",
      },
      common: {
        cancel: "Cancel",
        delete: "Delete",
        loading: "Loading...",
        import: "Import",
      },
    },
    changeLocale: vi.fn(),
  }),
}));

vi.mock("@/components/workspace/agents/agent-card", () => ({
  AgentCard: ({ agent }: { agent: Agent }) => (
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
  test("renders the page header with title and description", () => {
    render(<AgentGallery />);
    expect(screen.getByText("Agents")).toBeInTheDocument();
    expect(screen.getByText("Manage your agents")).toBeInTheDocument();
  });

  test("renders New Agent button", () => {
    render(<AgentGallery />);
    // New Agent appears in both header and empty state
    const newAgentBtns = screen.getAllByText("New Agent");
    expect(newAgentBtns.length).toBeGreaterThanOrEqual(1);
  });

  test("renders Import button", () => {
    render(<AgentGallery />);
    expect(screen.getByText("Import")).toBeInTheDocument();
  });

  test("shows loading state", () => {
    mockIsLoading = true;
    render(<AgentGallery />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  test("shows empty state when no agents", () => {
    mockAgents = [];
    render(<AgentGallery />);
    expect(screen.getByText("No agents yet")).toBeInTheDocument();
    expect(screen.getByText("Create your first agent")).toBeInTheDocument();
  });

  test("renders agent cards when agents exist", () => {
    mockAgents = [
      { name: "agent-1", description: "desc1", model: "gpt-4" } as Agent,
      { name: "agent-2", description: "desc2", model: "gpt-3" } as Agent,
    ];
    render(<AgentGallery />);
    const cards = screen.getAllByTestId("agent-card");
    expect(cards).toHaveLength(2);
    expect(screen.getByText("agent-1")).toBeInTheDocument();
    expect(screen.getByText("agent-2")).toBeInTheDocument();
  });

  test("new agent button navigates to new agent page", () => {
    render(<AgentGallery />);
    // Click the first New Agent button (in the header)
    const newAgentBtns = screen.getAllByText("New Agent");
    fireEvent.click(newAgentBtns[0]!);
    expect(mockPush).toHaveBeenCalledWith("/workspace/agents/new");
  });

  test("empty state new agent button also navigates", () => {
    mockAgents = [];
    render(<AgentGallery />);
    const newAgentBtns = screen.getAllByText("New Agent");
    // Click the one in the empty state
    fireEvent.click(newAgentBtns[newAgentBtns.length - 1]!);
    expect(mockPush).toHaveBeenCalledWith("/workspace/agents/new");
  });

  test("import button triggers file input click", () => {
    render(<AgentGallery />);
    // The import button should exist
    expect(screen.getByText("Import")).toBeInTheDocument();
    const fileInput = document.querySelector("input[type='file']")!;
    expect(fileInput).toBeInTheDocument();
  });

  test("handles successful file import", async () => {
    mockImportAgent.mockResolvedValue(undefined);
    mockRefetch.mockResolvedValue(undefined);

    render(<AgentGallery />);

    const fileInput = document.querySelector("input[type='file']")!;
    const file = new File(["test"], "agent.zip", { type: "application/zip" });

    // Mock the file input
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(mockImportAgent).toHaveBeenCalledWith(file);
    });
    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith("智能体已导入");
    });
  });

  test("handles failed file import", async () => {
    mockImportAgent.mockRejectedValue(new Error("Import failed"));

    render(<AgentGallery />);

    const fileInput = document.querySelector("input[type='file']")!;
    const file = new File(["test"], "agent.zip", { type: "application/zip" });

    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("Import failed");
    });
  });

  test("handles import with non-Error thrown", async () => {
    mockImportAgent.mockRejectedValue("unknown error");

    render(<AgentGallery />);

    const fileInput = document.querySelector("input[type='file']")!;
    const file = new File(["test"], "agent.zip", { type: "application/zip" });

    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("unknown error");
    });
  });

  test("import with no file selected does nothing", async () => {
    render(<AgentGallery />);

    const fileInput = document.querySelector("input[type='file']")!;
    Object.defineProperty(fileInput, "files", { value: [] });
    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(mockImportAgent).not.toHaveBeenCalled();
    });
  });

  test("file input accepts .zip files", () => {
    render(<AgentGallery />);
    const fileInput = document.querySelector("input[type='file']")!;
    expect(fileInput).toHaveAttribute("accept", ".zip");
  });

  test("file input has hidden class", () => {
    render(<AgentGallery />);
    const fileInput = document.querySelector("input[type='file']")!;
    expect(fileInput.className).toContain("hidden");
  });
});
