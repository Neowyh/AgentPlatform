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

const mockMutateAsync = vi.fn();
let mockDeletePending = false;
vi.mock("@/core/agents", () => ({
  useDeleteAgent: () => ({
    mutateAsync: mockMutateAsync,
    get isPending() {
      return mockDeletePending;
    },
  }),
}));

const mockExportAgent = vi.fn();
vi.mock("@/core/agents/api", () => ({
  exportAgent: (...args: unknown[]) => mockExportAgent(...args),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: {
      agents: {
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
      },
    },
    changeLocale: vi.fn(),
  }),
}));

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeAgent(overrides: Partial<Agent> = {}): Agent {
  return {
    name: "test-agent",
    description: "A test agent",
    model: "gpt-4",
    tool_groups: ["web", "code"],
    skills: ["summarize"],
    read_only: false,
    visibility: "public",
    owner_id: null,
    department_id: null,
    ...overrides,
  };
}

// ── Dynamic import (after mocks) ─────────────────────────────────────────────

let AgentCard: (props: { agent: Agent }) => React.JSX.Element;

beforeEach(async () => {
  vi.clearAllMocks();
  mockDeletePending = false;
  const mod = await import("@/components/workspace/agents/agent-card");
  AgentCard = mod.AgentCard;
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("AgentCard", () => {
  // ── Rendering ────────────────────────────────────────────────────────────

  test("renders the card with agent name", () => {
    render(<AgentCard agent={makeAgent()} />);
    expect(screen.getByTestId("agent-card")).toBeInTheDocument();
    expect(screen.getByText("test-agent")).toBeInTheDocument();
  });

  test("renders the description when provided", () => {
    render(<AgentCard agent={makeAgent({ description: "Hello world" })} />);
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  test("does not render description when description is empty string", () => {
    const { container } = render(
      <AgentCard agent={makeAgent({ description: "" })} />,
    );
    const desc = container.querySelector(".line-clamp-2");
    expect(desc).toBeNull();
  });

  test("does not render description when description is falsy", () => {
    const { container } = render(
      <AgentCard
        agent={makeAgent({ description: undefined as unknown as string })}
      />,
    );
    const desc = container.querySelector(".line-clamp-2");
    expect(desc).toBeNull();
  });

  test("renders model badge when model is provided", () => {
    render(<AgentCard agent={makeAgent({ model: "gpt-4" })} />);
    expect(screen.getByText("gpt-4")).toBeInTheDocument();
  });

  test("does not render model badge when model is null", () => {
    render(<AgentCard agent={makeAgent({ model: null })} />);
    expect(screen.queryByText("gpt-4")).not.toBeInTheDocument();
  });

  test("renders read-only badge when read_only is true", () => {
    render(<AgentCard agent={makeAgent({ read_only: true })} />);
    expect(screen.getByText("Template")).toBeInTheDocument();
  });

  test("does not render read-only badge when read_only is false", () => {
    render(<AgentCard agent={makeAgent({ read_only: false })} />);
    expect(screen.queryByText("Template")).not.toBeInTheDocument();
  });

  // ── Tool groups & skills badges ──────────────────────────────────────────

  test("renders tool_group badges", () => {
    render(
      <AgentCard
        agent={makeAgent({ tool_groups: ["web", "code"], skills: null })}
      />,
    );
    expect(screen.getByText("web")).toBeInTheDocument();
    expect(screen.getByText("code")).toBeInTheDocument();
  });

  test("renders skill badges", () => {
    render(
      <AgentCard
        agent={makeAgent({ tool_groups: null, skills: ["summarize"] })}
      />,
    );
    expect(screen.getByText("summarize")).toBeInTheDocument();
  });

  test("renders both tool_groups and skills badges together", () => {
    render(
      <AgentCard
        agent={makeAgent({ tool_groups: ["web"], skills: ["translate"] })}
      />,
    );
    expect(screen.getByText("web")).toBeInTheDocument();
    expect(screen.getByText("translate")).toBeInTheDocument();
  });

  test("does not render badges section when both tool_groups and skills are null", () => {
    render(
      <AgentCard agent={makeAgent({ tool_groups: null, skills: null })} />,
    );
    expect(screen.queryByText("web")).not.toBeInTheDocument();
    expect(screen.queryByText("summarize")).not.toBeInTheDocument();
  });

  test("does not render badges section when both tool_groups and skills are empty arrays", () => {
    render(<AgentCard agent={makeAgent({ tool_groups: [], skills: [] })} />);
    expect(screen.queryByText("web")).not.toBeInTheDocument();
    expect(screen.queryByText("summarize")).not.toBeInTheDocument();
  });

  // ── Chat button ──────────────────────────────────────────────────────────

  test("renders chat button", () => {
    render(<AgentCard agent={makeAgent()} />);
    expect(screen.getByTestId("agent-chat-button")).toBeInTheDocument();
    expect(screen.getByText("Chat")).toBeInTheDocument();
  });

  test("chat button navigates to the agent's new chat route", () => {
    render(<AgentCard agent={makeAgent({ name: "my-agent" })} />);
    fireEvent.click(screen.getByTestId("agent-chat-button"));
    expect(mockPush).toHaveBeenCalledWith(
      "/workspace/agents/my-agent/chats/new",
    );
  });

  // ── Export button ────────────────────────────────────────────────────────

  test("renders export button", () => {
    render(<AgentCard agent={makeAgent()} />);
    expect(screen.getByTestId("agent-export-button")).toBeInTheDocument();
  });

  test("export button has correct title attribute", () => {
    render(<AgentCard agent={makeAgent()} />);
    expect(screen.getByTestId("agent-export-button")).toHaveAttribute(
      "title",
      "导出",
    );
  });

  test("export button triggers exportAgent and shows success toast", async () => {
    const mockBlob = new Blob(["zip-data"], { type: "application/zip" });
    mockExportAgent.mockResolvedValue(mockBlob);

    render(<AgentCard agent={makeAgent({ name: "export-me" })} />);
    fireEvent.click(screen.getByTestId("agent-export-button"));

    await waitFor(() => {
      expect(mockExportAgent).toHaveBeenCalledWith("export-me");
    });
    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith("智能体已导出");
    });
  });

  test("export button shows error toast on failure", async () => {
    mockExportAgent.mockRejectedValue(new Error("Network error"));

    render(<AgentCard agent={makeAgent()} />);
    fireEvent.click(screen.getByTestId("agent-export-button"));

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("Network error");
    });
  });

  test("export button shows string error when non-Error thrown", async () => {
    mockExportAgent.mockRejectedValue("unknown failure");

    render(<AgentCard agent={makeAgent()} />);
    fireEvent.click(screen.getByTestId("agent-export-button"));

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("unknown failure");
    });
  });

  // ── Delete button visibility ─────────────────────────────────────────────

  test("renders delete button for non-read-only agent", () => {
    render(<AgentCard agent={makeAgent({ read_only: false })} />);
    expect(screen.getByTestId("agent-delete-button")).toBeInTheDocument();
  });

  test("does not render delete button for read-only agent", () => {
    render(<AgentCard agent={makeAgent({ read_only: true })} />);
    expect(screen.queryByTestId("agent-delete-button")).not.toBeInTheDocument();
  });

  test("delete button has correct title attribute", () => {
    render(<AgentCard agent={makeAgent()} />);
    expect(screen.getByTestId("agent-delete-button")).toHaveAttribute(
      "title",
      "Delete",
    );
  });

  // ── Delete dialog flow ───────────────────────────────────────────────────

  test("clicking delete button opens the delete confirmation dialog", async () => {
    render(<AgentCard agent={makeAgent()} />);
    fireEvent.click(screen.getByTestId("agent-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    expect(screen.getByText("Are you sure?")).toBeInTheDocument();
  });

  test("delete dialog shows cancel and confirm buttons", async () => {
    render(<AgentCard agent={makeAgent()} />);
    fireEvent.click(screen.getByTestId("agent-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    expect(screen.getByText("Cancel")).toBeInTheDocument();
    const deleteBtns = screen.getAllByText("Delete");
    expect(deleteBtns.length).toBeGreaterThanOrEqual(2);
  });

  test("clicking cancel closes the delete dialog", async () => {
    render(<AgentCard agent={makeAgent()} />);
    fireEvent.click(screen.getByTestId("agent-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Cancel"));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  test("confirming delete calls mutateAsync with agent name", async () => {
    mockMutateAsync.mockResolvedValue(undefined);

    render(<AgentCard agent={makeAgent({ name: "delete-me" })} />);
    fireEvent.click(screen.getByTestId("agent-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const dialog = screen.getByRole("dialog");
    const confirmBtn =
      dialog.querySelector('[data-variant="destructive"]') ??
      screen.getAllByText("Delete").pop();
    fireEvent.click(confirmBtn!);

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith("delete-me");
    });
  });

  test("successful delete shows success toast and closes dialog", async () => {
    mockMutateAsync.mockResolvedValue(undefined);

    render(<AgentCard agent={makeAgent({ name: "del-ok" })} />);
    fireEvent.click(screen.getByTestId("agent-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const dialog = screen.getByRole("dialog");
    const confirmBtn =
      dialog.querySelector('[data-variant="destructive"]') ??
      screen.getAllByText("Delete").pop();
    fireEvent.click(confirmBtn!);

    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith("Agent deleted");
    });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  test("delete failure shows error toast", async () => {
    mockMutateAsync.mockRejectedValue(new Error("Cannot delete"));

    render(<AgentCard agent={makeAgent()} />);
    fireEvent.click(screen.getByTestId("agent-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const dialog = screen.getByRole("dialog");
    const confirmBtn =
      dialog.querySelector('[data-variant="destructive"]') ??
      screen.getAllByText("Delete").pop();
    fireEvent.click(confirmBtn!);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("Cannot delete");
    });
  });

  test("delete failure with non-Error value shows string toast", async () => {
    mockMutateAsync.mockRejectedValue("string error");

    render(<AgentCard agent={makeAgent()} />);
    fireEvent.click(screen.getByTestId("agent-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const dialog = screen.getByRole("dialog");
    const confirmBtn =
      dialog.querySelector('[data-variant="destructive"]') ??
      screen.getAllByText("Delete").pop();
    fireEvent.click(confirmBtn!);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("string error");
    });
  });

  // ── Pending state ───────────────────────────────────────────────────────

  test("shows loading text on confirm button when delete is pending", async () => {
    mockDeletePending = true;

    render(<AgentCard agent={makeAgent()} />);
    fireEvent.click(screen.getByTestId("agent-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  test("cancel button is disabled when delete is pending", async () => {
    mockDeletePending = true;

    render(<AgentCard agent={makeAgent()} />);
    fireEvent.click(screen.getByTestId("agent-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const cancelBtn = screen.getByText("Cancel");
    expect(cancelBtn).toBeDisabled();
  });

  test("confirm button is disabled when delete is pending", async () => {
    mockDeletePending = true;

    render(<AgentCard agent={makeAgent()} />);
    fireEvent.click(screen.getByTestId("agent-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const loadingBtn = screen.getByText("Loading...");
    expect(loadingBtn).toBeDisabled();
  });

  // ── Edge cases ───────────────────────────────────────────────────────────

  test("agent with no optional fields renders basic card", () => {
    render(
      <AgentCard
        agent={makeAgent({
          description: "",
          model: null,
          tool_groups: null,
          skills: null,
          read_only: false,
        })}
      />,
    );
    expect(screen.getByTestId("agent-card")).toBeInTheDocument();
    expect(screen.getByText("test-agent")).toBeInTheDocument();
    expect(screen.getByTestId("agent-chat-button")).toBeInTheDocument();
    expect(screen.getByTestId("agent-export-button")).toBeInTheDocument();
    expect(screen.getByTestId("agent-delete-button")).toBeInTheDocument();
  });

  test("renders with many tool groups and skills", () => {
    const agent = makeAgent({
      tool_groups: ["group1", "group2", "group3", "group4"],
      skills: ["skill1", "skill2", "skill3"],
    });
    render(<AgentCard agent={agent} />);
    expect(screen.getByText("group1")).toBeInTheDocument();
    expect(screen.getByText("group4")).toBeInTheDocument();
    expect(screen.getByText("skill1")).toBeInTheDocument();
    expect(screen.getByText("skill3")).toBeInTheDocument();
  });
});
