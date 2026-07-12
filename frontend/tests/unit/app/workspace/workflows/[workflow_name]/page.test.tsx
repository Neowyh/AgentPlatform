import {
  render,
  screen,
  fireEvent,
  within,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import WorkflowDetailPage from "@/app/workspace/workflows/[workflow_name]/page";
import type {
  WorkflowDetail,
  WorkflowRunResult,
  RunStatus,
} from "@/core/workflows";

/* ------------------------------------------------------------------ */
/*  Default workflow fixture                                           */
/* ------------------------------------------------------------------ */

const defaultWorkflow: WorkflowDetail = {
  name: "test-workflow",
  description: "A test workflow",
  version: "1.0",
  steps: [
    { id: "step1", type: "agent", agent: "test-agent", prompt: "Do something" },
  ],
  steps_count: 1,
  inputs: {
    topic: {
      type: "string",
      required: true,
      description: "Research topic",
      default: undefined,
    },
  },
  yaml_content: "name: test-workflow\nsteps: []",
  visibility: "private",
  owner_id: null,
  department_id: null,
};

/* ------------------------------------------------------------------ */
/*  Mutable mock references                                            */
/* ------------------------------------------------------------------ */

let mockWorkflow: WorkflowDetail | null = defaultWorkflow;
let mockIsLoading = false;
let mockError: Error | null = null;
let mockMutateAsync: ReturnType<typeof vi.fn>;
let mockIsPending = false;
let mockRunStatus: RunStatus | null = null;
let mockPush: ReturnType<typeof vi.fn>;
const mockCreateVisibilityApplication = vi.fn();

/* ------------------------------------------------------------------ */
/*  Module mocks                                                       */
/* ------------------------------------------------------------------ */

vi.mock("next/navigation", () => ({
  useParams: () => ({ workflow_name: "test-workflow" }),
  useRouter: () => ({ push: (...args: any[]) => (mockPush as any)(...args) }),
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

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: () => ({
    user: { id: "user-1", name: "Test User", email: "test@example.com" },
    isAuthenticated: true,
    isLoading: false,
    logout: vi.fn(),
    refreshUser: vi.fn(),
  }),
}));

vi.mock("@/core/visibility-applications/api", () => ({
  createVisibilityApplication: (...args: any[]) =>
    mockCreateVisibilityApplication(...args),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      workflows: {
        notFound: "Not found",
        backToWorkflows: "Back",
        edit: "Edit",
        run: "Run",
        runDialog: "Run Workflow",
        runDialogDescription: "Configure inputs",
        stepsTitle: (n: number) => `${n} Steps`,
        stepsDescription: "Workflow steps",
        noSteps: "No steps",
        inputsTitle: "Inputs",
        inputsDescription: "Workflow inputs",
        required: "Required",
        yamlDefinition: "YAML Definition",
        started: "Workflow started",
        starting: "Starting...",
        runStatus: "Run Status",
        runId: "Run ID: ",
        noInputs: "No inputs required",
        defaultPrefix: "Default: ",
        enterInput: (k: string) => `Enter ${k}`,
        requiredMissing: (k: string) => `${k} is required`,
        visibility: "Visibility",
        export: "Export",
        exportSuccess: "Export successful",
        exportFailed: "Export failed",
        applyVisibility: "Apply Visibility Change",
        applyVisibilityDescription:
          "Submit an application to change the visibility level",
        currentTargetVisibility: "Current Visibility",
        targetVisibility: "Target Visibility",
        private: "Private",
        department: "Department",
        public: "Public",
        reason: "Reason",
        reasonPlaceholder: "Enter your reason...",
        reasonRequired: "Please enter a reason",
        submitting: "Submitting...",
        submit: "Submit Application",
        applicationSubmitted: "Application submitted",
        notOwner: "You are not the owner",
      },
      common: { loading: "Loading...", cancel: "Cancel" },
    },
  }),
}));

vi.mock("@/core/workflows", () => ({
  useWorkflow: () => ({
    workflow: mockWorkflow,
    isLoading: mockIsLoading,
    error: mockError,
  }),
  useRunWorkflow: () => ({
    mutateAsync: mockMutateAsync,
    isPending: mockIsPending,
  }),
  useRunStatus: () => ({
    runStatus: mockRunStatus,
  }),
}));

vi.mock("@/components/workspace/workspace-breadcrumb", () => ({
  WorkspaceBreadcrumb: () => <div data-testid="breadcrumb" />,
}));

vi.mock("@/components/ui/card", () => ({
  Card: ({ children }: any) => <div data-testid="card">{children}</div>,
  CardContent: ({ children }: any) => (
    <div data-testid="card-content">{children}</div>
  ),
  CardDescription: ({ children }: any) => (
    <div data-testid="card-description">{children}</div>
  ),
  CardHeader: ({ children }: any) => (
    <div data-testid="card-header">{children}</div>
  ),
  CardTitle: ({ children }: any) => (
    <div data-testid="card-title">{children}</div>
  ),
}));

vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children, open, onOpenChange }: any) =>
    open ? (
      <div data-testid="dialog" data-open="true">
        {children}
      </div>
    ) : null,
  DialogContent: ({ children }: any) => (
    <div data-testid="dialog-content">{children}</div>
  ),
  DialogDescription: ({ children }: any) => (
    <div data-testid="dialog-description">{children}</div>
  ),
  DialogFooter: ({ children }: any) => (
    <div data-testid="dialog-footer">{children}</div>
  ),
  DialogHeader: ({ children }: any) => (
    <div data-testid="dialog-header">{children}</div>
  ),
  DialogTitle: ({ children }: any) => (
    <div data-testid="dialog-title">{children}</div>
  ),
}));

