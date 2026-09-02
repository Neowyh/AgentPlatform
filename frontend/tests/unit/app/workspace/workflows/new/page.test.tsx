import {
  render,
  screen,
  cleanup,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const { mockPush, mockMutateAsync, mockValidateYaml } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockMutateAsync: vi.fn(),
  mockValidateYaml: vi.fn().mockReturnValue([]),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "dark" }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      workflows: {
        newWorkflow: "New Workflow",
        createSubtitle: "Create a new workflow",
        yamlEditor: "YAML Editor",
        created: "Workflow created",
        creating: "Creating...",
      },
      common: { loading: "Loading...", cancel: "Cancel", save: "Save" },
    },
  }),
}));

vi.mock("@/core/workflows", () => ({
  useCreateWorkflow: () => ({
    mutateAsync: (...args: any[]) => mockMutateAsync(...args),
    isPending: false,
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
  Alert: ({ children, ...props }: any) => (
    <div data-testid="alert" {...props}>
      {children}
    </div>
  ),
  AlertDescription: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: any) => (
    <button {...props}>{children}</button>
  ),
}));

import NewWorkflowPage from "@/app/workspace/workflows/new/page";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("NewWorkflowPage", () => {
  beforeEach(() => {
    mockValidateYaml.mockReturnValue([]);
    mockMutateAsync.mockResolvedValue({});
  });

  test("renders page title", () => {
    render(<NewWorkflowPage />);
    const elements = screen.getAllByText("New Workflow");
    expect(elements.length).toBeGreaterThanOrEqual(1);
  });

  test("renders YAML editor", () => {
    render(<NewWorkflowPage />);
    expect(screen.getByTestId("code-editor")).toBeInTheDocument();
  });

  test("renders save button with save action text", () => {
    render(<NewWorkflowPage />);
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });

  test("renders cancel button", () => {
    render(<NewWorkflowPage />);
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });

  test("renders breadcrumb", () => {
    render(<NewWorkflowPage />);
    expect(screen.getByTestId("breadcrumb")).toBeInTheDocument();
  });

  test("renders subtitle", () => {
    render(<NewWorkflowPage />);
    expect(screen.getByText("Create a new workflow")).toBeInTheDocument();
  });

  test("renders YAML editor label", () => {
    render(<NewWorkflowPage />);
    expect(screen.getByText("YAML Editor")).toBeInTheDocument();
  });

  test("navigates back when cancel is clicked", () => {
    render(<NewWorkflowPage />);
    fireEvent.click(screen.getByText("Cancel"));
    expect(mockPush).toHaveBeenCalledWith("/workspace/workflows");
  });

  test("navigates back when back button is clicked", () => {
    render(<NewWorkflowPage />);
    const backButton = screen.getByRole("button", { name: "" });
    fireEvent.click(backButton);
    expect(mockPush).toHaveBeenCalledWith("/workspace/workflows");
  });

  test("displays validation errors when validateYaml returns errors", () => {
    mockValidateYaml.mockReturnValue([
      "Missing 'name' field",
      "Missing 'steps' field",
    ]);

    render(<NewWorkflowPage />);

    const editor = screen.getByTestId("code-editor");
    fireEvent.change(editor, { target: { value: "invalid: yaml" } });

    expect(screen.getByText("Missing 'name' field")).toBeInTheDocument();
    expect(screen.getByText("Missing 'steps' field")).toBeInTheDocument();
  });

  test("hides validation errors when validateYaml returns empty array", () => {
    mockValidateYaml.mockReturnValue([]);

    render(<NewWorkflowPage />);

    expect(screen.queryByTestId("alert")).not.toBeInTheDocument();
  });

  test("calls createWorkflow on save with valid YAML", async () => {
    mockValidateYaml.mockReturnValue([]);

    render(<NewWorkflowPage />);

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalled();
    });
  });

  test("navigates to workflows after successful save", async () => {
    mockValidateYaml.mockReturnValue([]);
    mockMutateAsync.mockResolvedValue({});

    render(<NewWorkflowPage />);

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/workspace/workflows");
    });
  });

  test("does not save when validation errors exist", async () => {
    mockValidateYaml.mockReturnValue(["Missing name"]);

    render(<NewWorkflowPage />);

    const editor = screen.getByTestId("code-editor");
    fireEvent.change(editor, { target: { value: "bad yaml" } });

    expect(mockMutateAsync).not.toHaveBeenCalled();
  });

  test("editor has default YAML content", () => {
    render(<NewWorkflowPage />);
    const editor = screen.getByTestId("code-editor");
    expect((editor as HTMLInputElement).value).toContain("name: my-workflow");
    expect((editor as HTMLInputElement).value).toContain("name: code-dev");
    expect((editor as HTMLInputElement).value).toContain("nodes:");
  });

  test("updates content when editor value changes", () => {
    render(<NewWorkflowPage />);
    const editor = screen.getByTestId("code-editor");
    fireEvent.change(editor, {
      target: { value: "name: new-workflow\nsteps: []" },
    });
    expect((editor as HTMLTextAreaElement).value).toBe(
      "name: new-workflow\nsteps: []",
    );
  });

  test("shows error toast when save fails with Error", async () => {
    const { toast } = await import("sonner");
    mockValidateYaml.mockReturnValue([]);
    mockMutateAsync.mockRejectedValue(new Error("Create failed"));

    render(<NewWorkflowPage />);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Create failed");
    });
  });

  test("shows error toast when save fails with non-Error", async () => {
    const { toast } = await import("sonner");
    mockValidateYaml.mockReturnValue([]);
    mockMutateAsync.mockRejectedValue("raw string error");

    render(<NewWorkflowPage />);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("raw string error");
    });
  });
});
