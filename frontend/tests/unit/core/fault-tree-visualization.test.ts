import { describe, expect, test } from "vitest";

import { parseFaultTreeArtifact } from "@/core/artifacts/fault-tree";

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

/** Build a minimal valid fault-tree payload. */
function makePayload(overrides: Record<string, unknown> = {}) {
  return {
    top_event: "Top event",
    bottom_events: [
      {
        id: "BE-01",
        name: "Bottom 1",
        confidence: "high",
        status: "confirmed",
      },
    ],
    logic: [],
    ...overrides,
  };
}

function okTree(json: Record<string, unknown>) {
  return parseFaultTreeArtifact(JSON.stringify(json));
}

// ===========================================================================
// parseFaultTreeArtifact – happy path
// ===========================================================================

describe("parseFaultTreeArtifact", () => {
  test("builds graph nodes, edges, and summary from standard fault tree JSON", () => {
    const result = okTree({
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
    });

    expect(result.error).toBeNull();
    expect(result.nodes.map((n) => n.id)).toEqual([
      "TOP",
      "IE-01",
      "BE-01",
      "BE-02",
    ]);
    expect(result.edges.map((e) => `${e.source}->${e.target}`)).toEqual([
      "TOP->IE-01",
      "IE-01->BE-01",
      "IE-01->BE-02",
    ]);
    expect(result.summary).toEqual({
      bottomEventCount: 2,
      toVerifyCount: 1,
      rejectedCount: 0,
      confirmedCount: 0,
      confidenceCounts: { high: 1, medium: 0, low: 1, unknown: 0 },
    });
  });

  // -----------------------------------------------------------------------
  // JSON parsing errors
  // -----------------------------------------------------------------------

  test("reports invalid JSON without throwing", () => {
    const result = parseFaultTreeArtifact("{not-json");
    expect(result.nodes).toEqual([]);
    expect(result.edges).toEqual([]);
    expect(result.error).toContain("Invalid fault tree JSON");
  });

  test("includes the original error message when JSON parse fails", () => {
    const result = parseFaultTreeArtifact("{bad");
    // The JSON.parse error message should be embedded
    expect(result.error).toMatch(/Invalid fault tree JSON/);
    expect(result.error!.length).toBeGreaterThan(
      "Invalid fault tree JSON: ".length,
    );
  });

  test("returns error when root JSON value is a non-object (e.g. array)", () => {
    const result = parseFaultTreeArtifact('["not", "an", "object"]');
    expect(result.error).toBe(
      "Invalid fault tree JSON: root value must be an object.",
    );
    expect(result.nodes).toEqual([]);
    expect(result.edges).toEqual([]);
    expect(result.diagnostics).toEqual([]);
  });

  test("returns error when root JSON value is a non-object (e.g. string)", () => {
    const result = parseFaultTreeArtifact('"just a string"');
    expect(result.error).toBe(
      "Invalid fault tree JSON: root value must be an object.",
    );
  });

  test("returns error when root JSON value is a number", () => {
    const result = parseFaultTreeArtifact("42");
    expect(result.error).toBe(
      "Invalid fault tree JSON: root value must be an object.",
    );
  });

  test("returns error when root JSON value is null", () => {
    const result = parseFaultTreeArtifact("null");
    expect(result.error).toBe(
      "Invalid fault tree JSON: root value must be an object.",
    );
  });

  test("returns error when root JSON value is boolean", () => {
    const result = parseFaultTreeArtifact("true");
    expect(result.error).toBe(
      "Invalid fault tree JSON: root value must be an object.",
    );
  });

  // -----------------------------------------------------------------------
  // Deduplication
  // -----------------------------------------------------------------------

  test("deduplicates repeated node ids and records a diagnostic", () => {
    const result = okTree({
      top_event: "Top event",
      intermediate_events: [{ id: "DUP", name: "First" }],
      bottom_events: [{ id: "DUP", name: "Second" }],
      logic: [],
    });

    expect(result.nodes.map((n) => n.id)).toEqual(["TOP", "DUP"]);
    expect(result.diagnostics).toContain(
      "Duplicate fault tree node id ignored: DUP",
    );
  });

  test("deduplicates when bottom event has same id as TOP", () => {
    const result = okTree({
      top_event: "Top event",
      bottom_events: [{ id: "TOP", name: "Conflicting" }],
      logic: [],
    });

    // Only one TOP node should exist
    expect(result.nodes.filter((n) => n.id === "TOP")).toHaveLength(1);
    expect(result.diagnostics).toContain(
      "Duplicate fault tree node id ignored: TOP",
    );
  });

  // -----------------------------------------------------------------------
  // top_event handling
  // -----------------------------------------------------------------------

  test("uses default top event label when top_event is missing", () => {
    const result = okTree({ bottom_events: [], logic: [] });
    const top = result.nodes.find((n) => n.kind === "top");
    expect(top).toBeDefined();
    expect(top!.label).toBe("Top event");
  });

  test("falls through to id label when top_event is empty string", () => {
    const result = okTree({ top_event: "", bottom_events: [], logic: [] });
    const top = result.nodes.find((n) => n.kind === "top");
    // valueToString("", "Top event") returns "" since it IS a string.
    // Then nodeFromValue sees name="" which is falsy, falls through to id="TOP".
    expect(top!.label).toBe("TOP");
  });

  test("converts numeric top_event to string", () => {
    const result = okTree({ top_event: 12345, bottom_events: [], logic: [] });
    const top = result.nodes.find((n) => n.kind === "top");
    expect(top!.label).toBe("12345");
  });

  test("converts boolean top_event to string", () => {
    const result = okTree({ top_event: true, bottom_events: [], logic: [] });
    const top = result.nodes.find((n) => n.kind === "top");
    expect(top!.label).toBe("true");
  });

  // -----------------------------------------------------------------------
  // nodeFromValue – non-record (primitive) values
  // -----------------------------------------------------------------------

  test("creates default node from primitive intermediate event (string)", () => {
    const result = okTree({
      top_event: "T",
      intermediate_events: ["Simple branch"],
      logic: [],
    });
    const ie = result.nodes.find((n) => n.kind === "intermediate");
    expect(ie).toBeDefined();
    expect(ie!.label).toBe("Simple branch");
    expect(ie!.id).toBe("IE-1");
    expect(ie!.description).toBe("");
    expect(ie!.probability).toBeNull();
    expect(ie!.confidence).toBe("unknown");
    expect(ie!.status).toBe("unknown");
  });

  test("creates default node from numeric bottom event", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [42],
      logic: [],
    });
    const be = result.nodes.find((n) => n.kind === "bottom");
    expect(be).toBeDefined();
    expect(be!.label).toBe("42");
    expect(be!.id).toBe("BE-1");
  });

  test("creates default node from boolean bottom event", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [false],
      logic: [],
    });
    const be = result.nodes.find((n) => n.kind === "bottom");
    expect(be!.label).toBe("false");
  });

  test("uses fallbackId as label when primitive value is null/undefined", () => {
    const result = okTree({
      top_event: "T",
      intermediate_events: [null],
      bottom_events: [undefined],
      logic: [],
    });
    const ie = result.nodes.find((n) => n.kind === "intermediate");
    expect(ie!.label).toBe("IE-1");
    const be = result.nodes.find((n) => n.kind === "bottom");
    expect(be!.label).toBe("BE-1");
  });

  // -----------------------------------------------------------------------
  // nodeFromValue – label fallback chain
  // -----------------------------------------------------------------------

  test("uses name for label when present", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1", name: "ByName" }],
      logic: [],
    });
    expect(result.nodes.find((n) => n.id === "B1")!.label).toBe("ByName");
  });

  test("falls back to label field when name is absent", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1", label: "ByLabel" }],
      logic: [],
    });
    expect(result.nodes.find((n) => n.id === "B1")!.label).toBe("ByLabel");
  });

  test("falls back to title field when name and label are absent", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1", title: "ByTitle" }],
      logic: [],
    });
    expect(result.nodes.find((n) => n.id === "B1")!.label).toBe("ByTitle");
  });

  test("falls back to id when name, label, and title are all absent", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1" }],
      logic: [],
    });
    expect(result.nodes.find((n) => n.id === "B1")!.label).toBe("B1");
  });

  test("falls back to id when name is empty string", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1", name: "" }],
      logic: [],
    });
    // empty string is falsy, so it falls through to id
    expect(result.nodes.find((n) => n.id === "B1")!.label).toBe("B1");
  });

  test("uses fallbackId when record has no id field", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ name: "NoIdEvent" }],
      logic: [],
    });
    expect(result.nodes.find((n) => n.kind === "bottom")!.id).toBe("BE-1");
    expect(result.nodes.find((n) => n.kind === "bottom")!.label).toBe(
      "NoIdEvent",
    );
  });

  // -----------------------------------------------------------------------
  // normalizeProbability
  // -----------------------------------------------------------------------

  test("normalizes probability null to null", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1", probability: null }],
      logic: [],
    });
    expect(result.nodes.find((n) => n.id === "B1")!.probability).toBeNull();
  });

  test("normalizes probability undefined to null", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1" }],
      logic: [],
    });
    expect(result.nodes.find((n) => n.id === "B1")!.probability).toBeNull();
  });

  test("normalizes probability empty string to null", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1", probability: "" }],
      logic: [],
    });
    expect(result.nodes.find((n) => n.id === "B1")!.probability).toBeNull();
  });

  test("converts numeric probability to string", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1", probability: 0.95 }],
      logic: [],
    });
    expect(result.nodes.find((n) => n.id === "B1")!.probability).toBe("0.95");
  });

  test("converts boolean probability to string", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1", probability: true }],
      logic: [],
    });
    expect(result.nodes.find((n) => n.id === "B1")!.probability).toBe("true");
  });

  test("uses 'unknown' fallback for object probability via valueToString", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1", probability: { foo: "bar" } }],
      logic: [],
    });
    // valueToString({}, "unknown") returns "unknown" because object is not string/number/boolean
    expect(result.nodes.find((n) => n.id === "B1")!.probability).toBe(
      "unknown",
    );
  });

  // -----------------------------------------------------------------------
  // confidence and status defaults
  // -----------------------------------------------------------------------

  test("defaults confidence and status to 'unknown' when absent", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1" }],
      logic: [],
    });
    const b1 = result.nodes.find((n) => n.id === "B1")!;
    expect(b1.confidence).toBe("unknown");
    expect(b1.status).toBe("unknown");
  });

  test("lowercases confidence and status values", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1", confidence: "HIGH", status: "CONFIRMED" }],
      logic: [],
    });
    const b1 = result.nodes.find((n) => n.id === "B1")!;
    expect(b1.confidence).toBe("high");
    expect(b1.status).toBe("confirmed");
  });

  // -----------------------------------------------------------------------
  // edgesFromLogic – source/target path
  // -----------------------------------------------------------------------

  test("creates edges from source/target logic entries", () => {
    const result = okTree({
      top_event: "T",
      intermediate_events: [{ id: "IE-01", name: "Mid" }],
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [
        { source: "TOP", target: "IE-01", type: "AND" },
        { source: "IE-01", target: "BE-01", type: "OR" },
      ],
    });

    expect(result.edges).toHaveLength(2);
    expect(result.edges[0]!.id).toBe("TOP->IE-01:AND");
    expect(result.edges[0]!.label).toBe("AND");
    expect(result.edges[1]!.id).toBe("IE-01->BE-01:OR");
  });

  test("creates edge with 'logic' label when type is absent", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [{ source: "TOP", target: "BE-01" }],
    });

    expect(result.edges[0]!.id).toBe("TOP->BE-01:logic");
    expect(result.edges[0]!.label).toBe("");
  });

  test("ignores logic edge when source node does not exist and records diagnostic", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [{ source: "UNKNOWN", target: "BE-01", type: "OR" }],
    });

    // The invalid edge is rejected; since no valid edges remain, fallback kicks in
    expect(result.diagnostics).toContain(
      "Ignored logic edge with unknown node: UNKNOWN->BE-01",
    );
    expect(result.diagnostics).toContain(
      "No usable logic entries found; rendered a layered fallback graph.",
    );
    // Fallback generates TOP->BE-01
    expect(result.edges).toHaveLength(1);
    expect(result.edges[0]!.source).toBe("TOP");
  });

  test("ignores logic edge when target node does not exist and records diagnostic", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [{ source: "TOP", target: "UNKNOWN", type: "OR" }],
    });

    expect(result.diagnostics).toContain(
      "Ignored logic edge with unknown node: TOP->UNKNOWN",
    );
    expect(result.diagnostics).toContain(
      "No usable logic entries found; rendered a layered fallback graph.",
    );
  });

  // -----------------------------------------------------------------------
  // edgesFromLogic – parent/children path
  // -----------------------------------------------------------------------

  test("creates edges from parent/children logic entries", () => {
    const result = okTree({
      top_event: "T",
      intermediate_events: [{ id: "IE-01", name: "Mid" }],
      bottom_events: [
        { id: "BE-01", name: "Bot1" },
        { id: "BE-02", name: "Bot2" },
      ],
      logic: [{ parent: "IE-01", children: ["BE-01", "BE-02"], type: "AND" }],
    });

    expect(result.edges).toHaveLength(2);
    expect(result.edges.map((e) => `${e.source}->${e.target}`)).toEqual([
      "IE-01->BE-01",
      "IE-01->BE-02",
    ]);
    expect(result.edges[0]!.label).toBe("AND");
  });

  test("ignores parent/children edge when parent does not exist", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [{ parent: "UNKNOWN", children: ["BE-01"], type: "OR" }],
    });

    expect(result.diagnostics).toContain(
      "Ignored logic edge with unknown node: UNKNOWN->BE-01",
    );
    // Since no valid logic edges, fallback edges are generated
    expect(result.diagnostics).toContain(
      "No usable logic entries found; rendered a layered fallback graph.",
    );
  });

  test("ignores parent/children edge when child does not exist", () => {
    const result = okTree({
      top_event: "T",
      intermediate_events: [{ id: "IE-01", name: "Mid" }],
      logic: [{ parent: "IE-01", children: ["UNKNOWN"], type: "OR" }],
    });

    expect(result.diagnostics).toContain(
      "Ignored logic edge with unknown node: IE-01->UNKNOWN",
    );
    expect(result.diagnostics).toContain(
      "No usable logic entries found; rendered a layered fallback graph.",
    );
  });

  // -----------------------------------------------------------------------
  // edgesFromLogic – skipped / ignored entries
  // -----------------------------------------------------------------------

  test("ignores non-object logic entries with diagnostic", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: ["not-an-object", 42, null],
    });

    // Each non-object entry produces a diagnostic
    const nonObjectDiags = result.diagnostics.filter(
      (d) => d === "Ignored non-object logic entry.",
    );
    expect(nonObjectDiags).toHaveLength(3);
    // Since no valid logic edges, fallback edges are generated
    expect(result.diagnostics).toContain(
      "No usable logic entries found; rendered a layered fallback graph.",
    );
    expect(result.edges).toHaveLength(1);
    expect(result.edges[0]!.source).toBe("TOP");
    expect(result.edges[0]!.target).toBe("BE-01");
  });

  test("ignores unsupported logic entry (no source/target or parent/children)", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [{ random_field: "value" }],
    });

    expect(result.diagnostics).toContain("Ignored unsupported logic entry.");
  });

  test("ignores logic entry with source but no target", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [{ source: "TOP" }],
    });

    // source="" is falsy after valueToString (source is "TOP" but target is "")
    // Actually source="TOP" is truthy, target="" is falsy, so it won't enter the source/target branch
    // Then parent="" is falsy, so it falls to unsupported
    expect(result.diagnostics).toContain("Ignored unsupported logic entry.");
  });

  test("ignores logic entry with target but no source", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [{ target: "BE-01" }],
    });

    expect(result.diagnostics).toContain("Ignored unsupported logic entry.");
  });

  test("ignores logic entry with empty children array", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [{ parent: "TOP", children: [] }],
    });

    // parent is truthy but children.length === 0, falls to unsupported
    expect(result.diagnostics).toContain("Ignored unsupported logic entry.");
  });

  test("ignores logic entry with non-array children", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [{ parent: "TOP", children: "not-array" }],
    });

    // children becomes [] via valueToArray, so children.length === 0
    expect(result.diagnostics).toContain("Ignored unsupported logic entry.");
  });

  test("uses parent/children path when source/target are missing strings", () => {
    const result = okTree({
      top_event: "T",
      intermediate_events: [{ id: "IE-01", name: "Mid" }],
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [{ source: "", target: "", parent: "TOP", children: ["IE-01"] }],
    });

    // source="" and target="" are falsy, falls to parent/children path
    expect(result.edges).toHaveLength(1);
    expect(result.edges[0]!.source).toBe("TOP");
    expect(result.edges[0]!.target).toBe("IE-01");
  });

  // -----------------------------------------------------------------------
  // edgesFromLogic – label from type field
  // -----------------------------------------------------------------------

  test("uses type field as edge label", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [{ source: "TOP", target: "BE-01", type: "XOR" }],
    });

    expect(result.edges[0]!.label).toBe("XOR");
  });

  test("edge label defaults to empty string when type is missing", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [{ source: "TOP", target: "BE-01" }],
    });

    expect(result.edges[0]!.label).toBe("");
  });

  // -----------------------------------------------------------------------
  // fallbackEdges
  // -----------------------------------------------------------------------

  test("falls back to layered edges when logic is empty", () => {
    const result = okTree({
      top_event: "T",
      intermediate_events: ["Branch A", "Branch B"],
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [],
    });

    expect(result.diagnostics).toContain(
      "No usable logic entries found; rendered a layered fallback graph.",
    );
    expect(result.edges.map((e) => `${e.source}->${e.target}`)).toEqual([
      "TOP->IE-1",
      "TOP->IE-2",
      "IE-1->BE-01",
      "IE-2->BE-01",
    ]);
  });

  test("falls back to direct top->bottom edges when no intermediates and no logic", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [
        { id: "BE-01", name: "Bot1" },
        { id: "BE-02", name: "Bot2" },
      ],
      logic: [],
    });

    expect(result.diagnostics).toContain(
      "No usable logic entries found; rendered a layered fallback graph.",
    );
    expect(result.edges.map((e) => `${e.source}->${e.target}`)).toEqual([
      "TOP->BE-01",
      "TOP->BE-02",
    ]);
    expect(result.edges[0]!.label).toBe("OR");
  });

  test("returns no fallback edges when there is no top node", () => {
    // Manually craft a case where top node is deduplicated away
    const result = okTree({
      top_event: "T",
      intermediate_events: [{ id: "TOP", name: "Conflicting" }],
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [],
    });

    // TOP was already added as top, so the intermediate with id "TOP" is deduped
    // There is still a top node, so fallback edges will be generated
    expect(result.nodes.find((n) => n.kind === "top")).toBeDefined();
  });

  test("generates no fallback edges when nodes array has no top and no others", () => {
    // An empty tree with no events
    const result = okTree({
      top_event: "T",
      bottom_events: [],
      logic: [],
    });

    // Only TOP exists, no bottom or intermediate nodes to connect
    expect(result.nodes).toHaveLength(1);
    expect(result.edges).toHaveLength(0);
  });

  test("does not use fallback when valid logic edges exist", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [{ source: "TOP", target: "BE-01", type: "OR" }],
    });

    expect(result.diagnostics).not.toContain(
      "No usable logic entries found; rendered a layered fallback graph.",
    );
    expect(result.edges).toHaveLength(1);
  });

  // -----------------------------------------------------------------------
  // summarize – all status and confidence combinations
  // -----------------------------------------------------------------------

  test("counts to_verify status correctly", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1", status: "to_verify", confidence: "unknown" }],
      logic: [],
    });
    expect(result.summary.toVerifyCount).toBe(1);
    expect(result.summary.rejectedCount).toBe(0);
    expect(result.summary.confirmedCount).toBe(0);
  });

  test("counts rejected status correctly", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1", status: "rejected", confidence: "unknown" }],
      logic: [],
    });
    expect(result.summary.rejectedCount).toBe(1);
    expect(result.summary.toVerifyCount).toBe(0);
  });

  test("counts confirmed status correctly", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1", status: "confirmed", confidence: "unknown" }],
      logic: [],
    });
    expect(result.summary.confirmedCount).toBe(1);
  });

  test("counts high confidence correctly", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1", confidence: "high" }],
      logic: [],
    });
    expect(result.summary.confidenceCounts).toEqual({
      high: 1,
      medium: 0,
      low: 0,
      unknown: 0,
    });
  });

  test("counts medium confidence correctly", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1", confidence: "medium" }],
      logic: [],
    });
    expect(result.summary.confidenceCounts).toEqual({
      high: 0,
      medium: 1,
      low: 0,
      unknown: 0,
    });
  });

  test("counts low confidence correctly", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1", confidence: "low" }],
      logic: [],
    });
    expect(result.summary.confidenceCounts).toEqual({
      high: 0,
      medium: 0,
      low: 1,
      unknown: 0,
    });
  });

  test("counts unknown confidence for non-standard values", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "B1", confidence: "very_high" }],
      logic: [],
    });
    expect(result.summary.confidenceCounts).toEqual({
      high: 0,
      medium: 0,
      low: 0,
      unknown: 1,
    });
  });

  test("only counts bottom events in summary, not intermediate or top", () => {
    const result = okTree({
      top_event: "T",
      intermediate_events: [
        { id: "IE-01", confidence: "high", status: "confirmed" },
      ],
      bottom_events: [{ id: "BE-01", confidence: "low", status: "rejected" }],
      logic: [],
    });

    expect(result.summary.bottomEventCount).toBe(1);
    expect(result.summary.rejectedCount).toBe(1);
    expect(result.summary.confidenceCounts.low).toBe(1);
    expect(result.summary.confidenceCounts.high).toBe(0);
  });

  test("summarizes multiple bottom events with mixed statuses and confidences", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [
        { id: "B1", status: "confirmed", confidence: "high" },
        { id: "B2", status: "to_verify", confidence: "medium" },
        { id: "B3", status: "rejected", confidence: "low" },
        { id: "B4", status: "unknown", confidence: "unknown" },
        { id: "B5", status: "likely", confidence: "high" },
      ],
      logic: [],
    });

    expect(result.summary).toEqual({
      bottomEventCount: 5,
      toVerifyCount: 1,
      rejectedCount: 1,
      confirmedCount: 1,
      confidenceCounts: { high: 2, medium: 1, low: 1, unknown: 1 },
    });
  });

  // -----------------------------------------------------------------------
  // Missing / empty event arrays
  // -----------------------------------------------------------------------

  test("handles missing intermediate_events gracefully", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      // no intermediate_events key
    });

    expect(result.nodes.find((n) => n.kind === "intermediate")).toBeUndefined();
    expect(result.error).toBeNull();
  });

  test("handles missing bottom_events gracefully", () => {
    const result = okTree({
      top_event: "T",
      intermediate_events: [{ id: "IE-01", name: "Mid" }],
    });

    expect(result.nodes.find((n) => n.kind === "bottom")).toBeUndefined();
    expect(result.summary.bottomEventCount).toBe(0);
  });

  test("handles missing logic gracefully", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      // no logic key
    });

    // Should fall back to fallback edges
    expect(result.diagnostics).toContain(
      "No usable logic entries found; rendered a layered fallback graph.",
    );
  });

  test("handles non-array intermediate_events", () => {
    const result = okTree({
      top_event: "T",
      intermediate_events: "not-an-array",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [],
    });

    // valueToArray returns [] for non-array, so no intermediates
    expect(result.nodes.find((n) => n.kind === "intermediate")).toBeUndefined();
  });

  test("handles non-array bottom_events", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: 42,
      logic: [],
    });

    expect(result.nodes.find((n) => n.kind === "bottom")).toBeUndefined();
    expect(result.summary.bottomEventCount).toBe(0);
  });

  test("handles non-array logic", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: "not-an-array",
    });

    // valueToArray returns [] for non-array, triggers fallback
    expect(result.diagnostics).toContain(
      "No usable logic entries found; rendered a layered fallback graph.",
    );
  });

  // -----------------------------------------------------------------------
  // Edge id format
  // -----------------------------------------------------------------------

  test("edge id uses label or 'logic' when label is empty", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [{ source: "TOP", target: "BE-01", type: "AND" }],
    });

    expect(result.edges[0]!.id).toBe("TOP->BE-01:AND");
  });

  test("edge id uses 'logic' placeholder when type is missing", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [{ id: "BE-01", name: "Bot" }],
      logic: [{ source: "TOP", target: "BE-01" }],
    });

    expect(result.edges[0]!.id).toBe("TOP->BE-01:logic");
  });

  // -----------------------------------------------------------------------
  // Comprehensive integration tests
  // -----------------------------------------------------------------------

  test("handles a complete fault tree with all node kinds and logic types", () => {
    const result = okTree({
      top_event: "System failure",
      intermediate_events: [
        {
          id: "IE-1",
          name: "Hardware fault",
          description: "Physical component",
        },
        { id: "IE-2", name: "Software fault", description: "Code defect" },
      ],
      bottom_events: [
        {
          id: "BE-1",
          name: "Sensor failure",
          description: "Temp sensor malfunction",
          probability: "0.01",
          confidence: "high",
          status: "confirmed",
        },
        {
          id: "BE-2",
          name: "Null pointer exception",
          probability: "0.05",
          confidence: "medium",
          status: "to_verify",
        },
        {
          id: "BE-3",
          name: "Race condition",
          probability: "0.1",
          confidence: "low",
          status: "rejected",
        },
      ],
      logic: [
        { source: "TOP", target: "IE-1", type: "OR" },
        { source: "TOP", target: "IE-2", type: "OR" },
        { parent: "IE-1", children: ["BE-1"], type: "AND" },
        { parent: "IE-2", children: ["BE-2", "BE-3"], type: "OR" },
      ],
    });

    expect(result.error).toBeNull();
    expect(result.nodes).toHaveLength(6);
    // 2 source/target edges + 1 parent->child + 2 parent->children = 5
    expect(result.edges).toHaveLength(5);
    expect(result.summary).toEqual({
      bottomEventCount: 3,
      toVerifyCount: 1,
      rejectedCount: 1,
      confirmedCount: 1,
      confidenceCounts: { high: 1, medium: 1, low: 1, unknown: 0 },
    });
    expect(result.diagnostics).toHaveLength(0);
  });

  test("handles empty input object with all defaults", () => {
    const result = okTree({});

    expect(result.error).toBeNull();
    // Only TOP node should be created
    expect(result.nodes).toHaveLength(1);
    expect(result.nodes[0]!.kind).toBe("top");
    expect(result.nodes[0]!.label).toBe("Top event");
    expect(result.summary.bottomEventCount).toBe(0);
  });

  test("mixed logic entries with some valid and some invalid", () => {
    const result = okTree({
      top_event: "T",
      bottom_events: [
        { id: "BE-01", name: "Bot1" },
        { id: "BE-02", name: "Bot2" },
      ],
      logic: [
        { source: "TOP", target: "BE-01", type: "OR" }, // valid
        "invalid", // non-object
        { source: "TOP", target: "MISSING", type: "OR" }, // unknown target
        { random: "data" }, // unsupported
      ],
    });

    expect(result.edges).toHaveLength(1);
    expect(result.edges[0]!.source).toBe("TOP");
    expect(result.edges[0]!.target).toBe("BE-01");
    expect(result.diagnostics).toContain("Ignored non-object logic entry.");
    expect(result.diagnostics).toContain(
      "Ignored logic edge with unknown node: TOP->MISSING",
    );
    expect(result.diagnostics).toContain("Ignored unsupported logic entry.");
  });
});
