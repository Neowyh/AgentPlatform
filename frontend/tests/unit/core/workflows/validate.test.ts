import { describe, expect, it } from "vitest";

import { validateYaml } from "@/core/workflows/validate";

describe("validateYaml", () => {
  it("returns error for empty content", () => {
    const errors = validateYaml("");
    expect(errors).toContain("YAML content cannot be empty");
  });

  it("returns error for whitespace-only content", () => {
    const errors = validateYaml("   \n\t  ");
    expect(errors).toContain("YAML content cannot be empty");
  });

  it("returns error when name field is missing", () => {
    const errors = validateYaml("steps:\n  - id: step1");
    expect(errors).toContain('Missing required field: "name"');
  });

  it("returns error when steps field is missing", () => {
    const errors = validateYaml("name: my-workflow");
    expect(errors).toContain('Missing required field: "steps"');
  });

  it("returns both errors when both fields are missing", () => {
    const errors = validateYaml("description: hello");
    expect(errors).toHaveLength(2);
    expect(errors).toContain('Missing required field: "name"');
    expect(errors).toContain('Missing required field: "steps"');
  });

  it("returns no errors for valid YAML with name and steps", () => {
    const errors = validateYaml(
      "name: my-workflow\nsteps:\n  - id: step1\n    type: agent",
    );
    expect(errors).toHaveLength(0);
  });

  it("returns no errors for full workflow YAML", () => {
    const yaml = `name: test-workflow
description: "A test"
version: "1.0"
inputs:
  query:
    type: string
steps:
  - id: step1
    type: agent
    agent: test-agent
    prompt: Hello`;
    const errors = validateYaml(yaml);
    expect(errors).toHaveLength(0);
  });

  it("reports top-level lines without key-value syntax", () => {
    const errors = validateYaml("name: wf\nnot-a-pair\nsteps:\n  - id: s1");

    expect(errors).toContain(
      'Line 2: expected a key-value pair (missing ":"): "not-a-pair"',
    );
  });

  it("reports empty name and explicit empty steps list", () => {
    const errors = validateYaml("name:\nsteps: []");

    expect(errors).toContain('Required field "name" must have a value');
    expect(errors).toContain(
      'Required field "steps" must contain at least one step',
    );
  });

  it("reports block steps without items", () => {
    const errors = validateYaml("name: wf\nsteps:\ndescription: done");

    expect(errors).toContain(
      'Required field "steps" must contain at least one step',
    );
  });

  it("accepts quoted names and inline non-empty steps", () => {
    const errors = validateYaml('name: "quoted-wf"\nsteps: [first]');

    expect(errors).toHaveLength(0);
  });

  it("reports unbalanced brackets and braces", () => {
    const errors = validateYaml("name: wf\nsteps: [first\nconfig: {a: 1");

    expect(errors).toContain("Unbalanced brackets: check for unclosed arrays");
    expect(errors).toContain(
      "Unbalanced braces: check for unclosed inline mappings",
    );
  });
});
