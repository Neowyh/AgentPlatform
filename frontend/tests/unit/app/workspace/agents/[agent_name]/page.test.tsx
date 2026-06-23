import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ agent_name: "test-agent" }),
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("next/link", () => {
  const React = require("react");
  return {
    __esModule: true,
    default: React.forwardRef(({ children, href, ...props }: any, ref: any) =>
      React.createElement("a", { ...props, ref, href }, children),
    ),
  };
});

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      common: { loading: "Loading..." },
      agents: { backToGallery: "Back" },
    },
  }),
}));

const mockUseAgent = vi.fn();
vi.mock("@/core/agents", () => ({
  useAgent: (...args: unknown[]) => mockUseAgent(...args),
}));

vi.mock("@/components/workspace/workspace-breadcrumb", () => ({
  WorkspaceBreadcrumb: () => <div data-testid="breadcrumb" />,
}));

// ---------------------------------------------------------------------------
// Import component after mocks
// ---------------------------------------------------------------------------

import AgentDetailPage from "@/app/workspace/agents/[agent_name]/page";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const fullAgent = {
  name: "test-agent",
  description: "A test agent",
  model: "gpt-4",
  tool_groups: ["bash", "web"],
  skills: ["web-search", "code-gen"],
  soul: "Be helpful and concise",
  read_only: false,
};

