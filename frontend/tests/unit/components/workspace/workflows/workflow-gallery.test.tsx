import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockPush = vi.fn();
let mockWorkflows: unknown[] = [];
let mockIsLoading = false;
let mockError: Error | null = null;

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      workflows: {
        title: "Workflows",
        description: "Manage your workflows",
        newWorkflow: "New Workflow",
        emptyTitle: "No workflows yet",
        emptyDescription: "Create your first workflow",
      },
      common: {
        loading: "Loading...",
        favoritesOnly: "Favorites",
        showAll: "Show All",
      },
    },
  }),
}));

vi.mock("@/core/workflows", () => ({
  useWorkflows: () => ({
    workflows: mockWorkflows,
    isLoading: mockIsLoading,
    error: mockError,
  }),
}));

vi.mock("@/components/workspace/workflows/workflow-card", () => ({
  WorkflowCard: ({ workflow }: { workflow: { name: string } }) => (
    <div data-testid="workflow-card">{workflow.name}</div>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let WorkflowGallery: typeof import("@/components/workspace/workflows/workflow-gallery").WorkflowGallery;

beforeEach(async () => {
  vi.clearAllMocks();
  mockWorkflows = [];
  mockIsLoading = false;
  mockError = null;
  const mod = await import("@/components/workspace/workflows/workflow-gallery");
  WorkflowGallery = mod.WorkflowGallery;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("WorkflowGallery", () => {
  test("renders the page title", () => {
    render(<WorkflowGallery />);
    expect(screen.getByText("Workflows")).toBeInTheDocument();
  });

  test("renders the page description", () => {
    render(<WorkflowGallery />);
    expect(screen.getByText("Manage your workflows")).toBeInTheDocument();
  });

  test("renders new workflow button", () => {
    render(<WorkflowGallery />);
    const buttons = screen.getAllByText("New Workflow");
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });

  test("shows empty state when no workflows", () => {
    render(<WorkflowGallery />);
    expect(screen.getByText("No workflows yet")).toBeInTheDocument();
    expect(screen.getByText("Create your first workflow")).toBeInTheDocument();
  });

  test("navigates to new workflow page when button clicked", async () => {
    const user = userEvent.setup();
    render(<WorkflowGallery />);
    const newButtons = screen.getAllByText("New Workflow");
    await user.click(newButtons[0]!);
    expect(mockPush).toHaveBeenCalledWith("/workspace/workflows/new");
  });

  test("shows loading state", () => {
    mockIsLoading = true;
    mockWorkflows = [];
    render(<WorkflowGallery />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  test("shows error state", () => {
    mockError = new Error("Connection failed");
    mockWorkflows = [];
    render(<WorkflowGallery />);
    expect(screen.getByText("Connection failed")).toBeInTheDocument();
  });

  test("renders workflow cards when workflows exist", () => {
    mockWorkflows = [{ name: "Workflow 1" }, { name: "Workflow 2" }];
    render(<WorkflowGallery />);
    expect(screen.getByText("Workflow 1")).toBeInTheDocument();
    expect(screen.getByText("Workflow 2")).toBeInTheDocument();
    const cards = screen.getAllByTestId("workflow-card");
    expect(cards).toHaveLength(2);
  });

  test("empty state New Workflow button navigates to new workflow page", async () => {
    const user = userEvent.setup();
    render(<WorkflowGallery />);
    const newButtons = screen.getAllByText("New Workflow");
    // There should be 2 buttons: header button (index 0) and empty state button (index 1)
    expect(newButtons.length).toBe(2);
    // Click the empty state button (second one)
    await user.click(newButtons[1]!);
    expect(mockPush).toHaveBeenCalledWith("/workspace/workflows/new");
  });

  test("filters workflows by search text", async () => {
    const user = userEvent.setup();
    mockWorkflows = [
      { name: "Deploy", description: "Production release" },
      { name: "Research", description: "Find source material" },
    ];
    render(<WorkflowGallery />);

    await user.type(screen.getByPlaceholderText("Workflows..."), "source");

    expect(screen.queryByText("Deploy")).not.toBeInTheDocument();
    expect(screen.getByText("Research")).toBeInTheDocument();
  });

  test("filters workflows to favorites and toggles back to all", async () => {
    const user = userEvent.setup();
    mockWorkflows = [
      { name: "Favorite Flow", description: "", is_favorited: true },
      { name: "Regular Flow", description: "", is_favorited: false },
    ];
    render(<WorkflowGallery />);

    await user.click(screen.getByRole("button", { name: /Favorites/ }));
    expect(screen.getByText("Favorite Flow")).toBeInTheDocument();
    expect(screen.queryByText("Regular Flow")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Show All/ }));
    expect(screen.getByText("Regular Flow")).toBeInTheDocument();
  });
});
