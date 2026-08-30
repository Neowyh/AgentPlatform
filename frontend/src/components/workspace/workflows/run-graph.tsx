"use client";

import type { Edge as FlowEdge, Node as FlowNode } from "@xyflow/react";
import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import dagre from "dagre";
import {
  BotIcon,
  CombineIcon,
  GitBranchIcon,
  NetworkIcon,
  PauseCircleIcon,
  WrenchIcon,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useMemo } from "react";

import type { RunStatus, WorkflowDetail, WorkflowNode } from "@/core/workflows";
import { cn } from "@/lib/utils";

import "@xyflow/react/dist/style.css";

const NODE_WIDTH = 180;
const NODE_HEIGHT = 56;

const STATUS_CLASS: Record<string, string> = {
  pending: "border-border bg-card text-card-foreground",
  running:
    "animate-pulse border-blue-500 bg-blue-50 text-blue-950 dark:border-blue-400 dark:bg-blue-950/40 dark:text-blue-300",
  completed:
    "border-emerald-500 bg-emerald-50 text-emerald-950 dark:border-emerald-400 dark:bg-emerald-950/40 dark:text-emerald-300",
  failed:
    "border-red-500 bg-red-50 text-red-950 dark:border-red-400 dark:bg-red-950/40 dark:text-red-300",
  skipped:
    "border-amber-500 bg-amber-50 text-amber-950 dark:border-amber-400 dark:bg-amber-950/40 dark:text-amber-300",
  cancelled: "border-border bg-muted/60 text-muted-foreground",
};

const ROUTE_EDGE_STYLE = { strokeDasharray: "6 4" };

function nodeIcon(node: WorkflowNode) {
  switch (node.type) {
    case "route":
      return GitBranchIcon;
    case "fork":
      return NetworkIcon;
    case "join":
      return CombineIcon;
    case "interrupt":
      return PauseCircleIcon;
    default:
      return node.action?.kind === "agent" ? BotIcon : WrenchIcon;
  }
}

function edgeKey(from: string, to: string) {
  return `${from}->${to}`;
}

function layoutPositions(
  workflow: WorkflowDetail,
): Map<string, { x: number; y: number }> {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({
    rankdir: "TB",
    nodesep: 40,
    ranksep: 70,
    marginx: 20,
    marginy: 20,
  });
  for (const node of workflow.nodes)
    graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  for (const edge of workflow.edges) graph.setEdge(edge.from, edge.to);
  dagre.layout(graph);
  const positions = new Map<string, { x: number; y: number }>();
  for (const node of workflow.nodes) {
    const point = graph.node(node.id);
    positions.set(node.id, {
      x: point.x - NODE_WIDTH / 2,
      y: point.y - NODE_HEIGHT / 2,
    });
  }
  return positions;
}

function toFlowNodes(
  workflow: WorkflowDetail,
  runStatus: RunStatus,
  positions: Map<string, { x: number; y: number }>,
  selectedNodeId: string | null,
): FlowNode[] {
  const selectedEdges = runStatus.selected_edges ?? [];
  return workflow.nodes.map((node) => {
    const step = runStatus.steps?.[node.id];
    const status =
      step?.status ??
      (node.type === "route" &&
      selectedEdges.some((edge) => edge.from === node.id)
        ? "completed"
        : "pending");
    const Icon = nodeIcon(node);
    return {
      id: node.id,
      type: "default",
      position: positions.get(node.id) ?? { x: 0, y: 0 },
      draggable: false,
      selected: node.id === selectedNodeId,
      data: {
        label: (
          <div className="flex min-w-0 flex-col gap-0.5 text-left">
            <div className="flex items-center gap-1.5">
              <Icon className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate text-base font-medium">{node.id}</span>
            </div>
            {node.action?.name && (
              <span className="text-muted-foreground truncate text-[10px]">
                {node.action.name}
              </span>
            )}
          </div>
        ),
      },
      className: cn(
        "rounded-lg border shadow-sm",
        STATUS_CLASS[status] ?? STATUS_CLASS.pending,
      ),
      style: { width: NODE_WIDTH },
    } satisfies FlowNode;
  });
}

function toFlowEdges(
  workflow: WorkflowDetail,
  runStatus: RunStatus,
): FlowEdge[] {
  const selected = new Set(
    (runStatus.selected_edges ?? []).map((edge) => edgeKey(edge.from, edge.to)),
  );
  const routeSources = new Set(
    workflow.nodes
      .filter((node) => node.type === "route")
      .map((node) => node.id),
  );
  return workflow.edges.map((edge) => {
    const id = edgeKey(edge.from, edge.to);
    const isSelected = selected.has(id);
    const isRoute = routeSources.has(edge.from);
    return {
      id,
      source: edge.from,
      target: edge.to,
      type: "smoothstep",
      animated: isSelected,
      label:
        edge.max_iterations != null ? `↺ ${edge.max_iterations}` : undefined,
      labelBgStyle: { fill: "var(--background)", fillOpacity: 0.8 },
      style: isSelected
        ? { stroke: "var(--primary)" }
        : isRoute
          ? ROUTE_EDGE_STYLE
          : undefined,
    } satisfies FlowEdge;
  });
}

interface RunGraphProps {
  workflow: WorkflowDetail;
  runStatus: RunStatus;
  selectedNodeId: string | null;
  onSelect: (nodeId: string | null) => void;
}

function RunGraphInner({
  workflow,
  runStatus,
  selectedNodeId,
  onSelect,
}: RunGraphProps) {
  const { fitView } = useReactFlow();
  const { resolvedTheme } = useTheme();
  const positions = useMemo(() => layoutPositions(workflow), [workflow]);
  const nodes = useMemo(
    () => toFlowNodes(workflow, runStatus, positions, selectedNodeId),
    [runStatus, selectedNodeId, workflow, positions],
  );
  const edges = useMemo(
    () => toFlowEdges(workflow, runStatus),
    [runStatus, workflow],
  );

  useEffect(() => {
    if (!runStatus.current_step) return;
    void fitView({
      nodes: [{ id: runStatus.current_step }],
      padding: 0.8,
      maxZoom: 1.25,
      duration: 400,
    });
  }, [fitView, runStatus.current_step]);

  return (
    <ReactFlow
      className={cn(resolvedTheme === "dark" && "dark")}
      nodes={nodes}
      edges={edges}
      fitView
      fitViewOptions={{ padding: 0.15 }}
      nodesDraggable={false}
      nodesConnectable={false}
      minZoom={0.2}
      maxZoom={2}
      onNodeClick={(_event, node) => onSelect(node.id)}
      onPaneClick={() => onSelect(null)}
    >
      <Background bgColor="var(--background)" />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}

export function RunGraph(props: RunGraphProps) {
  return (
    <ReactFlowProvider>
      <div className="size-full">
        <RunGraphInner {...props} />
      </div>
    </ReactFlowProvider>
  );
}
