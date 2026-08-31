"use client";

import type { Edge as FlowEdge, Node as FlowNode } from "@xyflow/react";
import { ReactFlow, Background, Controls } from "@xyflow/react";
import { useTheme } from "next-themes";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  parseFaultTreeArtifact,
  type FaultTreeNode,
} from "@/core/artifacts/fault-tree";
import { cn } from "@/lib/utils";

import "@xyflow/react/dist/style.css";

const NODE_WIDTH = 220;
const X_GAP = 280;
const Y_BY_KIND = {
  top: 40,
  intermediate: 230,
  bottom: 430,
} as const;

const STATUS_CLASS: Record<string, string> = {
  confirmed:
    "border-emerald-500 bg-emerald-50 text-emerald-950 dark:border-emerald-400 dark:bg-emerald-950/40 dark:text-emerald-300",
  likely:
    "border-amber-500 bg-amber-50 text-amber-950 dark:border-amber-400 dark:bg-amber-950/40 dark:text-amber-300",
  to_verify:
    "border-sky-500 bg-sky-50 text-sky-950 dark:border-sky-400 dark:bg-sky-950/40 dark:text-sky-300",
  rejected:
    "border-zinc-400 bg-zinc-50 text-zinc-800 dark:border-zinc-500 dark:bg-zinc-900/40 dark:text-zinc-300",
  unknown: "border-border bg-card text-card-foreground",
};

function statusClass(status: string) {
  return STATUS_CLASS[status] ?? STATUS_CLASS.unknown;
}

function centeredX(index: number, count: number) {
  return (index - (count - 1) / 2) * X_GAP;
}

function nodePosition(node: FaultTreeNode, index: number, siblings: number) {
  return {
    x: centeredX(index, siblings),
    y: Y_BY_KIND[node.kind],
  };
}

function toFlowNodes(nodes: FaultTreeNode[]): FlowNode[] {
  const counts = {
    top: nodes.filter((node) => node.kind === "top").length,
    intermediate: nodes.filter((node) => node.kind === "intermediate").length,
    bottom: nodes.filter((node) => node.kind === "bottom").length,
  };
  const indexes = { top: 0, intermediate: 0, bottom: 0 };

  return nodes.map((node) => {
    const index = indexes[node.kind]++;
    const position = nodePosition(node, index, counts[node.kind]);
    const badges = [
      node.status !== "unknown" ? node.status : null,
      node.confidence !== "unknown" ? `${node.confidence} confidence` : null,
      node.probability ? `P: ${node.probability}` : null,
    ].filter(Boolean);

    return {
      id: node.id,
      type: "default",
      position,
      draggable: false,
      selectable: false,
      data: {
        label: (
          <div className="flex max-w-[200px] flex-col gap-2 text-left">
            <div className="type-body leading-snug font-medium break-words">
              {node.label}
            </div>
            {node.description && (
              <div className="text-muted-foreground type-body line-clamp-3 leading-snug break-words">
                {node.description}
              </div>
            )}
            {badges.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {badges.map((badge) => (
                  <Badge
                    key={badge}
                    className="type-compact max-w-full truncate"
                    variant="outline"
                  >
                    {badge}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        ),
      },
      style: {
        width: NODE_WIDTH,
        borderRadius: 8,
      },
      className: cn("border shadow-sm", statusClass(node.status)),
    } satisfies FlowNode;
  });
}

function toFlowEdges(
  edges: ReturnType<typeof parseFaultTreeArtifact>["edges"],
) {
  return edges.map(
    (edge) =>
      ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label || undefined,
        animated: false,
        type: "smoothstep",
      }) satisfies FlowEdge,
  );
}

export function FaultTreeViewer({ content }: { content: string }) {
  const result = parseFaultTreeArtifact(content);
  const { resolvedTheme } = useTheme();

  if (result.error) {
    return (
      <div className="p-4">
        <Alert variant="destructive">
          <AlertTitle>Fault tree preview unavailable</AlertTitle>
          <AlertDescription>{result.error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="flex size-full flex-col">
      <div className="border-border bg-background/80 type-body grid shrink-0 grid-cols-2 gap-2 border-b p-3 md:grid-cols-4">
        <SummaryItem
          label="Bottom events"
          value={result.summary.bottomEventCount}
        />
        <SummaryItem label="To verify" value={result.summary.toVerifyCount} />
        <SummaryItem label="Rejected" value={result.summary.rejectedCount} />
        <SummaryItem
          label="High confidence"
          value={result.summary.confidenceCounts.high}
        />
      </div>
      {result.diagnostics.length > 0 && (
        <div className="border-border bg-muted/40 type-body shrink-0 border-b px-4 py-2">
          {result.diagnostics.join(" ")}
        </div>
      )}
      <div className="min-h-0 grow">
        <ReactFlow
          className={cn(resolvedTheme === "dark" && "dark")}
          nodes={toFlowNodes(result.nodes)}
          edges={toFlowEdges(result.edges)}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          minZoom={0.3}
          maxZoom={1.5}
        >
          <Background bgColor="var(--background)" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </div>
  );
}

function SummaryItem({ label, value }: { label: string; value: number }) {
  return (
    <div className="border-border bg-card rounded-md border p-2">
      <div className="text-muted-foreground type-body">{label}</div>
      <div className="type-body font-semibold">{value}</div>
    </div>
  );
}