const minimalAgent = {
  name: "minimal-agent",
  description: null,
  model: null,
  tool_groups: [],
  skills: [],
  soul: null,
  read_only: true,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AgentDetailPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  // ── Loading state ──────────────────────────────────────────────────

  test("shows loading state when isLoading is true", () => {
    mockUseAgent.mockReturnValue({ agent: null, isLoading: true, error: null });
    render(<AgentDetailPage />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  test("does not render agent content during loading", () => {
    mockUseAgent.mockReturnValue({ agent: null, isLoading: true, error: null });
    render(<AgentDetailPage />);
    expect(screen.queryByText("Configuration")).not.toBeInTheDocument();
  });

  // ── Error state ────────────────────────────────────────────────────

  test("shows error message when error is present", () => {
    mockUseAgent.mockReturnValue({
      agent: null,
      isLoading: false,
      error: new Error("Not found"),
    });
    render(<AgentDetailPage />);
    expect(screen.getByText("Not found")).toBeInTheDocument();
  });

  test("shows 'Agent not found' when no error and no agent", () => {
    mockUseAgent.mockReturnValue({
      agent: null,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.getByText("Agent not found")).toBeInTheDocument();
  });

  test("renders back button in error state", () => {
    mockUseAgent.mockReturnValue({
      agent: null,
      isLoading: false,
      error: new Error("fail"),
    });
    render(<AgentDetailPage />);
    expect(screen.getByText("Back")).toBeInTheDocument();
  });

  test("back button navigates to /workspace/agents", async () => {
    const user = userEvent.setup();
    mockUseAgent.mockReturnValue({
      agent: null,
      isLoading: false,
      error: new Error("fail"),
    });
    render(<AgentDetailPage />);
    await user.click(screen.getByText("Back"));
    expect(mockPush).toHaveBeenCalledWith("/workspace/agents");
  });

  // ── Success state: full agent ──────────────────────────────────────

  test("renders agent name and description", () => {
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.getByText("test-agent")).toBeInTheDocument();
    expect(screen.getByText("A test agent")).toBeInTheDocument();
  });

  test("renders model badge", () => {
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    const badges = screen.getAllByText("gpt-4");
    expect(badges.length).toBeGreaterThanOrEqual(1);
  });

  test("renders tool groups", () => {
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.getByText("bash")).toBeInTheDocument();
    expect(screen.getByText("web")).toBeInTheDocument();
  });

  test("renders skills with sparkle icon", () => {
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.getByText("web-search")).toBeInTheDocument();
    expect(screen.getByText("code-gen")).toBeInTheDocument();
  });

  test("renders SOUL.md section", () => {
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.getByText("SOUL.md")).toBeInTheDocument();
    expect(screen.getByText("Be helpful and concise")).toBeInTheDocument();
  });

  test("renders configuration section", () => {
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.getByText("Configuration")).toBeInTheDocument();
  });

  test("renders quick actions section", () => {
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.getByText("Start Chat")).toBeInTheDocument();
    expect(screen.getByText("Edit Configuration")).toBeInTheDocument();
  });

  test("renders edit agent button in header", () => {
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    const editButtons = screen.getAllByText("Edit Agent");
    expect(editButtons.length).toBeGreaterThanOrEqual(1);
  });

  test("renders stats cards", () => {
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.getByText("Conversations")).toBeInTheDocument();
    expect(screen.getByText("Token Usage")).toBeInTheDocument();
    expect(screen.getByText("Active Days")).toBeInTheDocument();
  });

  test("renders breadcrumb", () => {
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.getByTestId("breadcrumb")).toBeInTheDocument();
  });

  // ── Minimal agent (no optionals) ───────────────────────────────────

  test("renders agent without description", () => {
    mockUseAgent.mockReturnValue({
      agent: minimalAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.getByText("minimal-agent")).toBeInTheDocument();
    // Description should not be rendered
    expect(screen.queryByText("A test agent")).not.toBeInTheDocument();
  });

  test("shows 'Default model' when model is null", () => {
    mockUseAgent.mockReturnValue({
      agent: minimalAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.getByText("Default model")).toBeInTheDocument();
  });

  test("does not render model badge when model is null", () => {
    mockUseAgent.mockReturnValue({
      agent: minimalAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    // No badge for null model
    expect(screen.queryByText("null")).not.toBeInTheDocument();
  });

  test("renders 'Template' badge for read_only agent", () => {
    mockUseAgent.mockReturnValue({
      agent: minimalAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.getByText("Template")).toBeInTheDocument();
  });

  test("does not render tool groups when empty", () => {
    mockUseAgent.mockReturnValue({
      agent: minimalAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.queryByText("Tool Groups")).not.toBeInTheDocument();
  });

  test("does not render skills when empty", () => {
    mockUseAgent.mockReturnValue({
      agent: minimalAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.queryByText("Skills")).not.toBeInTheDocument();
  });

  test("does not render SOUL.md when soul is null", () => {
    mockUseAgent.mockReturnValue({
      agent: minimalAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.queryByText("SOUL.md")).not.toBeInTheDocument();
  });

  // ── Navigation ─────────────────────────────────────────────────────

  test("edit link in header has correct href", () => {
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    const editLinks = screen.getAllByText("Edit Agent");
    // The first edit link should point to the edit page
    const editLink = editLinks[0]!.closest("a");
    expect(editLink).toHaveAttribute(
      "href",
      "/workspace/agents/test-agent/edit",
    );
  });

  test("start chat link has correct href", () => {
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    const startChatLink = screen.getByText("Start Chat").closest("a");
    expect(startChatLink).toHaveAttribute(
      "href",
      "/workspace/agents/test-agent/chats/new",
    );
  });

  test("back arrow button navigates to /workspace/agents", async () => {
    const user = userEvent.setup();
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    // The back arrow button - it's the first ghost button
    const backButtons = screen.getAllByRole("button");
    await user.click(backButtons[0]!);
    expect(mockPush).toHaveBeenCalledWith("/workspace/agents");
  });

  // ── Agent with tool groups and skills ──────────────────────────────

  test("renders tool groups section title", () => {
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.getByText("Tool Groups")).toBeInTheDocument();
  });

  test("renders skills section title", () => {
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.getByText("Skills")).toBeInTheDocument();
  });

  test("renders model in configuration section", () => {
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.getByText("Model")).toBeInTheDocument();
  });

  // ── API call ───────────────────────────────────────────────────────

  test("calls useAgent with agent_name param", () => {
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(mockUseAgent).toHaveBeenCalledWith("test-agent");
  });

  // ── Agent with empty tool_groups but non-null ──────────────────────

  test("hides tool groups when array is empty", () => {
    mockUseAgent.mockReturnValue({
      agent: { ...fullAgent, tool_groups: [] },
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.queryByText("Tool Groups")).not.toBeInTheDocument();
  });

  test("hides skills when array is empty", () => {
    mockUseAgent.mockReturnValue({
      agent: { ...fullAgent, skills: [] },
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.queryByText("Skills")).not.toBeInTheDocument();
  });

  // ── read_only false agent should not show Template badge ───────────

  test("does not show Template badge when read_only is false", () => {
    mockUseAgent.mockReturnValue({
      agent: fullAgent,
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.queryByText("Template")).not.toBeInTheDocument();
  });

  // ── Description conditionally hidden ───────────────────────────────

  test("renders description when it exists", () => {
    mockUseAgent.mockReturnValue({
      agent: { ...fullAgent, description: "Custom description" },
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(screen.getByText("Custom description")).toBeInTheDocument();
  });
});
