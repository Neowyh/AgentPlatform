import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { RunStatus, WorkflowDetail } from "@/core/workflows";

// ── Mocks ────────────────────────────────────────────────────────────────────

type MockReactFlowProps = {
  nodes: Array<{ id: string; className?: string; selected?: boolean }>;
  edges: Array<{ id: string; animated?: boolean }>;
  onNodeClick: (event: unknown, node: { id: string }) => void;
};

let lastFlowProps: MockReactFlowProps | undefined;

vi.mock("@xyflow/react", () => ({
  ReactFlow: (props: MockReactFlowProps) => {
    lastFlowProps = props;
    return (
      <div
        data-testid="react-flow"
        data-nodes={props.nodes.length}
        data-edges={props.edges.length}
        onClick={() => props.onNodeClick({}, { id: props.nodes[0]?.id ?? "" })}
      />
    );
  },
  ReactFlowProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="provider">{children}</div>
  ),
  useReactFlow: () => ({ fitView: vi.fn() }),
  Background: () => <div data-testid="background" />,
  Controls: () => <div data-testid="controls" />,
}));

vi.mock("@xyflow/react/dist/style.css", () => ({}));

vi.mock("dagre", () => ({
  default: {
    graphlib: {
      Graph: class {
        setDefaultEdgeLabel() {}
        setGraph() {}
        setNode() {}
        setEdge() {}
        node() {
          return { x: 50, y: 50 };
        }
      },
    },
    layout: () => {},
  },
}));

// ── Fixtures ─────────────────────────────────────────────────────────────────

const workflow: WorkflowDetail = {
  name: "wf",
  description: "",
  version: "1",
  steps_count: 2,
  inputs: {},
  visibility: "private",
  owner_id: null,
  department_id: null,
  yaml_content: "",
  schema_version: 2,
  state: {},
  entrypoint: "route",
  nodes: [
    { id: "route", type: "route", expression: "$.state.flag" },
    { id: "task", type: "action", action: { kind: "tool", name: "echo" } },
  ],
  steps: [],
  edges: [{ from: "route", to: "task" }],
};

const baseRun: RunStatus = {
  run_id: "run-1",
  workflow: "wf",
  status: "running",
  error: null,
};

// ── Dynamic import ───────────────────────────────────────────────────────────

let RunGraph: typeof import("@/components/workspace/workflows/run-graph").RunGraph;

beforeEach(async () => {
  vi.clearAllMocks();
  lastFlowProps = undefined;
  const mod = await import("@/components/workspace/workflows/run-graph");
  RunGraph = mod.RunGraph;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("RunGraph", () => {
  test("renders a node per workflow node and an edge per workflow edge", () => {
    render(
      <RunGraph
        workflow={workflow}
        runStatus={baseRun}
        selectedNodeId={null}
        onSelect={() => {}}
      />,
    );
    expect(screen.getByTestId("react-flow")).toHaveAttribute("data-nodes", "2");
    expect(screen.getByTestId("react-flow")).toHaveAttribute("data-edges", "1");
  });

  test("marks the running node with the running status class", () => {
    const runStatus: RunStatus = {
      ...baseRun,
      current_step: "task",
      steps: {
        task: {
          status: "running",
          output: null,
          error: null,
          retries: 0,
          started_at: null,
          finished_at: null,
        },
      },
    };
    render(
      <RunGraph
        workflow={workflow}
        runStatus={runStatus}
        selectedNodeId={null}
        onSelect={() => {}}
      />,
    );
    const taskNode = lastFlowProps?.nodes.find((node) => node.id === "task");
    expect(taskNode?.className).toContain("border-blue-500");
    expect(taskNode?.className).toContain("animate-pulse");
    const routeNode = lastFlowProps?.nodes.find((node) => node.id === "route");
    expect(routeNode?.className).toContain("bg-card");
  });

  test("marks failed nodes with the failed status class", () => {
    const runStatus: RunStatus = {
      ...baseRun,
      status: "failed",
      error: "boom",
      steps: {
        task: {
          status: "failed",
          output: null,
          error: "boom",
          retries: 0,
          started_at: null,
          finished_at: null,
        },
      },
    };
    render(
      <RunGraph
        workflow={workflow}
        runStatus={runStatus}
        selectedNodeId={null}
        onSelect={() => {}}
      />,
    );
    const taskNode = lastFlowProps?.nodes.find((node) => node.id === "task");
    expect(taskNode?.className).toContain("border-red-500");
  });

  test("colors a route node as completed once one of its edges was selected", () => {
    const runStatus: RunStatus = {
      ...baseRun,
      selected_edges: [{ from: "route", to: "task" }],
    };
    render(
      <RunGraph
        workflow={workflow}
        runStatus={runStatus}
        selectedNodeId={null}
        onSelect={() => {}}
      />,
    );
    const routeNode = lastFlowProps?.nodes.find((node) => node.id === "route");
    expect(routeNode?.className).toContain("border-emerald-500");
    const edge = lastFlowProps?.edges.find((e) => e.id === "route->task");
    expect(edge?.animated).toBe(true);
  });

  test("highlights the selected node", () => {
    render(
      <RunGraph
        workflow={workflow}
        runStatus={baseRun}
        selectedNodeId="task"
        onSelect={() => {}}
      />,
    );
    const taskNode = lastFlowProps?.nodes.find((node) => node.id === "task");
    expect(taskNode?.selected).toBe(true);
  });

  test("reports node clicks through onSelect", () => {
    const onSelect = vi.fn();
    render(
      <RunGraph
        workflow={workflow}
        runStatus={baseRun}
        selectedNodeId={null}
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByTestId("react-flow"));
    expect(onSelect).toHaveBeenCalledWith("route");
  });

  test("shows completed fork and join control nodes from lifecycle events", () => {
    const forkJoinWorkflow: WorkflowDetail = {
      ...workflow,
      entrypoint: "fork_start",
      nodes: [
        {
          id: "fork_start",
          type: "fork",
          branches: ["evidence_collection", "deductive_tree"],
          join: "join_review",
        },
        { id: "join_review", type: "join", fork: "fork_start" },
        {
          id: "evidence_collection",
          type: "action",
          action: { kind: "agent", name: "fault-zeroing" },
        },
      ],
      edges: [
        { from: "fork_start", to: "evidence_collection" },
        { from: "evidence_collection", to: "join_review" },
      ],
    };
    const completedRun: RunStatus = {
      ...baseRun,
      status: "completed",
      steps: {
        fork_start: {
          status: "completed",
          output: null,
          error: null,
          retries: 0,
          started_at: null,
          finished_at: null,
        },
        join_review: {
          status: "completed",
          output: null,
          error: null,
          retries: 0,
          started_at: null,
          finished_at: null,
        },
      },
    };
    render(
      <RunGraph
        workflow={forkJoinWorkflow}
        runStatus={completedRun}
        selectedNodeId={null}
        onSelect={() => {}}
      />,
    );
    const forkNode = lastFlowProps?.nodes.find(
      (node) => node.id === "fork_start",
    );
    expect(forkNode?.className).toContain("border-emerald-500");
    const joinNode = lastFlowProps?.nodes.find(
      (node) => node.id === "join_review",
    );
    expect(joinNode?.className).toContain("border-emerald-500");
    const actionNode = lastFlowProps?.nodes.find(
      (node) => node.id === "evidence_collection",
    );
    expect(actionNode?.className).toContain("bg-card");
  });
});
