import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/core/workflows/api", () => ({
  createWorkflow: vi.fn(),
  deleteWorkflow: vi.fn(),
  getRunStatus: vi.fn(),
  getWorkflow: vi.fn(),
  listWorkflows: vi.fn(),
  runWorkflow: vi.fn(),
  submitWorkflowCommand: vi.fn(),
  toggleWorkflowFavorite: vi.fn(),
  updateWorkflow: vi.fn(),
  workflowEventsUrl: vi.fn(
    (name: string, runId: string, afterSeq: number) =>
      `/events/${name}/${runId}?after_seq=${afterSeq}`,
  ),
}));

type EventListener = (event: MessageEvent<string>) => void;

class MockEventSource {
  static instances: MockEventSource[] = [];
  readonly listeners = new Map<string, EventListener[]>();
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  readonly close = vi.fn();

  constructor(readonly url: string) {
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListener) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  emit(type: string, seq: number, payload: Record<string, unknown>) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener({
        type,
        lastEventId: String(seq),
        data: JSON.stringify(payload),
      } as MessageEvent<string>);
    }
  }
}

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return React.createElement(QueryClientProvider, { client }, children);
}

describe("useRunStatus", () => {
  afterEach(() => {
    MockEventSource.instances = [];
    vi.unstubAllGlobals();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  test("replays approval state after a reconnect and falls back after repeated stream failures", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const api = await import("@/core/workflows/api");
    vi.mocked(api.getRunStatus).mockResolvedValue({
      run_id: "run-1",
      workflow: "approval",
      status: "paused",
      error: null,
    });
    const { useRunStatus } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useRunStatus("approval", "run-1"), {
      wrapper,
    });

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    act(() => {
      MockEventSource.instances[0]?.emit("resumed", 1, {});
      MockEventSource.instances[0]?.emit("action_token", 2, {
        node_id: "finish",
        text: "approved",
      });
    });
    await waitFor(() =>
      expect(result.current.runStatus?.action_tokens?.finish).toBe("approved"),
    );
    expect(result.current.runStatus?.status).toBe("running");

    vi.useFakeTimers();
    for (let attempt = 0; attempt < 3; attempt += 1) {
      act(() => MockEventSource.instances.at(-1)?.onerror?.());
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000 * 2 ** attempt);
      });
    }

    expect(MockEventSource.instances[1]?.url).toContain("after_seq=2");
    expect(result.current.fallbackPolling).toBe(true);
  });

  test("replays from zero in sequence order and does not duplicate a reconnect event", async () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const api = await import("@/core/workflows/api");
    vi.mocked(api.getRunStatus).mockResolvedValue({
      run_id: "run-1",
      workflow: "approval",
      status: "running",
      error: null,
    });
    const { useRunStatus } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useRunStatus("approval", "run-1"), {
      wrapper,
    });

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    expect(MockEventSource.instances[0]?.url).toContain("after_seq=0");
    act(() => {
      MockEventSource.instances[0]?.emit("node_started", 1, {
        node_id: "draft",
      });
      MockEventSource.instances[0]?.emit("action_token", 2, {
        node_id: "draft",
        text: "one",
      });
      MockEventSource.instances[0]?.emit("action_token", 2, {
        node_id: "draft",
        text: "one",
      });
    });

    await waitFor(() =>
      expect(
        result.current.runStatus?.events?.map((event) => event.seq),
      ).toEqual([1, 2]),
    );
    expect(result.current.runStatus?.action_tokens?.draft).toBe("one");
  });
});
