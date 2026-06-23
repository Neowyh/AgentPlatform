import { describe, expect, test } from "vitest";

import { parseFaultTreeArtifact } from "@/core/artifacts/fault-tree";

describe("parseFaultTreeArtifact", () => {
  test("returns error for invalid JSON", () => {
    const result = parseFaultTreeArtifact("not valid json");
    expect(result.error).toContain("Invalid fault tree JSON");
    expect(result.nodes).toEqual([]);
    expect(result.edges).toEqual([]);
  });

  test("returns error for non-object root", () => {
    const result = parseFaultTreeArtifact('"just a string"');
    expect(result.error).toContain("root value must be an object");
  });

  test("parses a minimal valid fault tree", () => {
    const input = JSON.stringify({
      top_event: "System Failure",
      bottom_events: ["Component A Failed", "Component B Failed"],
    });
    const result = parseFaultTreeArtifact(input);
    expect(result.error).toBeNull();
    expect(result.nodes.length).toBe(3);
    expect(result.nodes[0]!.kind).toBe("top");
    expect(result.nodes[0]!.label).toBe("System Failure");
    expect(result.nodes[1]!.kind).toBe("bottom");
    expect(result.nodes[2]!.kind).toBe("bottom");
  });

  test("parses intermediate events", () => {
    const input = JSON.stringify({
      top_event: "Root Cause",
      intermediate_events: ["Intermediate 1"],
      bottom_events: ["Bottom 1"],
    });
    const result = parseFaultTreeArtifact(input);
    expect(result.error).toBeNull();
    expect(result.nodes.length).toBe(3);
    expect(result.nodes[1]!.kind).toBe("intermediate");
  });

  test("creates fallback edges when no logic provided", () => {
    const input = JSON.stringify({
      top_event: "Root",
      bottom_events: ["B1", "B2"],
    });
    const result = parseFaultTreeArtifact(input);
    expect(result.edges.length).toBe(2);
    expect(result.edges[0]!.source).toBe("TOP");
    expect(result.edges[0]!.label).toBe("OR");
  });

  test("uses logic entries for edges when provided", () => {
    const input = JSON.stringify({
      top_event: "Root",
      bottom_events: ["B1", "B2"],
      logic: [
        { type: "AND", source: "TOP", target: "BE-1" },
        { type: "OR", source: "TOP", target: "BE-2" },
      ],
    });
    const result = parseFaultTreeArtifact(input);
    expect(result.edges.length).toBe(2);
    expect(result.edges[0]!.label).toBe("AND");
    expect(result.edges[1]!.label).toBe("OR");
  });

  test("supports parent/children logic format", () => {
    const input = JSON.stringify({
      top_event: "Root",
      bottom_events: ["B1", "B2"],
      logic: [{ type: "OR", parent: "TOP", children: ["BE-1", "BE-2"] }],
    });
    const result = parseFaultTreeArtifact(input);
    expect(result.edges.length).toBe(2);
    expect(result.edges[0]!.source).toBe("TOP");
  });

  test("summarizes bottom event counts", () => {
    const input = JSON.stringify({
      top_event: "Root",
      bottom_events: [
        { id: "B1", status: "confirmed", confidence: "high" },
        { id: "B2", status: "to_verify", confidence: "medium" },
        { id: "B3", status: "rejected", confidence: "low" },
      ],
    });
    const result = parseFaultTreeArtifact(input);
    expect(result.summary.bottomEventCount).toBe(3);
    expect(result.summary.confirmedCount).toBe(1);
    expect(result.summary.toVerifyCount).toBe(1);
    expect(result.summary.rejectedCount).toBe(1);
    expect(result.summary.confidenceCounts.high).toBe(1);
    expect(result.summary.confidenceCounts.medium).toBe(1);
    expect(result.summary.confidenceCounts.low).toBe(1);
  });

  test("handles duplicate node ids with diagnostic", () => {
    const input = JSON.stringify({
      top_event: { id: "TOP", name: "Root" },
      bottom_events: [
        { id: "TOP", name: "Duplicate" },
        { id: "B1", name: "Normal" },
      ],
    });
    const result = parseFaultTreeArtifact(input);
    expect(result.diagnostics.some((d) => d.includes("Duplicate"))).toBe(true);
  });

  test("ignores logic edges with unknown node ids", () => {
    const input = JSON.stringify({
      top_event: "Root",
      bottom_events: ["B1"],
      logic: [{ type: "AND", source: "UNKNOWN", target: "BE-1" }],
    });
    const result = parseFaultTreeArtifact(input);
    expect(result.diagnostics.some((d) => d.includes("unknown node"))).toBe(
      true,
    );
  });

  test("handles empty string top_event", () => {
    const input = JSON.stringify({ top_event: "" });
    const result = parseFaultTreeArtifact(input);
    expect(result.error).toBeNull();
    expect(result.nodes[0]!.label).toBe("TOP");
  });

  test("normalizes probability values", () => {
    const input = JSON.stringify({
      top_event: "Root",
      bottom_events: [
        { id: "B1", probability: 0.05 },
        { id: "B2", probability: null },
        { id: "B3", probability: "high" },
      ],
    });
    const result = parseFaultTreeArtifact(input);
    expect(result.nodes[1]!.probability).toBe("0.05");
    expect(result.nodes[2]!.probability).toBeNull();
    expect(result.nodes[3]!.probability).toBe("high");
  });

  test("handles node with string value instead of object", () => {
    const input = JSON.stringify({
      top_event: "Root",
      bottom_events: ["Simple String Event"],
    });
    const result = parseFaultTreeArtifact(input);
    expect(result.nodes[1]!.label).toBe("Simple String Event");
    expect(result.nodes[1]!.kind).toBe("bottom");
  });

  test("logic parent/children with unknown nodes emits diagnostic", () => {
    const input = JSON.stringify({
      top_event: "Root",
      bottom_events: ["B1"],
      logic: [{ type: "OR", parent: "UNKNOWN", children: ["BE-1"] }],
    });
    const result = parseFaultTreeArtifact(input);
    expect(result.diagnostics.some((d) => d.includes("unknown node"))).toBe(
      true,
    );
  });

  test("ignores non-object logic entries", () => {
    const input = JSON.stringify({
      top_event: "Root",
      bottom_events: ["B1"],
      logic: ["not an object", 42],
    });
    const result = parseFaultTreeArtifact(input);
    expect(result.diagnostics.some((d) => d.includes("non-object"))).toBe(true);
  });

  test("fallback edges with intermediate nodes", () => {
    const input = JSON.stringify({
      top_event: "Root",
      intermediate_events: ["I1"],
      bottom_events: ["B1", "B2"],
    });
    const result = parseFaultTreeArtifact(input);
    expect(result.edges.length).toBe(3);
    expect(result.edges[0]!.source).toBe("TOP");
    expect(result.edges[0]!.target).toBe("IE-1");
  });
});
