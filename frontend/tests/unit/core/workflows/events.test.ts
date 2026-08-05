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

  test("records started_at and finished_at from node lifecycle events", () => {
    const started = applyWorkflowEvent(
      { run_id: "run-1", workflow: "wf", status: "queued", error: null },
      {
        seq: 1,
        type: "node_started",
        payload: { node_id: "draft", started_at: "2026-08-04T07:00:00Z" },
      },
    );
    const completed = applyWorkflowEvent(started, {
      seq: 2,
      type: "node_completed",
      payload: {
        node_id: "draft",
        result: { ok: true },
        finished_at: "2026-08-04T07:00:10Z",
      },
    });

    expect(started.steps?.draft?.started_at).toBe("2026-08-04T07:00:00Z");
    expect(completed.steps?.draft).toMatchObject({
      status: "completed",
      started_at: "2026-08-04T07:00:00Z",
      finished_at: "2026-08-04T07:00:10Z",
    });
    expect(completed.steps?.draft?.output).toEqual({ ok: true });
  });

  test("collects unique edge_selected events", () => {
    const first = applyWorkflowEvent(
      { run_id: "run-1", workflow: "wf", status: "running", error: null },
      {
        seq: 5,
        type: "edge_selected",
        payload: { node_id: "route", from: "route", to: "yes" },
      },
    );
    const duplicate = applyWorkflowEvent(first, {
      seq: 6,
      type: "edge_selected",
      payload: { node_id: "route", from: "route", to: "yes" },
    });
    const other = applyWorkflowEvent(duplicate, {
      seq: 7,
      type: "edge_selected",
      payload: { node_id: "route", from: "route", to: "no" },
    });

    expect(first.selected_edges).toEqual([{ from: "route", to: "yes" }]);
    expect(duplicate.selected_edges).toEqual([{ from: "route", to: "yes" }]);
    expect(other.selected_edges).toEqual([
      { from: "route", to: "yes" },
      { from: "route", to: "no" },
    ]);
  });

  test("ignores run_started without disturbing status", () => {
    const result = applyWorkflowEvent(
      { run_id: "run-1", workflow: "wf", status: "queued", error: null },
      {
        seq: 0,
        type: "run_started",
        payload: { definition_version: 3 },
      },
    );
    expect(result.status).toBe("queued");
    expect(result.last_event_seq).toBe(0);
  });

  test("marks in-flight nodes cancelled on run_cancelled", () => {
    const started = applyWorkflowEvent(
      { run_id: "run-1", workflow: "wf", status: "running", error: null },
      { seq: 1, type: "node_started", payload: { node_id: "draft" } },
    );
    const cancelled = applyWorkflowEvent(started, {
      seq: 2,
      type: "run_cancelled",
      payload: {},
    });

    expect(cancelled.status).toBe("cancelled");
    expect(cancelled.steps?.draft?.status).toBe("cancelled");
    expect(cancelled.steps?.draft?.error).toBeNull();
  });

  test("keeps completed and failed steps untouched on run_cancelled", () => {
    const done = applyWorkflowEvent(
      { run_id: "run-1", workflow: "wf", status: "running", error: null },
      {
        seq: 1,
        type: "node_completed",
        payload: { node_id: "draft", result: "ok" },
      },
    );
    const cancelled = applyWorkflowEvent(done, {
      seq: 2,
      type: "run_cancelled",
      payload: {},
    });

    expect(cancelled.steps?.draft?.status).toBe("completed");
    expect(cancelled.steps?.draft?.output).toBe("ok");
  });

  test("marks only in-flight sibling nodes cancelled on run_failed", () => {
    const running = applyWorkflowEvent(
      { run_id: "run-1", workflow: "wf", status: "running", error: null },
      { seq: 1, type: "node_started", payload: { node_id: "sibling" } },
    );
    const failed = applyWorkflowEvent(running, {
      seq: 2,
      type: "node_failed",
      payload: { node_id: "draft", error: "adapter failed" },
    });
    const runFailed = applyWorkflowEvent(failed, {
      seq: 3,
      type: "run_failed",
      payload: { error: "workflow failed" },
    });

    expect(runFailed.status).toBe("failed");
    expect(runFailed.steps?.draft?.status).toBe("failed");
    expect(runFailed.steps?.sibling?.status).toBe("cancelled");
  });

  test("leaves steps untouched on run_completed", () => {
    const started = applyWorkflowEvent(
      { run_id: "run-1", workflow: "wf", status: "running", error: null },
      { seq: 1, type: "node_started", payload: { node_id: "draft" } },
    );
    const completed = applyWorkflowEvent(started, {
      seq: 2,
      type: "run_completed",
      payload: {},
    });

    expect(completed.status).toBe("completed");
    expect(completed.steps?.draft?.status).toBe("running");
  });
});
