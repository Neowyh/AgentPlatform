import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import WorkflowRunDetailPage from "@/app/workspace/workflows/[workflow_name]/runs/[run_id]/page";
import type { RunStatus } from "@/core/workflows";

const mockToastError = vi.hoisted(() => vi.fn());
const mockMutateAsync = vi.hoisted(() => vi.fn());
const mockPush = vi.hoisted(() => vi.fn());
const mockArtifacts = vi.hoisted<{
  current: Array<{ path: string; size: number }>;
}>(() => ({ current: [] }));
const mockArtifactContent = vi.hoisted<{ current: string | undefined }>(() => ({
  current: undefined,
}));
let runStatus: RunStatus = {
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
vi.mock("sonner", () => ({
  toast: { error: mockToastError, success: vi.fn() },
}));
vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      common: { loading: "Loading", cancel: "Cancel", preview: "Preview" },
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
        artifactSize: "Size",
        artifactLoadError: "Failed to load artifacts",
        noArtifacts: "No artifacts yet",
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
    artifacts: mockArtifacts.current,
    isLoading: false,
    error: null,
    refetch: () => {},
  }),
  useRunArtifactContent: () => ({
    data: mockArtifactContent.current,
    isLoading: false,
  }),
  useSubmitWorkflowCommand: () => ({
    mutateAsync: mockMutateAsync,
    isPending: false,
  }),
  workflowRunArtifactDownloadUrl: (name: string, runId: string, path: string) =>
    `http://backend/api/workflows/${encodeURIComponent(name)}/runs/${encodeURIComponent(runId)}/artifacts/content?path=${encodeURIComponent(path)}`,
  workflowRunRecordDownloadUrl: (name: string, runId: string, format: string) =>
    `http://backend/api/workflows/${encodeURIComponent(name)}/runs/${encodeURIComponent(runId)}/record?format=${format}`,
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
    mockToastError.mockReset();
    mockArtifacts.current = [];
    mockArtifactContent.current = undefined;
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

  test("downloads the markdown run record", async () => {
    const { fetchMock, downloads } = stubDownloads();
    render(<WorkflowRunDetailPage />);

    fireEvent.click(screen.getByRole("button", { name: "MD" }));

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        "/api/workflows/approval/runs/run-1/record?format=md",
      ),
      expect.anything(),
    );
    await vi.waitFor(() => expect(downloads).toEqual(["run_run-1.md"]));
  });

  test("downloads the jsonl event log", async () => {
    const { fetchMock, downloads } = stubDownloads();
    render(<WorkflowRunDetailPage />);

    fireEvent.click(screen.getByRole("button", { name: "JSONL" }));

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        "/api/workflows/approval/runs/run-1/record?format=jsonl",
      ),
      expect.anything(),
    );
    await vi.waitFor(() => expect(downloads).toEqual(["run_run-1.jsonl"]));
  });

  test("shows an error toast when the record download fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 404 }),
    );
    render(<WorkflowRunDetailPage />);

    fireEvent.click(screen.getByRole("button", { name: "MD" }));

    await vi.waitFor(() =>
      expect(mockToastError).toHaveBeenCalledWith("HTTP 404"),
    );
  });

  test("renders the event timeline with seq, type and edge labels", () => {
    runStatus = {
      ...runStatus,
      status: "completed",
      events: [
        {
          seq: 1,
          type: "node_started",
          payload: { node_id: "evidence_collection" },
        },
        {
          seq: 2,
          type: "edge_selected",
          payload: { from: "join_review", to: "review_and_crosscheck" },
        },
        { seq: 3, type: "run_completed", payload: {} },
      ],
    };
    render(<WorkflowRunDetailPage />);

    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("node_started")).toBeInTheDocument();
    expect(screen.getByText("edge_selected")).toBeInTheDocument();
    expect(
      screen.getByText("join_review → review_and_crosscheck"),
    ).toBeInTheDocument();
  });

  test("previews artifact content as pretty JSON", () => {
    mockArtifacts.current = [
      { path: "/mnt/user-data/outputs/fault_tree.json", size: 1234 },
    ];
    mockArtifactContent.current = '{"a": 1}';
    render(<WorkflowRunDetailPage />);

    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    expect(document.querySelector("pre")?.textContent).toBe('{\n  "a": 1\n}');
  });

  test("downloads an artifact by its virtual path", async () => {
    mockArtifacts.current = [
      { path: "/mnt/user-data/outputs/fault_tree.json", size: 1234 },
    ];
    const { fetchMock, downloads } = stubDownloads();
    render(<WorkflowRunDetailPage />);

    const row = screen.getByText("fault_tree.json").closest("li")!;
    const downloadButton = within(row).getAllByRole("button")[1]!;
    fireEvent.click(downloadButton);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        "/artifacts/content?path=%2Fmnt%2Fuser-data%2Foutputs%2Ffault_tree.json",
      ),
      expect.anything(),
    );
    await vi.waitFor(() => expect(downloads).toEqual(["fault_tree.json"]));
  });
});

let anchorClickSpy: ReturnType<typeof vi.spyOn> | undefined;

function stubDownloads() {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    blob: async () => new Blob(["record"], { type: "text/plain" }),
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("URL", {
    ...URL,
    createObjectURL: vi.fn(() => "blob:mock"),
    revokeObjectURL: vi.fn(),
  });
  anchorClickSpy?.mockRestore();
  const downloads: string[] = [];
  anchorClickSpy = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(function (this: HTMLAnchorElement) {
      downloads.push(this.download);
    });
  return { fetchMock, downloads };
}
