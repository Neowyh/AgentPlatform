import { renderHook, act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  SubtasksProvider,
  useSubtask,
  useSubtaskContext,
  useUpdateSubtask,
} from "@/core/tasks/context";
import type { Subtask } from "@/core/tasks/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeTask(overrides: Partial<Subtask> = {}): Subtask {
  return {
    id: "task-1",
    status: "in_progress",
    subagent_type: "general-purpose",
    description: "Do something",
    prompt: "Please do something",
    ...overrides,
  };
}

function wrapper({ children }: { children: React.ReactNode }) {
  return <SubtasksProvider>{children}</SubtasksProvider>;
}

// ---------------------------------------------------------------------------
// SubtasksProvider
// ---------------------------------------------------------------------------

describe("SubtasksProvider", () => {
  it("renders children", () => {
    render(
      <SubtasksProvider>
        <span>child content</span>
      </SubtasksProvider>,
    );
    expect(screen.getByText("child content")).toBeInTheDocument();
  });

  it("provides an empty tasks object by default", () => {
    const { result } = renderHook(() => useSubtaskContext(), { wrapper });
    expect(result.current.tasks).toEqual({});
  });

  it("provides a setTasks function", () => {
    const { result } = renderHook(() => useSubtaskContext(), { wrapper });
    expect(typeof result.current.setTasks).toBe("function");
  });
});

// ---------------------------------------------------------------------------
// SubtaskContext default value (accessed via useContext without a Provider)
// ---------------------------------------------------------------------------