vi.mock("@/components/ui/badge", () => ({
  Badge: ({ children, variant, className, ...props }: any) => (
    <span
      data-testid="badge"
      data-variant={variant}
      className={className}
      {...props}
    >
      {children}
    </span>
  ),
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    variant,
    onClick,
    disabled,
    asChild,
    ...props
  }: any) => (
    <button
      data-testid="button"
      data-variant={variant}
      onClick={onClick}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  ),
}));

vi.mock("@/components/ui/input", () => ({
  Input: (props: any) => <input data-testid="input" {...props} />,
}));

vi.mock("@/components/ui/label", () => ({
  Label: ({ children, htmlFor, ...props }: any) => (
    <label data-testid="label" htmlFor={htmlFor} {...props}>
      {children}
    </label>
  ),
}));

/* ------------------------------------------------------------------ */
/*  Import component under test (after mocks)                          */
/* ------------------------------------------------------------------ */

import { toast } from "sonner";

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

/** Find the Run button (not the ghost back button, not the outline edit link) */
function findRunButton(): HTMLElement {
  return screen
    .getAllByTestId("button")
    .find(
      (b) =>
        b.textContent?.includes("Run") &&
        b.getAttribute("data-variant") !== "ghost" &&
        b.getAttribute("data-variant") !== "outline",
    )!;
}

/** Find the submit button inside the dialog footer */
function findDialogSubmitButton(): HTMLElement {
  const dialog = screen.getByTestId("dialog");
  const footer = within(dialog).getByTestId("dialog-footer");
  const buttons = within(footer).getAllByTestId("button");
  return buttons.find(
    (b) => b.textContent === "Run" || b.textContent === "Starting...",
  )!;
}

/**
 * Trigger a successful run through the UI to set `activeRun` state,
 * so the run status card becomes visible.
 */
async function triggerSuccessfulRun(
  runResult: WorkflowRunResult,
  inputValue = "test-value",
) {
  mockMutateAsync = vi.fn().mockResolvedValue(runResult);
  const user = userEvent.setup();
  render(<WorkflowDetailPage />);
  await user.click(findRunButton());
  const input = screen.getByTestId("input");
  await user.type(input, inputValue);
  await user.click(findDialogSubmitButton());
  await waitFor(() => {
    expect(toast.success).toHaveBeenCalledWith("Workflow started");
  });
}

/* ------------------------------------------------------------------ */
/*  Test setup                                                         */
/* ------------------------------------------------------------------ */

beforeEach(() => {
  mockWorkflow = { ...defaultWorkflow };
  mockIsLoading = false;
  mockError = null;
  mockMutateAsync = vi.fn();
  mockIsPending = false;
  mockRunStatus = null;
  mockPush = vi.fn();
  mockCreateVisibilityApplication.mockReset().mockResolvedValue({
    id: "application-1",
  });
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:workflow");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
});

afterEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

/* ================================================================== */
/*  Tests                                                              */
/* ================================================================== */

