import { describe, expect, test } from "vitest";

import { applyWorkflowEvent } from "@/core/workflows/events";

describe("applyWorkflowEvent", () => {
  test("advances terminal status and keeps streamed tokens", () => {
    const started = applyWorkflowEvent(
      { run_id: "run-1", workflow: "wf", status: "running", error: null },
      {
        seq: 3,
        type: "action_token",
        payload: { node_id: "draft", text: "hello" },
      },
    );
    const completed = applyWorkflowEvent(started, {
      seq: 4,
      type: "run_completed",
      payload: {},
    });

    expect(started.action_tokens?.draft).toBe("hello");
    expect(completed.status).toBe("completed");
    expect(completed.last_event_seq).toBe(4);
  });

  test("updates node state and ignores malformed streaming payload values", () => {
    const started = applyWorkflowEvent(
      { run_id: "run-1", workflow: "wf", status: "queued", error: null },
      { seq: 1, type: "node_started", payload: { node_id: "draft" } },
    );
    const failed = applyWorkflowEvent(started, {
      seq: 2,
      type: "node_failed",
      payload: { node_id: "draft", error: "adapter failed" },
    });
    const malformed = applyWorkflowEvent(failed, {
      seq: 3,
      type: "action_token",
      payload: { node_id: "draft", text: { unsafe: true } },
    });

    expect(started.steps?.draft?.status).toBe("running");
    expect(failed.steps?.draft).toMatchObject({
      status: "failed",
      error: "adapter failed",
    });
    expect(malformed.action_tokens?.draft).toBe("");
  });
});