describe("SubtaskContext default value", () => {
  it("provides an empty tasks object as the default value", () => {
    // When no Provider wraps the consumer, useContext returns the default
    // value passed to createContext. We can observe this by rendering the
    // hook without a wrapper.
    const { result } = renderHook(() => useSubtaskContext());
    expect(result.current.tasks).toEqual({});
  });

  it("provides a callable no-op setTasks as the default value", () => {
    const { result } = renderHook(() => useSubtaskContext());
    // The default setTasks is a no-op; calling it should not throw.
    expect(() => result.current.setTasks({})).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// useSubtaskContext
// ---------------------------------------------------------------------------

describe("useSubtaskContext", () => {
  it("returns the context default value when no Provider is present", () => {
    // Because createContext is called with a default value, useContext never
    // returns undefined — the guard (`if (context === undefined)`) is dead
    // code. This test documents that behaviour: the hook returns the default
    // value silently instead of throwing.
    const { result } = renderHook(() => useSubtaskContext());
    expect(result.current.tasks).toEqual({});
    expect(typeof result.current.setTasks).toBe("function");
  });

  it("returns context value when used inside SubtasksProvider", () => {
    const { result } = renderHook(() => useSubtaskContext(), { wrapper });
    expect(result.current).toHaveProperty("tasks");
    expect(result.current).toHaveProperty("setTasks");
  });

  it("reflects tasks set via setTasks", () => {
    const task = makeTask();
    const { result } = renderHook(() => useSubtaskContext(), { wrapper });

    act(() => {
      result.current.setTasks({ [task.id]: task });
    });

    expect(result.current.tasks).toEqual({ [task.id]: task });
  });

  it("replaces the entire tasks map on setTasks", () => {
    const task1 = makeTask({ id: "t1" });
    const task2 = makeTask({ id: "t2" });
    const { result } = renderHook(() => useSubtaskContext(), { wrapper });

    act(() => {
      result.current.setTasks({ t1: task1 });
    });
    expect(Object.keys(result.current.tasks)).toEqual(["t1"]);

    act(() => {
      result.current.setTasks({ t2: task2 });
    });
    expect(Object.keys(result.current.tasks)).toEqual(["t2"]);
  });
});

// ---------------------------------------------------------------------------
// useSubtask
// ---------------------------------------------------------------------------

describe("useSubtask", () => {
  it("returns undefined for a non-existent task id", () => {
    const { result } = renderHook(() => useSubtask("missing"), { wrapper });
    expect(result.current).toBeUndefined();
  });

  it("returns the task matching the given id", () => {
    const task = makeTask({ id: "find-me" });
    const { result } = renderHook(
      () => ({
        ctx: useSubtaskContext(),
        subtask: useSubtask("find-me"),
      }),
      { wrapper },
    );

    act(() => {
      result.current.ctx.setTasks({ "find-me": task });
    });

    // After re-render the hook should pick up the new task.
    expect(result.current.subtask).toEqual(task);
  });

  it("returns undefined after tasks are cleared", () => {
    const task = makeTask({ id: "clear-me" });
    const { result } = renderHook(
      () => ({
        ctx: useSubtaskContext(),
        subtask: useSubtask("clear-me"),
      }),
      { wrapper },
    );

    act(() => {
      result.current.ctx.setTasks({ "clear-me": task });
    });
    expect(result.current.subtask).toEqual(task);

    act(() => {
      result.current.ctx.setTasks({});
    });
    expect(result.current.subtask).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// useUpdateSubtask
// ---------------------------------------------------------------------------

describe("useUpdateSubtask", () => {
  it("creates a new task entry when none exists", () => {
    const { result } = renderHook(
      () => ({
        ctx: useSubtaskContext(),
        update: useUpdateSubtask(),
      }),
      { wrapper },
    );

    act(() => {
      result.current.update({
        id: "new-task",
        status: "in_progress",
        subagent_type: "general-purpose",
        description: "brand new",
        prompt: "go",
        latestMessage: { content: "started" } as any,
      });
    });

    expect(result.current.ctx.tasks["new-task"]).toBeDefined();
    expect(result.current.ctx.tasks["new-task"]!.id).toBe("new-task");
    expect(result.current.ctx.tasks["new-task"]!.status).toBe("in_progress");
    expect(result.current.ctx.tasks["new-task"]!.description).toBe("brand new");
  });

  it("merges partial updates into an existing task", () => {
    const existing = makeTask({
      id: "merge-me",
      description: "original",
      status: "in_progress",
    });

    const { result } = renderHook(
      () => ({
        ctx: useSubtaskContext(),
        update: useUpdateSubtask(),
      }),
      { wrapper },
    );

    // Seed the task.
    act(() => {
      result.current.ctx.setTasks({ "merge-me": existing });
    });

    // Update with a partial (latestMessage triggers re-render).
    act(() => {
      result.current.update({
        id: "merge-me",
        status: "completed",
        result: "done",
        latestMessage: { content: "finished" } as any,
      });
    });

    const updated = result.current.ctx.tasks["merge-me"];
    expect(updated!.status).toBe("completed");
    expect(updated!.result).toBe("done");
    // Fields not provided in the partial should survive from the original.
    expect(updated!.description).toBe("original");
    expect(updated!.prompt).toBe("Please do something");
  });

  it("triggers a state update (re-render) when latestMessage is present", () => {
    const existing = makeTask({ id: "rerender" });
    const { result } = renderHook(
      () => ({
        ctx: useSubtaskContext(),
        update: useUpdateSubtask(),
      }),
      { wrapper },
    );

    act(() => {
      result.current.ctx.setTasks({ rerender: existing });
    });

    const tasksBefore = result.current.ctx.tasks;

    act(() => {
      result.current.update({
        id: "rerender",
        description: "updated",
        latestMessage: { content: "msg" } as any,
      });
    });

    // Reference equality should break because setTasks creates a new object.
    expect(result.current.ctx.tasks).not.toBe(tasksBefore);
    expect(result.current.ctx.tasks.rerender!.description).toBe("updated");
  });

  it("mutates the task in-place but does NOT trigger re-render when latestMessage is absent", () => {
    const existing = makeTask({ id: "no-rerender" });
    const { result } = renderHook(
      () => ({
        ctx: useSubtaskContext(),
        update: useUpdateSubtask(),
      }),
      { wrapper },
    );

    act(() => {
      result.current.ctx.setTasks({ "no-rerender": existing });
    });

    const tasksBefore = result.current.ctx.tasks;

    act(() => {
      result.current.update({
        id: "no-rerender",
        description: "mutated but no rerender",
        // no latestMessage
      });
    });

    // The tasks reference should be the same object (no setTasks call).
    expect(result.current.ctx.tasks).toBe(tasksBefore);
    // But the task itself was mutated in place.
    expect(result.current.ctx.tasks["no-rerender"]!.description).toBe(
      "mutated but no rerender",
    );
  });

  it("preserves existing latestMessage when updating other fields", () => {
    const existing = makeTask({
      id: "preserve-msg",
      latestMessage: { content: "original-msg" } as any,
    });

    const { result } = renderHook(
      () => ({
        ctx: useSubtaskContext(),
        update: useUpdateSubtask(),
      }),
      { wrapper },
    );

    act(() => {
      result.current.ctx.setTasks({ "preserve-msg": existing });
    });

    act(() => {
      result.current.update({
        id: "preserve-msg",
        status: "completed",
        // no latestMessage in the partial, so the existing one is kept
      });
    });

    // The original latestMessage should survive because the partial doesn't
    // include one, and the spread keeps the old value.
    expect(result.current.ctx.tasks["preserve-msg"]!.latestMessage).toEqual({
      content: "original-msg",
    });
    expect(result.current.ctx.tasks["preserve-msg"]!.status).toBe("completed");
  });

  it("overwrites latestMessage when a new one is provided", () => {
    const existing = makeTask({
      id: "overwrite-msg",
      latestMessage: { content: "old" } as any,
    });

    const { result } = renderHook(
      () => ({
        ctx: useSubtaskContext(),
        update: useUpdateSubtask(),
      }),
      { wrapper },
    );

    act(() => {
      result.current.ctx.setTasks({ "overwrite-msg": existing });
    });

    act(() => {
      result.current.update({
        id: "overwrite-msg",
        latestMessage: { content: "new" } as any,
      });
    });

    expect(result.current.ctx.tasks["overwrite-msg"]!.latestMessage).toEqual({
      content: "new",
    });
  });

  it("handles updating multiple different tasks", () => {
    const { result } = renderHook(
      () => ({
        ctx: useSubtaskContext(),
        update: useUpdateSubtask(),
      }),
      { wrapper },
    );

    act(() => {
      result.current.update({
        id: "a",
        status: "in_progress",
        subagent_type: "general-purpose",
        description: "task A",
        prompt: "a",
        latestMessage: { content: "a-start" } as any,
      });
    });

    act(() => {
      result.current.update({
        id: "b",
        status: "in_progress",
        subagent_type: "general-purpose",
        description: "task B",
        prompt: "b",
        latestMessage: { content: "b-start" } as any,
      });
    });

    expect(result.current.ctx.tasks.a!.description).toBe("task A");
    expect(result.current.ctx.tasks.b!.description).toBe("task B");
    expect(Object.keys(result.current.ctx.tasks)).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// Integration: multiple hooks sharing the same provider
// ---------------------------------------------------------------------------

describe("integration: shared provider state", () => {
  it("useSubtask reflects updates made via useUpdateSubtask", () => {
    const { result } = renderHook(
      () => ({
        update: useUpdateSubtask(),
        task: useSubtask("shared"),
      }),
      { wrapper },
    );

    act(() => {
      result.current.update({
        id: "shared",
        status: "in_progress",
        subagent_type: "general-purpose",
        description: "shared task",
        prompt: "go",
        latestMessage: { content: "hello" } as any,
      });
    });

    expect(result.current.task).toBeDefined();
    expect(result.current.task!.description).toBe("shared task");
    expect(result.current.task!.status).toBe("in_progress");
  });

  it("useSubtask returns updated status after useUpdateSubtask marks it completed", () => {
    const { result } = renderHook(
      () => ({
        update: useUpdateSubtask(),
        task: useSubtask("lifecycle"),
      }),
      { wrapper },
    );

    // Create
    act(() => {
      result.current.update({
        id: "lifecycle",
        status: "in_progress",
        subagent_type: "general-purpose",
        description: "lifecycle test",
        prompt: "run",
        latestMessage: { content: "started" } as any,
      });
    });
    expect(result.current.task!.status).toBe("in_progress");

    // Complete
    act(() => {
      result.current.update({
        id: "lifecycle",
        status: "completed",
        result: "all good",
        latestMessage: { content: "finished" } as any,
      });
    });
    expect(result.current.task!.status).toBe("completed");
    expect(result.current.task!.result).toBe("all good");
  });

  it("useSubtask returns updated status after useUpdateSubtask marks it failed", () => {
    const { result } = renderHook(
      () => ({
        update: useUpdateSubtask(),
        task: useSubtask("fail-lifecycle"),
      }),
      { wrapper },
    );

    act(() => {
      result.current.update({
        id: "fail-lifecycle",
        status: "in_progress",
        subagent_type: "general-purpose",
        description: "will fail",
        prompt: "run",
        latestMessage: { content: "started" } as any,
      });
    });

    act(() => {
      result.current.update({
        id: "fail-lifecycle",
        status: "failed",
        error: "something broke",
        latestMessage: { content: "error" } as any,
      });
    });

    expect(result.current.task!.status).toBe("failed");
    expect(result.current.task!.error).toBe("something broke");
  });
});
