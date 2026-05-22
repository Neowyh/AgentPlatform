export type FaultTreeNodeKind = "top" | "intermediate" | "bottom";

export type FaultTreeNode = {
  id: string;
  label: string;
  description: string;
  kind: FaultTreeNodeKind;
  probability: string | null;
  confidence: string;
  status: string;
};

export type FaultTreeEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
};

export type FaultTreeSummary = {
  bottomEventCount: number;
  toVerifyCount: number;
  rejectedCount: number;
  confirmedCount: number;
  confidenceCounts: {
    high: number;
    medium: number;
    low: number;
    unknown: number;
  };
};

export type FaultTreeParseResult = {
  nodes: FaultTreeNode[];
  edges: FaultTreeEdge[];
  summary: FaultTreeSummary;
  diagnostics: string[];
  error: string | null;
};

type FaultTreeRecord = {
  top_event?: unknown;
  intermediate_events?: unknown;
  bottom_events?: unknown;
  logic?: unknown;
};

const EMPTY_SUMMARY: FaultTreeSummary = {
  bottomEventCount: 0,
  toVerifyCount: 0,
  rejectedCount: 0,
  confirmedCount: 0,
  confidenceCounts: {
    high: 0,
    medium: 0,
    low: 0,
    unknown: 0,
  },
};

function valueToString(value: unknown, fallback = "") {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return fallback;
}

