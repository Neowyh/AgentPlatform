import { describe, expect, test } from "vitest";

import { parseFaultTreeArtifact } from "@/core/artifacts/fault-tree";

describe("parseFaultTreeArtifact", () => {
  test("builds graph nodes, edges, and summary from standard fault tree JSON", () => {
    const result = parseFaultTreeArtifact(
      JSON.stringify({
        top_event: "HF-07 heat flux exceeds limit",
        intermediate_events: [
          {
            id: "IE-01",
            name: "Measurement chain anomaly",
            description: "Sensor channel and grounding path need review",
          },
        ],
        bottom_events: [
          {
            id: "BE-01",
            name: "CH-07 zero drift",
            description: "Shutdown zero offset exceeded normal range",
            evidence: ["zero_offset"],
            probability: "medium",
            confidence: "high",
            status: "likely",
          },
          {
            id: "BE-02",
            name: "Local flow anomaly",
            probability: null,
            confidence: "low",
            status: "to_verify",
          },
        ],
        logic: [
          { source: "TOP", target: "IE-01", type: "OR" },
          { parent: "IE-01", children: ["BE-01", "BE-02"], type: "OR" },
        ],
      }),
    );

    expect(result.error).toBeNull();
    expect(result.nodes.map((node) => node.id)).toEqual([
      "TOP",
      "IE-01",
      "BE-01",
      "BE-02",
    ]);
    expect(
      result.edges.map((edge) => `${edge.source}->${edge.target}`),
    ).toEqual(["TOP->IE-01", "IE-01->BE-01", "IE-01->BE-02"]);
    expect(result.summary).toEqual({
      bottomEventCount: 2,
      toVerifyCount: 1,
      rejectedCount: 0,
      confirmedCount: 0,
      confidenceCounts: { high: 1, medium: 0, low: 1, unknown: 0 },
    });
  });

  test("falls back to deterministic layered edges when logic is missing", () => {
    const result = parseFaultTreeArtifact(
      JSON.stringify({
        top_event: "Top event",
        intermediate_events: ["Branch A", "Branch B"],
        bottom_events: [{ id: "BE-01", name: "Bottom event" }],
        logic: [],
      }),
    );

    expect(result.error).toBeNull();
    expect(result.diagnostics).toContain(
      "No usable logic entries found; rendered a layered fallback graph.",
    );
    expect(
      result.edges.map((edge) => `${edge.source}->${edge.target}`),
    ).toEqual(["TOP->IE-1", "TOP->IE-2", "IE-1->BE-01", "IE-2->BE-01"]);
  });

  test("reports invalid JSON without throwing", () => {
    const result = parseFaultTreeArtifact("{not-json");

    expect(result.nodes).toEqual([]);
    expect(result.edges).toEqual([]);
    expect(result.error).toContain("Invalid fault tree JSON");
  });

  test("deduplicates repeated node ids and records a diagnostic", () => {
    const result = parseFaultTreeArtifact(
      JSON.stringify({
        top_event: "Top event",
        intermediate_events: [{ id: "DUP", name: "First" }],
        bottom_events: [{ id: "DUP", name: "Second" }],
        logic: [],
      }),
    );

    expect(result.nodes.map((node) => node.id)).toEqual(["TOP", "DUP"]);
    expect(result.diagnostics).toContain(
      "Duplicate fault tree node id ignored: DUP",
    );
  });
});
