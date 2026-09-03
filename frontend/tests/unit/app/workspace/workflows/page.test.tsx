import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/styles/globals.css", () => ({}));
vi.mock("katex/dist/katex.min.css", () => ({}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ workflow_name: "test-workflow" }),
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

vi.mock("next/link", () => ({
  default: ({ children, href }: any) => (
    <a href={href} data-testid="next-link">
      {children}
    </a>
  ),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const mockUseWorkflow = vi.fn(() => ({
  workflow: {
    name: "test-workflow",
    description: "A test workflow",
    version: "1.0",
    steps_count: 2,
    steps: [
      {
        id: "step1",
        type: "action",
        action: {
          kind: "agent",
          name: "agent-a",
          params: { prompt: "Do something" },
        },
      },
      {
        id: "step2",
        type: "action",
        action: {
          kind: "tool",
          name: "tool-b",
          params: { prompt: "Run tool" },
        },
      },
    ],
    inputs: {
      query: { type: "string", description: "Search query", required: true },
    },
    yaml_content:
      "schema_version: 2\nname: test-workflow\nnodes:\n  - id: step1\n    type: action\n    action:\n      kind: agent\n      name: agent-a",
  },
  isLoading: false,
  error: null,
}));

const mockUseRunWorkflow = vi.fn(() => ({
  mutateAsync: vi.fn(),
  isPending: false,
}));

const mockUseWorkflowRuns = vi.fn(() => ({
  runs: [] as unknown[],
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en",
    t: {
      common: { loading: "Loading...", cancel: "Cancel" },
      workflows: {
        notFound: "Workflow not found",
        backToWorkflows: "Back to Workflows",
        edit: "Edit",
        run: "Run",
        stepsTitle: (count: number) => `Steps (${count})`,
        stepsDescription: "Workflow step definitions",
        noSteps: "No steps defined",
        inputsTitle: "Inputs",
        inputsDescription: "Required and optional inputs",
        required: "Required",
        yamlDefinition: "YAML Definition",
        runDialog: "Run Workflow",
        runDialogDescription: "Enter input values",
        noInputs: "No inputs required",
        defaultPrefix: "Default: ",
        enterInput: (key: string) => `Enter ${key}`,
        starting: "Starting...",
        started: "Workflow started",
        runStatus: "Run Status",
        runId: "Run ID: ",
        fileCount: (count: number) => `${count} file${count === 1 ? "" : "s"}`,
        noSelectedFiles: "No files selected",
        requiredMissing: (key: string) => `Required input missing: ${key}`,
      },
    },
  }),
}));

vi.mock("@/core/workflows", () => ({
  useWorkflow: (...args: any[]) => (mockUseWorkflow as any)(...args),
  useRunWorkflow: (...args: any[]) => (mockUseRunWorkflow as any)(...args),
  useWorkflowRuns: (...args: any[]) => (mockUseWorkflowRuns as any)(...args),
}));

vi.mock("@/core/models/hooks", () => ({
  useModels: () => ({ models: [] }),
}));

vi.mock("@/components/ui/badge", () => ({
  Badge: ({ children, variant }: any) => (
    <span data-testid="badge" data-variant={variant}>
      {children}
    </span>
  ),
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, variant, onClick, asChild }: any) => (
    <button data-testid="button" data-variant={variant} onClick={onClick}>
      {children}
    </button>
  ),
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
  Dialog: ({ children, open }: any) => (
    <div data-testid="dialog" data-open={String(open)}>
      {children}
    </div>
  ),
  DialogContent: ({ children }: any) => (
    <div data-testid="dialog-content">{children}</div>
  ),
  DialogDescription: ({ children }: any) => <div>{children}</div>,
  DialogFooter: ({ children }: any) => <div>{children}</div>,
  DialogHeader: ({ children }: any) => <div>{children}</div>,
  DialogTitle: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("@/components/ui/input", () => ({
  Input: (props: any) => <input data-testid="input" {...props} />,
}));

vi.mock("@/components/ui/label", () => ({
  Label: ({ children, ...props }: any) => (
    <label data-testid="label" {...props}>
      {children}
    </label>
  ),
}));

vi.mock("@/components/workspace/workspace-breadcrumb", () => ({
  WorkspaceBreadcrumb: () => <div data-testid="workspace-breadcrumb" />,
}));

import WorkflowDetailPage from "@/app/workspace/workflows/[workflow_name]/page";

const defaultWorkflow = {
  name: "test-workflow",
  description: "A test workflow",
  version: "1.0",
  steps_count: 2,
  steps: [
    {
      id: "step1",
      type: "action",
      action: {
        kind: "agent",
        name: "agent-a",
        params: { prompt: "Do something" },
      },
    },
    {
      id: "step2",
      type: "action",
      action: { kind: "tool", name: "tool-b", params: { prompt: "Run tool" } },
    },
  ],
  inputs: {
    query: { type: "string", description: "Search query", required: true },
  },
  yaml_content:
    "schema_version: 2\nname: test-workflow\nnodes:\n  - id: step1\n    type: action\n    action:\n      kind: agent\n      name: agent-a",
};

afterEach(() => {
  vi.clearAllMocks();
  mockUseWorkflow.mockReturnValue({
    workflow: defaultWorkflow,
    isLoading: false,
    error: null,
  });
  mockUseRunWorkflow.mockReturnValue({
    mutateAsync: vi.fn(),
    isPending: false,
  });
  mockUseWorkflowRuns.mockReturnValue({
    runs: [],
  });
});

describe("WorkflowDetailPage", () => {
  test("renders workflow name", () => {
    render(<WorkflowDetailPage />);
    expect(screen.getByText("test-workflow")).toBeInTheDocument();
  });

  test("renders workflow description", () => {
    render(<WorkflowDetailPage />);
    expect(screen.getByText("A test workflow")).toBeInTheDocument();
  });

  test("renders workspace breadcrumb", () => {
    render(<WorkflowDetailPage />);
    expect(screen.getByTestId("workspace-breadcrumb")).toBeInTheDocument();
  });

  test("renders version badge", () => {
    render(<WorkflowDetailPage />);
    const badges = screen.getAllByTestId("badge");
    const versionBadge = badges.find((b) => b.textContent === "v1.0");
    expect(versionBadge).toBeDefined();
    expect(versionBadge!.textContent).toBe("v1.0");
  });

  test("renders steps section", () => {
    render(<WorkflowDetailPage />);
    expect(screen.getByText("step1")).toBeInTheDocument();
    expect(screen.getByText("step2")).toBeInTheDocument();
  });

  test("renders step type badges", () => {
    render(<WorkflowDetailPage />);
    const badges = screen.getAllByText("action");
    expect(badges.length).toBeGreaterThanOrEqual(2);
  });

  test("renders step agent badge", () => {
    render(<WorkflowDetailPage />);
    expect(screen.getByText("agent-a")).toBeInTheDocument();
  });

  test("renders step prompts", () => {
    render(<WorkflowDetailPage />);
    expect(screen.getByText("Do something")).toBeInTheDocument();
    expect(screen.getByText("Run tool")).toBeInTheDocument();
  });

  test("renders inputs section", () => {
    render(<WorkflowDetailPage />);
    const queryElements = screen.getAllByText("query");
    expect(queryElements.length).toBeGreaterThanOrEqual(1);
    const searchQueryElements = screen.getAllByText("Search query");
    expect(searchQueryElements.length).toBeGreaterThanOrEqual(1);
  });

  test("renders yaml definition", () => {
    render(<WorkflowDetailPage />);
    expect(screen.getByText("YAML Definition")).toBeInTheDocument();
  });

  test("renders run button", () => {
    render(<WorkflowDetailPage />);
    const buttons = screen.getAllByTestId("button");
    const runButton = buttons.find((b) => b.textContent?.includes("Run"));
    expect(runButton).toBeDefined();
    expect(runButton!.textContent).toMatch(/Run/i);
  });

  test("renders edit button with correct link", () => {
    render(<WorkflowDetailPage />);
    const links = screen.getAllByTestId("next-link");
    const editLink = links.find((l) =>
      l.getAttribute("href")?.includes("/edit"),
    );
    expect(editLink).toBeDefined();
    expect(editLink!.getAttribute("href")).toMatch(/\/edit$/);
  });
});

describe("WorkflowDetailPage - Loading state", () => {
  test("shows loading indicator", () => {
    mockUseWorkflow.mockReturnValue({
      workflow: null as any,
      isLoading: true,
      error: null,
    });
    render(<WorkflowDetailPage />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });
});

describe("WorkflowDetailPage - Error state", () => {
  test("shows error when workflow not found", () => {
    mockUseWorkflow.mockReturnValue({
      workflow: null as any,
      isLoading: false,
      error: null,
    });
    render(<WorkflowDetailPage />);
    expect(screen.getByText("Workflow not found")).toBeInTheDocument();
  });
});

describe("WorkflowDetailPage - No inputs", () => {
  test("renders correctly when workflow has no inputs", () => {
    mockUseWorkflow.mockReturnValue({
      workflow: {
        name: "no-input-wf",
        description: "No inputs",
        version: "2.0",
        steps_count: 1,
        steps: [
          { id: "step1", type: "action", action: { kind: "agent", name: "" } },
        ] as any,
        inputs: {} as any,
        yaml_content: "schema_version: 2\nname: no-input-wf",
      },
      isLoading: false,
      error: null,
    });
    render(<WorkflowDetailPage />);
    expect(screen.getByText("no-input-wf")).toBeInTheDocument();
  });
});

describe("WorkflowDetailPage - Run status", () => {
  test("shows run status when active run exists", () => {
    mockUseWorkflow.mockReturnValue({
      workflow: {
        name: "test-workflow",
        description: "Test",
        version: "1.0",
        steps_count: 1,
        steps: [
          { id: "step1", type: "action", action: { kind: "agent", name: "" } },
        ] as any,
        inputs: {} as any,
        yaml_content: "schema_version: 2\nname: test-workflow",
      },
      isLoading: false,
      error: null,
    });
    mockUseWorkflowRuns.mockReturnValue({
      runs: [
        {
          status: "completed",
          run_id: "run-123",
          steps: { step1: { status: "completed" } },
        },
      ],
    });
    render(<WorkflowDetailPage />);
    expect(screen.getByText("test-workflow")).toBeInTheDocument();
  });
});