describe("WorkflowDetailPage", () => {
  /* ---------- Breadcrumb ---------- */
  describe("breadcrumb", () => {
    test("renders WorkspaceBreadcrumb", () => {
      render(<WorkflowDetailPage />);
      expect(screen.getByTestId("breadcrumb")).toBeInTheDocument();
    });
  });

  /* ---------- Loading state ---------- */
  describe("loading state", () => {
    test("shows loading text when isLoading is true", () => {
      mockIsLoading = true;
      mockWorkflow = null;
      render(<WorkflowDetailPage />);
      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });

    test("does not render main content when loading", () => {
      mockIsLoading = true;
      mockWorkflow = null;
      render(<WorkflowDetailPage />);
      expect(screen.queryByTestId("breadcrumb")).not.toBeInTheDocument();
      expect(screen.queryByTestId("card")).not.toBeInTheDocument();
    });
  });

  /* ---------- Error / not-found state ---------- */
  describe("error state", () => {
    test("shows error message when error is provided", () => {
      mockWorkflow = null;
      mockError = new Error("Something went wrong");
      render(<WorkflowDetailPage />);
      expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    });

    test("shows 'Not found' when error is null but workflow is null", () => {
      mockWorkflow = null;
      mockError = null;
      render(<WorkflowDetailPage />);
      expect(screen.getByText("Not found")).toBeInTheDocument();
    });

    test("renders back button that navigates to workflows list", () => {
      mockWorkflow = null;
      mockError = new Error("fail");
      render(<WorkflowDetailPage />);
      const btn = screen.getByText("Back");
      fireEvent.click(btn);
      expect(mockPush).toHaveBeenCalledWith("/workspace/workflows");
    });

    test("does not render workflow content in error state", () => {
      mockWorkflow = null;
      mockError = new Error("fail");
      render(<WorkflowDetailPage />);
      expect(screen.queryByTestId("card")).not.toBeInTheDocument();
    });
  });

  /* ---------- Header ---------- */
  describe("header", () => {
    test("renders workflow name in header", () => {
      render(<WorkflowDetailPage />);
      expect(screen.getByText("test-workflow")).toBeInTheDocument();
    });

    test("renders workflow description when present", () => {
      render(<WorkflowDetailPage />);
      expect(screen.getByText("A test workflow")).toBeInTheDocument();
    });

    test("does not render description when workflow has no description", () => {
      mockWorkflow = { ...defaultWorkflow, description: "" };
      render(<WorkflowDetailPage />);
      expect(screen.queryByText("A test workflow")).not.toBeInTheDocument();
    });

    test("does not render description when workflow description is falsy", () => {
      mockWorkflow = { ...defaultWorkflow, description: "" as any };
      render(<WorkflowDetailPage />);
      const descParagraphs = screen.queryAllByText("A test workflow");
      expect(descParagraphs).toHaveLength(0);
    });

    test("renders version badge", () => {
      render(<WorkflowDetailPage />);
      const badge = screen.getByText("v1.0");
      expect(badge).toBeInTheDocument();
    });

    test("renders back button that navigates to workflows list", () => {
      render(<WorkflowDetailPage />);
      const backButtons = screen.getAllByTestId("button");
      const backButton = backButtons.find(
        (b) => b.getAttribute("data-variant") === "ghost",
      );
      expect(backButton).toBeDefined();
      fireEvent.click(backButton!);
      expect(mockPush).toHaveBeenCalledWith("/workspace/workflows");
    });

    test("renders edit link with correct href", () => {
      render(<WorkflowDetailPage />);
      const editLink = screen.getByText("Edit").closest("a");
      expect(editLink).toBeInTheDocument();
      expect(editLink).toHaveAttribute(
        "href",
        "/workspace/workflows/test-workflow/edit",
      );
    });

    test("renders run button", () => {
      render(<WorkflowDetailPage />);
      expect(screen.getByText("Run")).toBeInTheDocument();
    });

    test("renders visibility badge styles for public and department", () => {
      mockWorkflow = { ...defaultWorkflow, visibility: "public" };
      const { rerender } = render(<WorkflowDetailPage />);
      expect(screen.getByText("Visibility: public")).toHaveClass(
        "bg-green-100",
      );

      mockWorkflow = { ...defaultWorkflow, visibility: "department" };
      rerender(<WorkflowDetailPage />);
      expect(screen.getByText("Visibility: department")).toHaveClass(
        "bg-blue-100",
      );
    });
  });

  /* ---------- Export ---------- */
  describe("export", () => {
    test("downloads yaml content and shows success toast", () => {
      const appendChild = vi.spyOn(document.body, "appendChild");
      const removeChild = vi.spyOn(document.body, "removeChild");
      const click = vi
        .spyOn(HTMLAnchorElement.prototype, "click")
        .mockImplementation(() => {});

      render(<WorkflowDetailPage />);
      fireEvent.click(screen.getByText("Export"));

      expect(URL.createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
      expect(appendChild).toHaveBeenCalled();
      expect(click).toHaveBeenCalled();
      expect(removeChild).toHaveBeenCalled();
      expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:workflow");
      expect(toast.success).toHaveBeenCalledWith("Export successful");
    });

    test("shows error when yaml content is missing", () => {
      mockWorkflow = { ...defaultWorkflow, yaml_content: "" };

      render(<WorkflowDetailPage />);
      fireEvent.click(screen.getByText("Export"));

      expect(URL.createObjectURL).not.toHaveBeenCalled();
      expect(toast.error).toHaveBeenCalledWith("Export failed");
    });
  });

  /* ---------- Visibility application ---------- */
  describe("visibility application", () => {
    test("validates required reason", async () => {
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);

      await user.click(screen.getByText("Apply Visibility Change"));

      expect(screen.getByText("Submit Application")).toBeDisabled();
      expect(mockCreateVisibilityApplication).not.toHaveBeenCalled();
    });

    test("submits visibility application with trimmed reason", async () => {
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);

      await user.click(screen.getByText("Apply Visibility Change"));
      await user.click(screen.getByRole("combobox"));
      await user.click(screen.getByRole("option", { name: "Public" }));
      fireEvent.change(screen.getByPlaceholderText("Enter your reason..."), {
        target: { value: "  Share this workflow  " },
      });
      await user.click(screen.getByText("Submit Application"));

      await waitFor(() => {
        expect(mockCreateVisibilityApplication).toHaveBeenCalledWith({
          resource_type: "workflow",
          resource_id: "test-workflow",
          target_visibility: "public",
          reason: "Share this workflow",
        });
        expect(toast.success).toHaveBeenCalledWith("Application submitted");
      });
      expect(screen.queryByText("Submit Application")).not.toBeInTheDocument();
    });

    test("shows visibility application errors", async () => {
      const user = userEvent.setup();
      mockCreateVisibilityApplication.mockRejectedValue(
        new Error("application failed"),
      );
      render(<WorkflowDetailPage />);

      await user.click(screen.getByText("Apply Visibility Change"));
      fireEvent.change(screen.getByPlaceholderText("Enter your reason..."), {
        target: { value: "Need wider access" },
      });
      await user.click(screen.getByText("Submit Application"));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("application failed");
      });
    });

    test("shows non-Error visibility application errors", async () => {
      const user = userEvent.setup();
      mockCreateVisibilityApplication.mockRejectedValue(
        "raw application error",
      );
      render(<WorkflowDetailPage />);

      await user.click(screen.getByText("Apply Visibility Change"));
      fireEvent.change(screen.getByPlaceholderText("Enter your reason..."), {
        target: { value: "Need wider access" },
      });
      await user.click(screen.getByText("Submit Application"));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("raw application error");
      });
    });
  });

  /* ---------- Steps section ---------- */
  describe("steps section", () => {
    test("renders steps count title", () => {
      render(<WorkflowDetailPage />);
      expect(screen.getByText("1 Steps")).toBeInTheDocument();
    });

    test("renders steps description", () => {
      render(<WorkflowDetailPage />);
      expect(screen.getByText("Workflow steps")).toBeInTheDocument();
    });

    test("renders step with id, type badge, agent badge, and prompt", () => {
      render(<WorkflowDetailPage />);
      expect(screen.getByText("step1")).toBeInTheDocument();
      expect(screen.getByText("agent")).toBeInTheDocument();
      expect(screen.getByText("test-agent")).toBeInTheDocument();
      expect(screen.getByText("Do something")).toBeInTheDocument();
    });

    test("renders step number indicator", () => {
      render(<WorkflowDetailPage />);
      expect(screen.getByText("1")).toBeInTheDocument();
    });

    test("renders 'No steps' when steps array is empty", () => {
      mockWorkflow = { ...defaultWorkflow, steps: [], steps_count: 0 };
      render(<WorkflowDetailPage />);
      expect(screen.getByText("No steps")).toBeInTheDocument();
    });

    test("does not render step cards when steps are empty", () => {
      mockWorkflow = { ...defaultWorkflow, steps: [], steps_count: 0 };
      render(<WorkflowDetailPage />);
      expect(screen.queryByText("step1")).not.toBeInTheDocument();
    });

    test("renders multiple steps with correct indices", () => {
      mockWorkflow = {
        ...defaultWorkflow,
        steps: [
          { id: "s1", type: "agent", prompt: "first" },
          { id: "s2", type: "tool", prompt: "second" },
          { id: "s3", type: "condition" },
        ],
        steps_count: 3,
      };
      render(<WorkflowDetailPage />);
      expect(screen.getByText("3 Steps")).toBeInTheDocument();
      expect(screen.getByText("s1")).toBeInTheDocument();
      expect(screen.getByText("s2")).toBeInTheDocument();
      expect(screen.getByText("s3")).toBeInTheDocument();
      expect(screen.getByText("1")).toBeInTheDocument();
      expect(screen.getByText("2")).toBeInTheDocument();
      expect(screen.getByText("3")).toBeInTheDocument();
    });

    test("does not render agent badge when step has no agent", () => {
      mockWorkflow = {
        ...defaultWorkflow,
        steps: [{ id: "no-agent-step", type: "condition" }],
        steps_count: 1,
      };
      render(<WorkflowDetailPage />);
      expect(screen.getByText("no-agent-step")).toBeInTheDocument();
      expect(screen.getByText("condition")).toBeInTheDocument();
      // The version badge "v1.0" uses secondary variant, but within the step
      // there should be no secondary badge (agent badge).
      // Find the step container that has "no-agent-step" and check for secondary badges.
      const stepContainer = screen
        .getByText("no-agent-step")
        .closest("div")?.parentElement;
      const secondaryBadges = stepContainer
        ? within(stepContainer)
            .queryAllByTestId("badge")
            .filter((b) => b.getAttribute("data-variant") === "secondary")
        : [];
      expect(secondaryBadges).toHaveLength(0);
    });

    test("does not render prompt when step has no prompt", () => {
      mockWorkflow = {
        ...defaultWorkflow,
        steps: [{ id: "no-prompt-step", type: "loop" }],
        steps_count: 1,
      };
      render(<WorkflowDetailPage />);
      expect(screen.getByText("no-prompt-step")).toBeInTheDocument();
      expect(screen.queryByText("Do something")).not.toBeInTheDocument();
    });
  });

  /* ---------- Inputs section ---------- */
  describe("inputs section", () => {
    test("renders inputs section when inputs exist", () => {
      render(<WorkflowDetailPage />);
      expect(screen.getByText("Inputs")).toBeInTheDocument();
      expect(screen.getByText("Research topic")).toBeInTheDocument();
    });

    test("renders input key name", () => {
      render(<WorkflowDetailPage />);
      expect(screen.getByText("topic")).toBeInTheDocument();
    });

    test("renders input type badge", () => {
      render(<WorkflowDetailPage />);
      expect(screen.getByText("string")).toBeInTheDocument();
    });

    test("renders required badge for required inputs", () => {
      render(<WorkflowDetailPage />);
      const badges = screen.getAllByTestId("badge");
      const requiredBadge = badges.find(
        (b) =>
          b.textContent === "Required" &&
          b.getAttribute("data-variant") === "destructive",
      );
      expect(requiredBadge).toBeInTheDocument();
    });

    test("does not render required badge for optional inputs", () => {
      mockWorkflow = {
        ...defaultWorkflow,
        inputs: {
          topic: {
            type: "string",
            required: false,
            description: "Optional topic",
            default: undefined,
          },
        },
      };
      render(<WorkflowDetailPage />);
      const badges = screen.getAllByTestId("badge");
      const requiredBadge = badges.find(
        (b) =>
          b.textContent === "Required" &&
          b.getAttribute("data-variant") === "destructive",
      );
      expect(requiredBadge).toBeUndefined();
    });

    test("renders input description", () => {
      render(<WorkflowDetailPage />);
      expect(screen.getByText("Research topic")).toBeInTheDocument();
    });

    test("does not render description paragraph when param has no description", () => {
      mockWorkflow = {
        ...defaultWorkflow,
        inputs: {
          topic: {
            type: "string",
            required: true,
            description: "",
            default: undefined,
          },
        },
      };
      render(<WorkflowDetailPage />);
      expect(screen.getByText("topic")).toBeInTheDocument();
    });

    test("does not render inputs section when inputs is empty", () => {
      mockWorkflow = { ...defaultWorkflow, inputs: {} };
      render(<WorkflowDetailPage />);
      expect(screen.queryByText("Inputs")).not.toBeInTheDocument();
    });

    test("renders multiple inputs", () => {
      mockWorkflow = {
        ...defaultWorkflow,
        inputs: {
          topic: {
            type: "string",
            required: true,
            description: "The topic",
            default: undefined,
          },
          count: {
            type: "number",
            required: false,
            description: "How many",
            default: undefined,
          },
        },
      };
      render(<WorkflowDetailPage />);
      expect(screen.getByText("topic")).toBeInTheDocument();
      expect(screen.getByText("count")).toBeInTheDocument();
      expect(screen.getByText("The topic")).toBeInTheDocument();
      expect(screen.getByText("How many")).toBeInTheDocument();
    });
  });

  /* ---------- YAML preview ---------- */
  describe("yaml preview", () => {
    test("renders YAML definition title", () => {
      render(<WorkflowDetailPage />);
      expect(screen.getByText("YAML Definition")).toBeInTheDocument();
    });

    test("renders yaml_content in pre tag", () => {
      render(<WorkflowDetailPage />);
      const pre = document.querySelector("pre");
      expect(pre).toBeInTheDocument();
      expect(pre?.textContent).toContain("name: test-workflow");
      expect(pre?.textContent).toContain("steps: []");
    });
  });

  /* ---------- Run dialog ---------- */
  describe("run dialog", () => {
    test("dialog is not open by default", () => {
      render(<WorkflowDetailPage />);
      expect(screen.queryByTestId("dialog")).not.toBeInTheDocument();
    });

    test("clicking run button opens dialog", async () => {
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      expect(screen.getByTestId("dialog")).toBeInTheDocument();
    });

    test("dialog shows title and description", async () => {
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      expect(screen.getByText("Run Workflow")).toBeInTheDocument();
      expect(screen.getByText("Configure inputs")).toBeInTheDocument();
    });

    test("dialog shows input fields for each input", async () => {
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const dialog = screen.getByTestId("dialog");
      expect(within(dialog).getByText("topic")).toBeInTheDocument();
      expect(within(dialog).getByText("Research topic")).toBeInTheDocument();
    });

    test("dialog shows required asterisk for required inputs", async () => {
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const dialog = screen.getByTestId("dialog");
      // The label contains "topic" and a required span with "*"
      const labels = within(dialog).getAllByTestId("label");
      const topicLabel = labels.find((l) => l.textContent?.includes("topic"));
      expect(topicLabel).toBeDefined();
      expect(topicLabel?.textContent).toContain("*");
    });

    test("dialog shows default placeholder when input has default value", async () => {
      mockWorkflow = {
        ...defaultWorkflow,
        inputs: {
          topic: {
            type: "string",
            required: false,
            description: "The topic",
            default: "default-value",
          },
        },
      };
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const input = screen.getByTestId("input");
      expect(input).toHaveAttribute("placeholder", 'Default: "default-value"');
    });

    test("dialog shows enter input placeholder when no default", async () => {
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const input = screen.getByTestId("input");
      expect(input).toHaveAttribute("placeholder", "Enter topic");
    });

    test("dialog shows 'No inputs required' when no inputs", async () => {
      mockWorkflow = { ...defaultWorkflow, inputs: {} };
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      expect(screen.getByText("No inputs required")).toBeInTheDocument();
    });

    test("cancel button closes dialog", async () => {
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      expect(screen.getByTestId("dialog")).toBeInTheDocument();
      const cancelBtn = screen.getByText("Cancel");
      await user.click(cancelBtn);
      expect(screen.queryByTestId("dialog")).not.toBeInTheDocument();
    });

    test("run button in dialog is disabled when isPending", async () => {
      mockIsPending = true;
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const dialog = screen.getByTestId("dialog");
      const footer = within(dialog).getByTestId("dialog-footer");
      const buttons = within(footer).getAllByTestId("button");
      const submitBtn = buttons.find(
        (b) => b.textContent?.includes("Starting") || b.textContent === "Run",
      );
      expect(submitBtn).toBeDefined();
      expect(submitBtn).toHaveAttribute("disabled");
    });

    test("run button shows 'Starting...' text when isPending", async () => {
      mockIsPending = true;
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      expect(screen.getByText("Starting...")).toBeInTheDocument();
    });

    test("dialog renders input description text", async () => {
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const dialog = screen.getByTestId("dialog");
      // "Research topic" also appears in the inputs card, so scope to dialog
      const descriptions = within(dialog).getAllByText("Research topic");
      expect(descriptions.length).toBeGreaterThanOrEqual(1);
    });
  });

  /* ---------- handleRun ---------- */
  describe("handleRun", () => {
    test("validates required inputs and shows error toast when missing", async () => {
      mockMutateAsync = vi.fn();
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      await user.click(findDialogSubmitButton());
      expect(toast.error).toHaveBeenCalledWith("topic is required");
      expect(mockMutateAsync).not.toHaveBeenCalled();
    });

    test("trims whitespace and validates required inputs", async () => {
      mockMutateAsync = vi.fn();
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const input = screen.getByTestId("input");
      await user.type(input, "   ");
      await user.click(findDialogSubmitButton());
      expect(toast.error).toHaveBeenCalledWith("topic is required");
      expect(mockMutateAsync).not.toHaveBeenCalled();
    });

    test("parses JSON input values", async () => {
      mockMutateAsync = vi.fn().mockResolvedValue({
        run_id: "run-1",
        status: "running",
        workflow: "test-workflow",
      });
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const input = screen.getByTestId("input");
      // Use fireEvent because { and } are special in userEvent.type
      fireEvent.change(input, { target: { value: '{"key": "value"}' } });
      await user.click(findDialogSubmitButton());
      expect(mockMutateAsync).toHaveBeenCalledWith({
        name: "test-workflow",
        inputs: { topic: { key: "value" } },
      });
    });

    test("keeps non-JSON input as string", async () => {
      mockMutateAsync = vi.fn().mockResolvedValue({
        run_id: "run-2",
        status: "running",
        workflow: "test-workflow",
      });
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const input = screen.getByTestId("input");
      await user.type(input, "plain text input");
      await user.click(findDialogSubmitButton());
      expect(mockMutateAsync).toHaveBeenCalledWith({
        name: "test-workflow",
        inputs: { topic: "plain text input" },
      });
    });

    test("skips empty/whitespace inputs in payload", async () => {
      mockWorkflow = {
        ...defaultWorkflow,
        inputs: {
          topic: {
            type: "string",
            required: false,
            description: "Topic",
            default: undefined,
          },
          extra: {
            type: "string",
            required: false,
            description: "Extra",
            default: undefined,
          },
        },
      };
      mockMutateAsync = vi.fn().mockResolvedValue({
        run_id: "run-3",
        status: "running",
        workflow: "test-workflow",
      });
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const inputs = screen.getAllByTestId("input");
      await user.type(inputs[0]!, "hello");
      // Leave second input empty
      await user.click(findDialogSubmitButton());
      expect(mockMutateAsync).toHaveBeenCalledWith({
        name: "test-workflow",
        inputs: { topic: "hello" },
      });
    });

    test("on success: closes dialog, shows success toast", async () => {
      const runResult: WorkflowRunResult = {
        run_id: "run-abc",
        status: "running",
        workflow: "test-workflow",
      };
      mockMutateAsync = vi.fn().mockResolvedValue(runResult);
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const input = screen.getByTestId("input");
      await user.type(input, "some value");
      await user.click(findDialogSubmitButton());
      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith("Workflow started");
      });
      expect(screen.queryByTestId("dialog")).not.toBeInTheDocument();
    });

    test("on error: shows error toast with error message", async () => {
      mockMutateAsync = vi.fn().mockRejectedValue(new Error("Run failed"));
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const input = screen.getByTestId("input");
      await user.type(input, "value");
      await user.click(findDialogSubmitButton());
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Run failed");
      });
    });

    test("on error: handles non-Error thrown value", async () => {
      mockMutateAsync = vi.fn().mockRejectedValue("string error");
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const input = screen.getByTestId("input");
      await user.type(input, "value");
      await user.click(findDialogSubmitButton());
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("string error");
      });
    });

    test("does not run when workflow is null", () => {
      mockWorkflow = null;
      mockError = null;
      render(<WorkflowDetailPage />);
      expect(screen.getByText("Not found")).toBeInTheDocument();
    });
  });

  /* ---------- Run status card ---------- */
  describe("run status card", () => {
    test("does not show run status card when no active run", () => {
      mockRunStatus = null;
      render(<WorkflowDetailPage />);
      expect(screen.queryByText("Run Status")).not.toBeInTheDocument();
    });

    test("shows run status card after successful run", async () => {
      mockRunStatus = {
        run_id: "run-123",
        workflow: "test-workflow",
        status: "running",
        current_step: "step1",
        error: null,
        steps: {},
      };
      await triggerSuccessfulRun({
        run_id: "run-123",
        status: "running",
        workflow: "test-workflow",
      });
      expect(screen.getByText("Run Status")).toBeInTheDocument();
    });

    test("shows run id in status card", async () => {
      mockRunStatus = {
        run_id: "run-xyz",
        workflow: "test-workflow",
        status: "running",
        current_step: null,
        error: null,
        steps: {},
      };
      await triggerSuccessfulRun({
        run_id: "run-xyz",
        status: "running",
        workflow: "test-workflow",
      });
      expect(screen.getByText(/run-xyz/)).toBeInTheDocument();
    });

    test("renders status badge with correct color for completed", async () => {
      mockRunStatus = {
        run_id: "run-1",
        workflow: "test-workflow",
        status: "completed",
        current_step: null,
        error: null,
        steps: {},
      };
      await triggerSuccessfulRun({
        run_id: "run-1",
        status: "running",
        workflow: "test-workflow",
      });
      const badge = screen
        .getAllByTestId("badge")
        .find((b) => b.textContent === "completed");
      expect(badge).toBeDefined();
      expect(badge).toHaveClass("text-green-600");
    });

    test("renders status badge with correct color for failed", async () => {
      mockRunStatus = {
        run_id: "run-2",
        workflow: "test-workflow",
        status: "failed",
        current_step: null,
        error: null,
        steps: {},
      };
      await triggerSuccessfulRun({
        run_id: "run-2",
        status: "running",
        workflow: "test-workflow",
      });
      const badge = screen
        .getAllByTestId("badge")
        .find((b) => b.textContent === "failed");
      expect(badge).toBeDefined();
      expect(badge).toHaveClass("text-destructive");
    });

    test("renders status badge with correct color for running", async () => {
      mockRunStatus = {
        run_id: "run-3",
        workflow: "test-workflow",
        status: "running",
        current_step: null,
        error: null,
        steps: {},
      };
      await triggerSuccessfulRun({
        run_id: "run-3",
        status: "running",
        workflow: "test-workflow",
      });
      const badge = screen
        .getAllByTestId("badge")
        .find((b) => b.textContent === "running");
      expect(badge).toBeDefined();
      expect(badge).toHaveClass("text-blue-600");
    });

    test("renders status badge with muted color for unknown status", async () => {
      mockRunStatus = {
        run_id: "run-4",
        workflow: "test-workflow",
        status: "pending",
        current_step: null,
        error: null,
        steps: {},
      };
      await triggerSuccessfulRun({
        run_id: "run-4",
        status: "running",
        workflow: "test-workflow",
      });
      const badge = screen
        .getAllByTestId("badge")
        .find((b) => b.textContent === "pending");
      expect(badge).toBeDefined();
      expect(badge).toHaveClass("text-muted-foreground");
    });

    test("shows error message in run status card", async () => {
      mockRunStatus = {
        run_id: "run-5",
        workflow: "test-workflow",
        status: "failed",
        current_step: null,
        error: "Something went wrong during execution",
        steps: {},
      };
      await triggerSuccessfulRun({
        run_id: "run-5",
        status: "running",
        workflow: "test-workflow",
      });
      expect(
        screen.getByText("Something went wrong during execution"),
      ).toBeInTheDocument();
    });

    test("does not show error section when runStatus.error is null", async () => {
      mockRunStatus = {
        run_id: "run-6",
        workflow: "test-workflow",
        status: "completed",
        current_step: null,
        error: null,
        steps: {},
      };
      await triggerSuccessfulRun({
        run_id: "run-6",
        status: "running",
        workflow: "test-workflow",
      });
      const errorDiv = document.querySelector(".bg-red-50");
      expect(errorDiv).toBeNull();
    });

    test("renders step statuses", async () => {
      mockRunStatus = {
        run_id: "run-7",
        workflow: "test-workflow",
        status: "running",
        current_step: "step1",
        error: null,
        steps: {
          runstep1: {
            status: "completed",
            output: null,
            error: null,
            retries: 0,
            started_at: null,
            finished_at: null,
          },
          runstep2: {
            status: "running",
            output: null,
            error: null,
            retries: 0,
            started_at: null,
            finished_at: null,
          },
        },
      };
      await triggerSuccessfulRun({
        run_id: "run-7",
        status: "running",
        workflow: "test-workflow",
      });
      // Use getAllByText since step names also appear in the workflow steps card
      expect(screen.getAllByText("runstep1").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("runstep2").length).toBeGreaterThanOrEqual(1);
    });

    test("renders step error when present", async () => {
      mockRunStatus = {
        run_id: "run-8",
        workflow: "test-workflow",
        status: "failed",
        current_step: null,
        error: null,
        steps: {
          step1: {
            status: "failed",
            output: null,
            error: "Step execution failed",
            retries: 0,
            started_at: null,
            finished_at: null,
          },
        },
      };
      await triggerSuccessfulRun({
        run_id: "run-8",
        status: "running",
        workflow: "test-workflow",
      });
      expect(screen.getByText("Step execution failed")).toBeInTheDocument();
    });

    test("step status badge colors: completed", async () => {
      mockRunStatus = {
        run_id: "run-9",
        workflow: "test-workflow",
        status: "completed",
        current_step: null,
        error: null,
        steps: {
          step1: {
            status: "completed",
            output: null,
            error: null,
            retries: 0,
            started_at: null,
            finished_at: null,
          },
        },
      };
      await triggerSuccessfulRun({
        run_id: "run-9",
        status: "running",
        workflow: "test-workflow",
      });
      const badges = screen.getAllByTestId("badge");
      const stepBadge = badges.find((b) => b.textContent === "completed");
      expect(stepBadge).toHaveClass("text-green-600");
    });

    test("step status badge colors: failed", async () => {
      mockRunStatus = {
        run_id: "run-10",
        workflow: "test-workflow",
        status: "failed",
        current_step: null,
        error: null,
        steps: {
          step1: {
            status: "failed",
            output: null,
            error: null,
            retries: 0,
            started_at: null,
            finished_at: null,
          },
        },
      };
      await triggerSuccessfulRun({
        run_id: "run-10",
        status: "running",
        workflow: "test-workflow",
      });
      const badges = screen.getAllByTestId("badge");
      const stepBadge = badges.find((b) => b.textContent === "failed");
      expect(stepBadge).toHaveClass("text-destructive");
    });

    test("step status badge colors: running", async () => {
      mockRunStatus = {
        run_id: "run-11",
        workflow: "test-workflow",
        status: "running",
        current_step: null,
        error: null,
        steps: {
          step1: {
            status: "running",
            output: null,
            error: null,
            retries: 0,
            started_at: null,
            finished_at: null,
          },
        },
      };
      await triggerSuccessfulRun({
        run_id: "run-11",
        status: "running",
        workflow: "test-workflow",
      });
      const badges = screen.getAllByTestId("badge");
      const stepBadge = badges.find((b) => b.textContent === "running");
      expect(stepBadge).toHaveClass("text-blue-600");
    });

    test("step status badge colors: unknown status", async () => {
      mockRunStatus = {
        run_id: "run-12",
        workflow: "test-workflow",
        status: "running",
        current_step: null,
        error: null,
        steps: {
          step1: {
            status: "queued",
            output: null,
            error: null,
            retries: 0,
            started_at: null,
            finished_at: null,
          },
        },
      };
      await triggerSuccessfulRun({
        run_id: "run-12",
        status: "running",
        workflow: "test-workflow",
      });
      const badges = screen.getAllByTestId("badge");
      const stepBadge = badges.find((b) => b.textContent === "queued");
      expect(stepBadge).toHaveClass("text-muted-foreground");
    });
  });

  /* ---------- Input typing ---------- */
  describe("input interaction", () => {
    test("typing in dialog input updates the input value", async () => {
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const input = screen.getByTestId("input");
      await user.type(input, "hello world");
      expect(input).toHaveValue("hello world");
    });

    test("handles multiple inputs in dialog", async () => {
      mockWorkflow = {
        ...defaultWorkflow,
        inputs: {
          topic: {
            type: "string",
            required: true,
            description: "The topic",
            default: undefined,
          },
          count: {
            type: "number",
            required: false,
            description: "How many",
            default: undefined,
          },
        },
      };
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const inputs = screen.getAllByTestId("input");
      expect(inputs).toHaveLength(2);
      await user.type(inputs[0]!, "AI");
      await user.type(inputs[1]!, "5");
      expect(inputs[0]).toHaveValue("AI");
      expect(inputs[1]).toHaveValue("5");
    });
  });

  /* ---------- Full page structure ---------- */
  describe("full page structure", () => {
    test("renders all major sections together", () => {
      render(<WorkflowDetailPage />);
      expect(screen.getByTestId("breadcrumb")).toBeInTheDocument();
      expect(screen.getByText("test-workflow")).toBeInTheDocument();
      expect(screen.getByText("A test workflow")).toBeInTheDocument();
      expect(screen.getByText("v1.0")).toBeInTheDocument();
      expect(screen.getByText("1 Steps")).toBeInTheDocument();
      expect(screen.getByText("Inputs")).toBeInTheDocument();
      expect(screen.getByText("YAML Definition")).toBeInTheDocument();
    });

    test("renders three cards in main content area", () => {
      render(<WorkflowDetailPage />);
      const cards = screen.getAllByTestId("card");
      // Steps card, inputs card, yaml card
      expect(cards.length).toBeGreaterThanOrEqual(3);
    });
  });

  /* ---------- Edge cases ---------- */
  describe("edge cases", () => {
    test("workflow with special characters in name", () => {
      mockWorkflow = {
        ...defaultWorkflow,
        name: "my workflow & special <chars>",
      };
      render(<WorkflowDetailPage />);
      expect(
        screen.getByText("my workflow & special <chars>"),
      ).toBeInTheDocument();
    });

    test("workflow with empty yaml_content", () => {
      mockWorkflow = { ...defaultWorkflow, yaml_content: "" };
      render(<WorkflowDetailPage />);
      expect(screen.getByText("YAML Definition")).toBeInTheDocument();
      const pre = document.querySelector("pre");
      expect(pre?.textContent).toBe("");
    });

    test("workflow with many steps renders all", () => {
      const steps = Array.from({ length: 10 }, (_, i) => ({
        id: `step-${i}`,
        type: "agent",
        prompt: `Prompt ${i}`,
      }));
      mockWorkflow = { ...defaultWorkflow, steps, steps_count: 10 };
      render(<WorkflowDetailPage />);
      expect(screen.getByText("10 Steps")).toBeInTheDocument();
      for (let i = 0; i < 10; i++) {
        expect(screen.getByText(`step-${i}`)).toBeInTheDocument();
        expect(screen.getByText(`Prompt ${i}`)).toBeInTheDocument();
      }
    });

    test("step with tool instead of agent", () => {
      mockWorkflow = {
        ...defaultWorkflow,
        steps: [{ id: "tool-step", type: "tool", tool: "search" }],
        steps_count: 1,
      };
      render(<WorkflowDetailPage />);
      expect(screen.getByText("tool-step")).toBeInTheDocument();
      expect(screen.getByText("tool")).toBeInTheDocument();
    });

    test("input with no description in dialog", async () => {
      mockWorkflow = {
        ...defaultWorkflow,
        inputs: {
          topic: {
            type: "string",
            required: false,
            description: "",
            default: undefined,
          },
        },
      };
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      expect(screen.getByTestId("input")).toBeInTheDocument();
    });

    test("input with number default value in dialog", async () => {
      mockWorkflow = {
        ...defaultWorkflow,
        inputs: {
          count: {
            type: "number",
            required: false,
            description: "Count",
            default: 42,
          },
        },
      };
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const input = screen.getByTestId("input");
      expect(input).toHaveAttribute("placeholder", "Default: 42");
    });

    test("input with null default value in dialog shows Default: null", async () => {
      mockWorkflow = {
        ...defaultWorkflow,
        inputs: {
          topic: {
            type: "string",
            required: false,
            description: "Topic",
            default: null,
          },
        },
      };
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const input = screen.getByTestId("input");
      // null !== undefined is true, so JSON.stringify(null) = "null"
      expect(input).toHaveAttribute("placeholder", "Default: null");
    });

    test("input with undefined default shows enter placeholder", async () => {
      mockWorkflow = {
        ...defaultWorkflow,
        inputs: {
          topic: {
            type: "string",
            required: false,
            description: "Topic",
            default: undefined,
          },
        },
      };
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const input = screen.getByTestId("input");
      expect(input).toHaveAttribute("placeholder", "Enter topic");
    });

    test("input with boolean default in dialog", async () => {
      mockWorkflow = {
        ...defaultWorkflow,
        inputs: {
          flag: {
            type: "boolean",
            required: false,
            description: "A flag",
            default: true,
          },
        },
      };
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const input = screen.getByTestId("input");
      expect(input).toHaveAttribute("placeholder", "Default: true");
    });

    test("input with array default in dialog", async () => {
      mockWorkflow = {
        ...defaultWorkflow,
        inputs: {
          items: {
            type: "array",
            required: false,
            description: "Items",
            default: [1, 2, 3],
          },
        },
      };
      const user = userEvent.setup();
      render(<WorkflowDetailPage />);
      await user.click(findRunButton());
      const input = screen.getByTestId("input");
      expect(input).toHaveAttribute("placeholder", "Default: [1,2,3]");
    });
  });
});
