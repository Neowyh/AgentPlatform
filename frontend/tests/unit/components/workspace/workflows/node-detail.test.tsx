import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { WorkflowNode } from "@/core/workflows";

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      workflows: {
        selectNodeHint: "Select a node in the graph",
        nodeDetailTitle: "Node details",
        duration: "Duration",
        actionOutput: "Action output",
        tokenStream: "Token stream",
        nodeNotStarted: "This node has not started yet.",
      },
    },
  }),
}));

const actionNode: WorkflowNode = {
  id: "task",
  type: "action",
  action: { kind: "tool", name: "echo" },
};

let NodeDetailPanel: typeof import("@/components/workspace/workflows/node-detail").NodeDetailPanel;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/workspace/workflows/node-detail");
  NodeDetailPanel = mod.NodeDetailPanel;
});

afterEach(() => {
  cleanup();
});

describe("NodeDetailPanel", () => {
  test("shows a hint when no node is selected", () => {
    render(<NodeDetailPanel node={null} />);
    expect(screen.getByText("Select a node in the graph")).toBeInTheDocument();
  });

  test("shows node identity, type and action", () => {
    render(<NodeDetailPanel node={actionNode} />);
    expect(screen.getByText("task")).toBeInTheDocument();
    expect(screen.getByText("action")).toBeInTheDocument();
    expect(screen.getByText("tool: echo")).toBeInTheDocument();
  });

  test("shows status and formatted duration", () => {
    render(
      <NodeDetailPanel
        node={actionNode}
        step={{
          status: "completed",
          output: null,
          error: null,
          retries: 0,
          started_at: "2026-08-04T07:00:00Z",
          finished_at: "2026-08-04T07:00:01.5Z",
        }}
      />,
    );
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("Duration: 1.5s")).toBeInTheDocument();
  });

  test("shows the error for a failed step", () => {
    render(
      <NodeDetailPanel
        node={actionNode}
        step={{
          status: "failed",
          output: null,
          error: "adapter exploded",
          retries: 0,
          started_at: null,
          finished_at: null,
        }}
      />,
    );
    expect(screen.getByText("adapter exploded")).toBeInTheDocument();
  });

  test("reveals the action output when expanded", () => {
    render(
      <NodeDetailPanel
        node={actionNode}
        step={{
          status: "completed",
          output: { ok: true },
          error: null,
          retries: 0,
          started_at: null,
          finished_at: null,
        }}
      />,
    );
    fireEvent.click(screen.getByText("Action output"));
    expect(screen.getByText(/"ok": true/)).toBeInTheDocument();
  });

  test("renders the token stream when present", () => {
    render(<NodeDetailPanel node={actionNode} tokens="hello world" />);
    fireEvent.click(screen.getByText("Token stream"));
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });

  test("reports when the node has not started", () => {
    render(<NodeDetailPanel node={actionNode} />);
    expect(
      screen.getByText("This node has not started yet."),
    ).toBeInTheDocument();
  });
});
