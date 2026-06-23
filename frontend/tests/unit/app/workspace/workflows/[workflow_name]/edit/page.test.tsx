import {
  render,
  screen,
  cleanup,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const {
  mockPush,
  mockMutateAsync,
  mockValidateYaml,
  mockUseWorkflow,
  mockIsPending,
  mockResolvedTheme,
} = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockMutateAsync: vi.fn(),
  mockValidateYaml: vi.fn().mockReturnValue([]),
  mockUseWorkflow: vi.fn().mockReturnValue({
    workflow: { name: "test-workflow", yaml_content: "name: test\nsteps: []" },
    isLoading: false,
  }),
  mockIsPending: { value: false },
  mockResolvedTheme: { value: "dark" as string },
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ workflow_name: "test-workflow" }),
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: mockResolvedTheme.value }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      workflows: {
        edit: "Edit Workflow",
        yamlEditor: "YAML Editor",
        saveChanges: "Save Changes",
        saving: "Saving...",
        updated: "Workflow updated",
        notFound: "Not found",
        backToWorkflows: "Back",
      },
      common: { loading: "Loading...", cancel: "Cancel" },
    },
  }),
}));

vi.mock("@/core/workflows", () => ({
  useWorkflow: (...args: any[]) => mockUseWorkflow(...args),
  useUpdateWorkflow: () => ({
    mutateAsync: (...args: any[]) => mockMutateAsync(...args),
    get isPending() {
      return mockIsPending.value;
    },
  }),
}));

vi.mock("@/core/workflows/validate", () => ({
  validateYaml: (...args: any[]) => mockValidateYaml(...args),
}));

vi.mock("@uiw/react-codemirror", () => ({
  __esModule: true,
  default: ({ value, onChange }: any) => (
    <textarea
      data-testid="code-editor"
      value={value}
      onChange={(e: any) => onChange(e.target.value)}
    />
  ),
}));

vi.mock("@codemirror/lang-yaml", () => ({ yaml: () => [] }));
vi.mock("@uiw/codemirror-theme-basic", () => ({ basicLightInit: () => ({}) }));
vi.mock("@uiw/codemirror-theme-monokai", () => ({ monokaiInit: () => ({}) }));

vi.mock("@/components/workspace/workspace-breadcrumb", () => ({
  WorkspaceBreadcrumb: () => <div data-testid="breadcrumb" />,
}));

vi.mock("@/components/ui/alert", () => ({
  Alert: ({ children }: any) => <div data-testid="alert">{children}</div>,
  AlertDescription: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: any) => (
    <button {...props}>{children}</button>
  ),
}));

