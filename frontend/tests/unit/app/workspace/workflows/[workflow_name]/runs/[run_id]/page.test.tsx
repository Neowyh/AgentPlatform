import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import WorkflowRunDetailPage from "@/app/workspace/workflows/[workflow_name]/runs/[run_id]/page";

const mockMutateAsync = vi.fn();
const mockPush = vi.fn();
let runStatus = {
  run_id: "run-1",
  workflow: "approval",
  status: "paused",
  definition_version: 2,
  error: null,
  steps: {
    review: {
      status: "running",
      output: null,
      error: null,
      retries: 0,
      started_at: null,
      finished_at: null,
    },
  },
  action_tokens: { review: "thinking" },
  events: [
    { seq: 1, type: "node_started" as const, payload: { node_id: "review" } },
  ],
};

vi.mock("next/navigation", () => ({
  useParams: () => ({ workflow_name: "approval", run_id: "run-1" }),
  useRouter: () => ({ push: mockPush }),
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      common: { loading: "Loading", cancel: "Cancel" },
      workflows: {
        backToWorkflows: "Back to workflow",
        runStatus: "Run status",
        runId: "Run ID: ",
        resume: "Resume execution",
        cancelRun: "Cancel run",
        definitionVersion: "Definition version",
        streamFallback: "Live updates unavailable; refreshing status.",
        eventTimeline: "Event timeline",
        actionOutput: "Action output",
        commandSubmitted: "Command submitted",
        runNotFound: "Run not found",
      },
    },
  }),
}));
vi.mock("@/core/workflows", () => ({
  useWorkflow: () => ({
    workflow: { name: "approval", version: "2", nodes: [], edges: [] },
    isLoading: false,
    error: null,
  }),
  useRunStatus: () => ({
    runStatus,
    isLoading: false,
    error: null,
    fallbackPolling: false,
  }),
  useRunArtifacts: () => ({
    artifacts: [],
    isLoading: false,
    error: null,
    refetch: () => {},
  }),
  useRunArtifactContent: () => ({
    data: undefined,
    isLoading: false,
  }),
  useSubmitWorkflowCommand: () => ({
    mutateAsync: mockMutateAsync,
    isPending: false,
  }),
}));
vi.mock("@/components/workspace/workspace-breadcrumb", () => ({
  WorkspaceBreadcrumb: () => <div />,
}));
vi.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, disabled, ...props }: any) => (
    <button onClick={onClick} disabled={disabled} {...props}>
      {children}
    </button>
  ),
}));
vi.mock("@/components/ui/badge", () => ({
  Badge: ({ children }: any) => <span>{children}</span>,
}));
vi.mock("@/components/ui/card", () => ({
  Card: ({ children }: any) => <section>{children}</section>,
  CardContent: ({ children }: any) => <div>{children}</div>,
  CardHeader: ({ children }: any) => <div>{children}</div>,
  CardTitle: ({ children }: any) => <h2>{children}</h2>,
  CardDescription: ({ children }: any) => <p>{children}</p>,
}));
vi.mock("@/components/ui/collapsible", () => ({
  Collapsible: ({ children }: any) => <div>{children}</div>,
  CollapsibleTrigger: ({ children }: any) => <div>{children}</div>,
  CollapsibleContent: ({ children }: any) => <div>{children}</div>,
}));
vi.mock("@/components/workspace/workflows/run-graph", () => ({
  RunGraph: () => <div data-testid="run-graph" />,
}));
vi.mock("@/components/workspace/workflows/node-detail", () => ({
  NodeDetailPanel: () => <div data-testid="node-detail" />,
}));

describe("WorkflowRunDetailPage", () => {
  beforeEach(() => {
    mockMutateAsync.mockReset().mockResolvedValue({ accepted: true });
  });

  test("submits a resume command with a fresh command id for paused runs", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "command-1" });
    render(<WorkflowRunDetailPage />);

    fireEvent.click(screen.getByRole("button", { name: "Resume execution" }));

    expect(mockMutateAsync).toHaveBeenCalledWith({
      name: "approval",
      runId: "run-1",
      command: { command_id: "command-1", type: "resume", payload: {} },
    });
  });

  test("only shows cancellation while a run is active", () => {
    runStatus = { ...runStatus, status: "running" };
    render(<WorkflowRunDetailPage />);

    expect(
      screen.queryByRole("button", { name: "Resume execution" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Cancel run" }),
    ).toBeInTheDocument();
  });

  test("paused runs offer both resume and cancel", () => {
    runStatus = { ...runStatus, status: "paused" };
    render(<WorkflowRunDetailPage />);

    expect(
      screen.getByRole("button", { name: "Resume execution" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Cancel run" }),
    ).toBeInTheDocument();
  });
});
