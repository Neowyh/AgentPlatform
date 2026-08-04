import { describe, expect, it } from "vitest";

import { validateYaml } from "@/core/workflows/validate";

describe("validateYaml", () => {
  it("rejects empty content", () => {
    expect(validateYaml("")).toContain("YAML content cannot be empty");
  });

  it("requires schema_version 2 and nodes", () => {
    const errors = validateYaml("name: workflow\nnodes: []");
    expect(errors).toContain('Required field "schema_version" must be 2');
    expect(errors).toContain(
      'Required field "nodes" must contain at least one node',
    );
  });

  it("accepts a minimal v2 definition", () => {
    expect(
      validateYaml(
        "schema_version: 2\nname: workflow\ninputs: {}\nstate: {}\nentrypoint: start\nnodes:\n  - id: start\n    type: interrupt\n    roles: [user]",
      ),
    ).toEqual([]);
  });

  it("rejects an empty v2 node list and missing workflow name", () => {
    const errors = validateYaml("schema_version: 2\nname:\nnodes: []");

    expect(errors).toContain('Required field "name" must have a value');
    expect(errors).toContain(
      'Required field "nodes" must contain at least one node',
    );
  });

  it("rejects action node with empty name", () => {
    const errors = validateYaml(
      'schema_version: 2\nname: workflow\ninputs: {}\nstate: {}\nentrypoint: start\nnodes:\n  - id: start\n    type: action\n    action:\n      kind: agent\n      name: ""\n      params:\n        prompt: ""\nedges: []',
    );
    expect(errors).toContain(
      'Action node has empty "name" — provide a valid agent or tool name',
    );
  });

  it("accepts action node with non-empty name", () => {
    expect(
      validateYaml(
        'schema_version: 2\nname: workflow\ninputs: {}\nstate: {}\nentrypoint: start\nnodes:\n  - id: start\n    type: action\n    action:\n      kind: agent\n      name: my-agent\n      params:\n        prompt: ""\nedges: []',
      ),
    ).toEqual([]);
  });

  it("reports malformed top-level YAML and unbalanced delimiters", () => {
    const errors = validateYaml(
      "schema_version: 2\nname: workflow\nbad-line\nnodes: [{",
    );
    expect(errors).toContain(
      'Line 3: expected a key-value pair (missing ":"): "bad-line"',
    );
    expect(errors).toContain("Unbalanced brackets: check for unclosed arrays");
    expect(errors).toContain(
      "Unbalanced braces: check for unclosed inline mappings",
    );
  });
});