import WorkflowEditPage from "@/app/workspace/workflows/[workflow_name]/edit/page";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("WorkflowEditPage", () => {
  beforeEach(() => {
    mockUseWorkflow.mockReturnValue({
      workflow: {
        name: "test-workflow",
        yaml_content: "name: test\nsteps: []",
      },
      isLoading: false,
    });
    mockValidateYaml.mockReturnValue([]);
    mockMutateAsync.mockResolvedValue({});
    mockIsPending.value = false;
  });

  test("renders page title", () => {
    render(<WorkflowEditPage />);
    expect(screen.getByText("Edit Workflow")).toBeInTheDocument();
  });

  test("renders workflow name", () => {
    render(<WorkflowEditPage />);
    expect(screen.getByText("test-workflow")).toBeInTheDocument();
  });

  test("renders YAML editor with workflow content", () => {
    render(<WorkflowEditPage />);
    const editor = screen.getByTestId("code-editor");
    expect((editor as HTMLInputElement).value).toBe("name: test\nsteps: []");
  });

  test("renders save button", () => {
    render(<WorkflowEditPage />);
    expect(screen.getByText("Save Changes")).toBeInTheDocument();
  });

  test("renders cancel button", () => {
    render(<WorkflowEditPage />);
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });

  test("shows loading state", () => {
    mockUseWorkflow.mockReturnValue({ workflow: null, isLoading: true });
    render(<WorkflowEditPage />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  test("shows not found state", () => {
    mockUseWorkflow.mockReturnValue({ workflow: null, isLoading: false });
    render(<WorkflowEditPage />);
    expect(screen.getByText("Not found")).toBeInTheDocument();
  });

  test("renders back button in not found state", () => {
    mockUseWorkflow.mockReturnValue({ workflow: null, isLoading: false });
    render(<WorkflowEditPage />);
    expect(screen.getByText("Back")).toBeInTheDocument();
  });

  test("navigates to workflows list from not found back button", () => {
    mockUseWorkflow.mockReturnValue({ workflow: null, isLoading: false });
    render(<WorkflowEditPage />);
    fireEvent.click(screen.getByText("Back"));
    expect(mockPush).toHaveBeenCalledWith("/workspace/workflows");
  });

  test("renders breadcrumb", () => {
    render(<WorkflowEditPage />);
    expect(screen.getByTestId("breadcrumb")).toBeInTheDocument();
  });

  test("renders YAML editor label", () => {
    render(<WorkflowEditPage />);
    expect(screen.getByText("YAML Editor")).toBeInTheDocument();
  });

  test("navigates back when cancel is clicked", () => {
    render(<WorkflowEditPage />);
    fireEvent.click(screen.getByText("Cancel"));
    expect(mockPush).toHaveBeenCalledWith("/workspace/workflows/test-workflow");
  });

  test("navigates back when back button is clicked", () => {
    render(<WorkflowEditPage />);
    // The back button is the first button rendered (ArrowLeftIcon)
    const buttons = screen.getAllByRole("button");
    // First button is the back button (ghost variant with ArrowLeftIcon)
    fireEvent.click(buttons[0]!);
    expect(mockPush).toHaveBeenCalledWith("/workspace/workflows/test-workflow");
  });

  test("displays validation errors", () => {
    mockValidateYaml.mockReturnValue(["Missing name field", "Invalid YAML"]);

    render(<WorkflowEditPage />);
    const editor = screen.getByTestId("code-editor");
    fireEvent.change(editor, { target: { value: "bad yaml" } });

    expect(screen.getByText("Missing name field")).toBeInTheDocument();
    expect(screen.getByText("Invalid YAML")).toBeInTheDocument();
  });

  test("hides alert when no validation errors", () => {
    mockValidateYaml.mockReturnValue([]);
    render(<WorkflowEditPage />);
    expect(screen.queryByTestId("alert")).not.toBeInTheDocument();
  });

  test("calls updateWorkflow on save", async () => {
    mockValidateYaml.mockReturnValue([]);

    render(<WorkflowEditPage />);
    fireEvent.click(screen.getByText("Save Changes"));

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        name: "test-workflow",
        data: { yaml_content: "name: test\nsteps: []" },
      });
    });
  });

  test("navigates to workflow detail after save", async () => {
    mockValidateYaml.mockReturnValue([]);
    mockMutateAsync.mockResolvedValue({});

    render(<WorkflowEditPage />);
    fireEvent.click(screen.getByText("Save Changes"));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith(
        "/workspace/workflows/test-workflow",
      );
    });
  });

  test("shows error toast when save fails", async () => {
    const { toast } = await import("sonner");
    mockValidateYaml.mockReturnValue([]);
    mockMutateAsync.mockRejectedValue(new Error("Save failed"));

    render(<WorkflowEditPage />);
    fireEvent.click(screen.getByText("Save Changes"));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Save failed");
    });
  });

  test("does not save when validation errors exist", async () => {
    mockValidateYaml.mockReturnValue(["Missing name"]);

    render(<WorkflowEditPage />);
    const editor = screen.getByTestId("code-editor");
    fireEvent.change(editor, { target: { value: "bad" } });

    expect(mockMutateAsync).not.toHaveBeenCalled();
  });

  test("not found state does not render loading", () => {
    mockUseWorkflow.mockReturnValue({ workflow: null, isLoading: false });
    render(<WorkflowEditPage />);
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
  });

  test("loading state does not render not found", () => {
    mockUseWorkflow.mockReturnValue({ workflow: null, isLoading: true });
    render(<WorkflowEditPage />);
    expect(screen.queryByText("Not found")).not.toBeInTheDocument();
  });

  test("shows error toast when save fails with non-Error throw", async () => {
    const { toast } = await import("sonner");
    mockValidateYaml.mockReturnValue([]);
    mockMutateAsync.mockRejectedValue("raw string error");

    render(<WorkflowEditPage />);
    fireEvent.click(screen.getByText("Save Changes"));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("raw string error");
    });
  });

  test("shows Saving... text when update is pending", () => {
    mockIsPending.value = true;
    render(<WorkflowEditPage />);
    expect(screen.getByText("Saving...")).toBeInTheDocument();
  });

  test("handleSave returns early when validation errors exist (line 64)", async () => {
    mockValidateYaml.mockReturnValue(["Missing name field"]);

    render(<WorkflowEditPage />);
    fireEvent.click(screen.getByText("Save Changes"));

    // mutateAsync should NOT be called because validation errors cause early return
    await waitFor(() => {
      expect(mockMutateAsync).not.toHaveBeenCalled();
    });
  });

  test("renders with light theme (line 165)", () => {
    mockResolvedTheme.value = "light";
    render(<WorkflowEditPage />);
    expect(screen.getByText("Edit Workflow")).toBeInTheDocument();
    mockResolvedTheme.value = "dark";
  });
});
