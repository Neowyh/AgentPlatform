import { describe, expect, it } from "vitest";

import {
  applyTaskInputInsertion,
  getResolvedInputMode,
  hasTaskInput,
  prepareTaskInputInsertion,
  prepareTaskSubmission,
} from "@/core/threads/task-input";

const context = {
  model_name: "gpt-4o",
  mode: "flash" as const,
};

describe("task input", () => {
  it("removes a slash Skill prefix and adds the Skill to context", () => {
    expect(
      prepareTaskSubmission(
        { text: "/research summarize this", files: [] },
        context,
      ),
    ).toEqual({
      message: { text: "summarize this", files: [] },
      context: { ...context, skill_name: "research" },
      skillName: "research",
    });
  });

  it("keeps normal text and context unchanged", () => {
    expect(
      prepareTaskSubmission({ text: "hello", files: [] }, context),
    ).toEqual({
      message: { text: "hello", files: [] },
      context,
      skillName: null,
    });
  });

  it("accepts files when text is empty", () => {
    expect(hasTaskInput({ text: "  ", files: [{}] })).toBe(true);
    expect(hasTaskInput({ text: "  ", files: [] })).toBe(false);
  });

  it("resolves unsupported modes to flash", () => {
    expect(getResolvedInputMode("pro", false)).toBe("flash");
    expect(getResolvedInputMode(undefined, true)).toBe("pro");
  });

  it("requires a choice before a template replaces existing text", () => {
    expect(prepareTaskInputInsertion("my task", "template")).toEqual({
      kind: "conflict",
      current: "my task",
      incoming: "template",
    });
    expect(applyTaskInputInsertion("my task", "template", "replace")).toBe(
      "template",
    );
    expect(applyTaskInputInsertion("my task", "template", "append")).toBe(
      "my task\ntemplate",
    );
  });

  it("inserts a template directly when the input is empty", () => {
    expect(prepareTaskInputInsertion("  ", "template")).toEqual({
      kind: "insert",
      text: "template",
    });
  });
});