function valueToArray(value: unknown) {
  return Array.isArray(value) ? value : [];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeProbability(value: unknown) {
  if (value === null || value === undefined || value === "") return null;
  return valueToString(value, "unknown");
}

function nodeFromValue(
  value: unknown,
  kind: FaultTreeNodeKind,
  fallbackId: string,
) {
  if (isRecord(value)) {
    const id = valueToString(value.id, fallbackId);
    const label =
      valueToString(value.name) ||
      valueToString(value.label) ||
      valueToString(value.title) ||
      id;
    return {
      id,
      label,
      description: valueToString(value.description),
      kind,
      probability: normalizeProbability(value.probability),
      confidence: valueToString(value.confidence, "unknown").toLowerCase(),
      status: valueToString(value.status, "unknown").toLowerCase(),
    } satisfies FaultTreeNode;
  }

  const label = valueToString(value, fallbackId);
  return {
    id: fallbackId,
    label,
    description: "",
    kind,
    probability: null,
    confidence: "unknown",
    status: "unknown",
  } satisfies FaultTreeNode;
}

function addNode(
  nodes: FaultTreeNode[],
  seen: Set<string>,
  node: FaultTreeNode,
  diagnostics: string[],
) {
  if (seen.has(node.id)) {
    diagnostics.push(`Duplicate fault tree node id ignored: ${node.id}`);
    return;
  }
  seen.add(node.id);
  nodes.push(node);
}

function makeEdge(source: string, target: string, label: string) {
  return {
    id: `${source}->${target}:${label || "logic"}`,
    source,
    target,
    label,
  } satisfies FaultTreeEdge;
}

function edgesFromLogic(logic: unknown, validNodeIds: Set<string>) {
  const edges: FaultTreeEdge[] = [];
  const diagnostics: string[] = [];

  for (const entry of valueToArray(logic)) {
    if (!isRecord(entry)) {
      diagnostics.push("Ignored non-object logic entry.");
      continue;
    }

    const label = valueToString(entry.type);
    const source = valueToString(entry.source);
    const target = valueToString(entry.target);
    if (source && target) {
      if (validNodeIds.has(source) && validNodeIds.has(target)) {
        edges.push(makeEdge(source, target, label));
      } else {
        diagnostics.push(
          `Ignored logic edge with unknown node: ${source}->${target}`,
        );
      }
      continue;
    }

    const parent = valueToString(entry.parent);
    const children = valueToArray(entry.children).map((child) =>
      valueToString(child),
    );
    if (parent && children.length > 0) {
      for (const child of children) {
        if (validNodeIds.has(parent) && validNodeIds.has(child)) {
          edges.push(makeEdge(parent, child, label));
        } else {
          diagnostics.push(
            `Ignored logic edge with unknown node: ${parent}->${child}`,
          );
        }
      }
      continue;
    }

    diagnostics.push("Ignored unsupported logic entry.");
  }

  return { edges, diagnostics };
}

function fallbackEdges(nodes: FaultTreeNode[]) {
  const top = nodes.find((node) => node.kind === "top");
  const intermediateNodes = nodes.filter(
    (node) => node.kind === "intermediate",
  );
  const bottomNodes = nodes.filter((node) => node.kind === "bottom");

  if (!top) return [];
  if (intermediateNodes.length === 0) {
    return bottomNodes.map((bottom) => makeEdge(top.id, bottom.id, "OR"));
  }

  return [
    ...intermediateNodes.map((node) => makeEdge(top.id, node.id, "OR")),
    ...intermediateNodes.flatMap((intermediate) =>
      bottomNodes.map((bottom) => makeEdge(intermediate.id, bottom.id, "OR")),
    ),
  ];
}

function summarize(nodes: FaultTreeNode[]) {
  const summary: FaultTreeSummary = structuredClone(EMPTY_SUMMARY);
  for (const node of nodes.filter((item) => item.kind === "bottom")) {
    summary.bottomEventCount += 1;

    if (node.status === "to_verify") summary.toVerifyCount += 1;
    if (node.status === "rejected") summary.rejectedCount += 1;
    if (node.status === "confirmed") summary.confirmedCount += 1;

    if (node.confidence === "high") summary.confidenceCounts.high += 1;
    else if (node.confidence === "medium") summary.confidenceCounts.medium += 1;
    else if (node.confidence === "low") summary.confidenceCounts.low += 1;
    else summary.confidenceCounts.unknown += 1;
  }
  return summary;
}

export function parseFaultTreeArtifact(content: string): FaultTreeParseResult {
  let parsed: FaultTreeRecord;
  try {
    parsed = JSON.parse(content) as FaultTreeRecord;
  } catch (error) {
    return {
      nodes: [],
      edges: [],
      summary: structuredClone(EMPTY_SUMMARY),
      diagnostics: [],
      error: `Invalid fault tree JSON: ${
        error instanceof Error ? error.message : String(error)
      }`,
    };
  }

  if (!isRecord(parsed)) {
    return {
      nodes: [],
      edges: [],
      summary: structuredClone(EMPTY_SUMMARY),
      diagnostics: [],
      error: "Invalid fault tree JSON: root value must be an object.",
    };
  }

  const diagnostics: string[] = [];
  const nodes: FaultTreeNode[] = [];
  const seen = new Set<string>();

  addNode(
    nodes,
    seen,
    nodeFromValue(
      { id: "TOP", name: valueToString(parsed.top_event, "Top event") },
      "top",
      "TOP",
    ),
    diagnostics,
  );

  valueToArray(parsed.intermediate_events).forEach((event, index) => {
    addNode(
      nodes,
      seen,
      nodeFromValue(event, "intermediate", `IE-${index + 1}`),
      diagnostics,
    );
  });

  valueToArray(parsed.bottom_events).forEach((event, index) => {
    addNode(
      nodes,
      seen,
      nodeFromValue(event, "bottom", `BE-${index + 1}`),
      diagnostics,
    );
  });

  const logicResult = edgesFromLogic(
    parsed.logic,
    new Set(nodes.map((node) => node.id)),
  );
  diagnostics.push(...logicResult.diagnostics);

  let edges = logicResult.edges;
  if (edges.length === 0) {
    edges = fallbackEdges(nodes);
    diagnostics.push(
      "No usable logic entries found; rendered a layered fallback graph.",
    );
  }

  return {
    nodes,
    edges,
    summary: summarize(nodes),
    diagnostics,
    error: null,
  };
}
