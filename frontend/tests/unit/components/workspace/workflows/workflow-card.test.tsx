import {
  render,
  screen,
  cleanup,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { WorkflowSummary } from "@/core/workflows";

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
vi.mock("@/core/workflows", () => ({
  useDeleteWorkflow: () => ({
    mutateAsync: mockMutateAsync,
    get isPending() {
      return mockDeletePending;
    },
  }),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: {
      workflows: {
        view: "View",
        deleteTitle: "Delete Workflow",
        deleteConfirm: (name: string) => `Delete "${name}"?`,
        deleteSuccess: "Workflow deleted",
        deleting: "Deleting...",
        unknown: "unknown",
        steps: (count: number) => `${count} steps`,
        inputs: (count: number) => `${count} inputs`,
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

function makeWorkflow(
  overrides: Partial<WorkflowSummary> = {},
): WorkflowSummary {
  return {
    name: "test-workflow",
    description: "A test workflow",
    version: "1.0",
    steps_count: 3,
    inputs: {
      prompt: {
        type: "string",
        required: true,
        default: null,
        description: "Input prompt",
      },
    },
    visibility: "private",
    owner_id: null,
    department_id: null,
    ...overrides,
  };
}

// ── Dynamic import ───────────────────────────────────────────────────────────

let WorkflowCard: (props: { workflow: WorkflowSummary }) => React.JSX.Element;

beforeEach(async () => {
  vi.clearAllMocks();
  mockDeletePending = false;
  const mod = await import("@/components/workspace/workflows/workflow-card");
  WorkflowCard = mod.WorkflowCard;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("WorkflowCard", () => {
  // ── Rendering ────────────────────────────────────────────────────────────

  test("renders the card with workflow name", () => {
    render(<WorkflowCard workflow={makeWorkflow()} />);
    expect(screen.getByTestId("workflow-card")).toBeInTheDocument();
    expect(screen.getByText("test-workflow")).toBeInTheDocument();
  });

  test("renders the description when provided", () => {
    render(
      <WorkflowCard
        workflow={makeWorkflow({ description: "Deploy pipeline" })}
      />,
    );
    expect(screen.getByText("Deploy pipeline")).toBeInTheDocument();
  });

  test("does not render description when description is empty string", () => {
    const { container } = render(
      <WorkflowCard workflow={makeWorkflow({ description: "" })} />,
    );
    const desc = container.querySelector(".line-clamp-2");
    expect(desc).toBeNull();
  });

  test("does not render description when description is falsy", () => {
    const { container } = render(
      <WorkflowCard
        workflow={makeWorkflow({ description: undefined as unknown as string })}
      />,
    );
    const desc = container.querySelector(".line-clamp-2");
    expect(desc).toBeNull();
  });

  test("renders version badge with version number", () => {
    render(<WorkflowCard workflow={makeWorkflow({ version: "2.1" })} />);
    expect(screen.getByText("v2.1")).toBeInTheDocument();
  });

  test("renders version badge with 'unknown' fallback when version is missing", () => {
    render(
      <WorkflowCard
        workflow={makeWorkflow({ version: undefined as unknown as string })}
      />,
    );
    expect(screen.getByText("vunknown")).toBeInTheDocument();
  });

  test("renders version badge with empty version (shows 'v' only)", () => {
    render(<WorkflowCard workflow={makeWorkflow({ version: "" })} />);
    // Empty string is not null/undefined, so ?? does not fallback
    expect(screen.getByText("v")).toBeInTheDocument();
  });

  // ── Steps & inputs badges ────────────────────────────────────────────────

  test("renders steps count badge", () => {
    render(<WorkflowCard workflow={makeWorkflow({ steps_count: 5 })} />);
    expect(screen.getByText("5 steps")).toBeInTheDocument();
  });

  test("renders steps count as 0 when steps_count is missing", () => {
    render(
      <WorkflowCard
        workflow={makeWorkflow({ steps_count: undefined as unknown as number })}
      />,
    );
    expect(screen.getByText("0 steps")).toBeInTheDocument();
  });

  test("renders steps count as 0 when steps_count is null", () => {
    render(
      <WorkflowCard
        workflow={makeWorkflow({ steps_count: null as unknown as number })}
      />,
    );
    expect(screen.getByText("0 steps")).toBeInTheDocument();
  });

  test("renders inputs count badge when inputs are provided", () => {
    render(
      <WorkflowCard
        workflow={makeWorkflow({
          inputs: {
            a: {
              type: "string",
              required: true,
              default: null,
              description: "",
            },
            b: { type: "number", required: false, default: 0, description: "" },
          },
        })}
      />,
    );
    expect(screen.getByText("2 inputs")).toBeInTheDocument();
  });

  test("renders inputs count badge for single input", () => {
    render(
      <WorkflowCard
        workflow={makeWorkflow({
          inputs: {
            x: {
              type: "string",
              required: true,
              default: null,
              description: "",
            },
          },
        })}
      />,
    );
    expect(screen.getByText("1 inputs")).toBeInTheDocument();
  });

  test("does not render inputs badge when inputs is empty object", () => {
    render(<WorkflowCard workflow={makeWorkflow({ inputs: {} })} />);
    expect(screen.queryByText(/inputs/)).not.toBeInTheDocument();
  });

  test("does not render inputs badge when inputs is null/undefined", () => {
    render(
      <WorkflowCard
        workflow={makeWorkflow({
          inputs: undefined as unknown as Record<string, never>,
        })}
      />,
    );
    expect(screen.queryByText(/inputs/)).not.toBeInTheDocument();
  });

  // ── Card click navigation ────────────────────────────────────────────────

  test("clicking the card navigates to workflow detail page", () => {
    render(<WorkflowCard workflow={makeWorkflow({ name: "my-flow" })} />);
    fireEvent.click(screen.getByTestId("workflow-card"));
    expect(mockPush).toHaveBeenCalledWith("/workspace/workflows/my-flow");
  });

  test("card has role='button' and tabIndex=0 for accessibility", () => {
    render(<WorkflowCard workflow={makeWorkflow()} />);
    const card = screen.getByTestId("workflow-card");
    expect(card).toHaveAttribute("role", "button");
    expect(card).toHaveAttribute("tabindex", "0");
  });

  test("pressing Enter on card triggers navigation", () => {
    render(<WorkflowCard workflow={makeWorkflow({ name: "kb-flow" })} />);
    fireEvent.keyDown(screen.getByTestId("workflow-card"), {
      key: "Enter",
    });
    expect(mockPush).toHaveBeenCalledWith("/workspace/workflows/kb-flow");
  });

  test("pressing Space on card triggers navigation", () => {
    render(<WorkflowCard workflow={makeWorkflow({ name: "space-flow" })} />);
    fireEvent.keyDown(screen.getByTestId("workflow-card"), {
      key: " ",
    });
    expect(mockPush).toHaveBeenCalledWith("/workspace/workflows/space-flow");
  });

  test("pressing other keys does not trigger navigation", () => {
    render(<WorkflowCard workflow={makeWorkflow()} />);
    fireEvent.keyDown(screen.getByTestId("workflow-card"), { key: "Tab" });
    fireEvent.keyDown(screen.getByTestId("workflow-card"), { key: "Escape" });
    fireEvent.keyDown(screen.getByTestId("workflow-card"), { key: "a" });
    expect(mockPush).not.toHaveBeenCalled();
  });

  // ── Run (View) button ────────────────────────────────────────────────────

  test("renders the view/run button", () => {
    render(<WorkflowCard workflow={makeWorkflow()} />);
    expect(screen.getByTestId("workflow-run-button")).toBeInTheDocument();
    expect(screen.getByText("View")).toBeInTheDocument();
  });

  test("clicking the view button navigates to workflow detail", () => {
    render(<WorkflowCard workflow={makeWorkflow({ name: "run-flow" })} />);
    fireEvent.click(screen.getByTestId("workflow-run-button"));
    expect(mockPush).toHaveBeenCalledWith("/workspace/workflows/run-flow");
  });

  test("view button click does not propagate to card", () => {
    render(<WorkflowCard workflow={makeWorkflow()} />);
    fireEvent.click(screen.getByTestId("workflow-run-button"));
    // Called once (from the button handler) not twice (card + button)
    expect(mockPush).toHaveBeenCalledTimes(1);
  });

  // ── Delete button ────────────────────────────────────────────────────────

  test("renders the delete button", () => {
    render(<WorkflowCard workflow={makeWorkflow()} />);
    expect(screen.getByTestId("workflow-delete-button")).toBeInTheDocument();
  });

  test("clicking delete button opens delete dialog", async () => {
    render(<WorkflowCard workflow={makeWorkflow()} />);
    fireEvent.click(screen.getByTestId("workflow-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    expect(screen.getByText("Delete Workflow")).toBeInTheDocument();
  });

  test("delete dialog shows confirmation message with workflow name", async () => {
    render(<WorkflowCard workflow={makeWorkflow({ name: "confirm-me" })} />);
    fireEvent.click(screen.getByTestId("workflow-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    expect(screen.getByText('Delete "confirm-me"?')).toBeInTheDocument();
  });

  test("delete button click stops propagation (does not navigate)", () => {
    render(<WorkflowCard workflow={makeWorkflow()} />);
    fireEvent.click(screen.getByTestId("workflow-delete-button"));
    expect(mockPush).not.toHaveBeenCalled();
  });

  // ── Delete dialog interactions ───────────────────────────────────────────

  test("clicking cancel in delete dialog closes it", async () => {
    render(<WorkflowCard workflow={makeWorkflow()} />);
    fireEvent.click(screen.getByTestId("workflow-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Cancel"));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  test("confirming delete calls mutateAsync with workflow name", async () => {
    mockMutateAsync.mockResolvedValue(undefined);

    render(<WorkflowCard workflow={makeWorkflow({ name: "del-flow" })} />);
    fireEvent.click(screen.getByTestId("workflow-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const dialog = screen.getByRole("dialog");
    const confirmBtn =
      dialog.querySelector('[data-variant="destructive"]') ??
      screen.getAllByText("Delete").pop();
    fireEvent.click(confirmBtn!);

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith("del-flow");
    });
  });

  test("successful delete shows success toast and closes dialog", async () => {
    mockMutateAsync.mockResolvedValue(undefined);

    render(<WorkflowCard workflow={makeWorkflow({ name: "ok-del" })} />);
    fireEvent.click(screen.getByTestId("workflow-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const dialog = screen.getByRole("dialog");
    const confirmBtn =
      dialog.querySelector('[data-variant="destructive"]') ??
      screen.getAllByText("Delete").pop();
    fireEvent.click(confirmBtn!);

    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith("Workflow deleted");
    });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  test("delete failure shows error toast", async () => {
    mockMutateAsync.mockRejectedValue(new Error("Permission denied"));

    render(<WorkflowCard workflow={makeWorkflow()} />);
    fireEvent.click(screen.getByTestId("workflow-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const dialog = screen.getByRole("dialog");
    const confirmBtn =
      dialog.querySelector('[data-variant="destructive"]') ??
      screen.getAllByText("Delete").pop();
    fireEvent.click(confirmBtn!);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("Permission denied");
    });
  });

  test("delete failure with non-Error value shows string toast", async () => {
    mockMutateAsync.mockRejectedValue("server error");

    render(<WorkflowCard workflow={makeWorkflow()} />);
    fireEvent.click(screen.getByTestId("workflow-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const dialog = screen.getByRole("dialog");
    const confirmBtn =
      dialog.querySelector('[data-variant="destructive"]') ??
      screen.getAllByText("Delete").pop();
    fireEvent.click(confirmBtn!);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("server error");
    });
  });

  // ── Pending state ───────────────────────────────────────────────────────

  test("shows deleting text on confirm button when delete is pending", async () => {
    mockDeletePending = true;

    render(<WorkflowCard workflow={makeWorkflow()} />);
    fireEvent.click(screen.getByTestId("workflow-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    expect(screen.getByText("Deleting...")).toBeInTheDocument();
  });

  test("cancel button is disabled when delete is pending", async () => {
    mockDeletePending = true;

    render(<WorkflowCard workflow={makeWorkflow()} />);
    fireEvent.click(screen.getByTestId("workflow-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const cancelBtn = screen.getByText("Cancel");
    expect(cancelBtn).toBeDisabled();
  });

  test("confirm button is disabled when delete is pending", async () => {
    mockDeletePending = true;

    render(<WorkflowCard workflow={makeWorkflow()} />);
    fireEvent.click(screen.getByTestId("workflow-delete-button"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const deletingBtn = screen.getByText("Deleting...");
    expect(deletingBtn).toBeDisabled();
  });

  // ── Edge cases ───────────────────────────────────────────────────────────

  test("workflow with all optional fields missing still renders", () => {
    render(
      <WorkflowCard
        workflow={makeWorkflow({
          description: "",
          version: undefined as unknown as string,
          steps_count: undefined as unknown as number,
          inputs: undefined as unknown as Record<string, never>,
        })}
      />,
    );
    expect(screen.getByTestId("workflow-card")).toBeInTheDocument();
    expect(screen.getByText("test-workflow")).toBeInTheDocument();
    expect(screen.getByTestId("workflow-run-button")).toBeInTheDocument();
    expect(screen.getByTestId("workflow-delete-button")).toBeInTheDocument();
  });
});
