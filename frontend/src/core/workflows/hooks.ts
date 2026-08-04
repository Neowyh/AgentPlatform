import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import {
  createWorkflow,
  deleteWorkflow,
  getRunArtifactContent,
  getRunStatus,
  getWorkflow,
  listRunArtifacts,
  listWorkflowRuns,
  listWorkflows,
  runWorkflow,
  submitWorkflowCommand,
  toggleWorkflowFavorite,
  updateWorkflow,
  workflowEventsUrl,
} from "./api";
import { applyWorkflowEvent } from "./events";
import type { RunArtifact, RunStatus, WorkflowEvent } from "./types";

const workflowEventTypes = new Set<WorkflowEvent["type"]>([
  "node_started",
  "action_token",
  "action_progress",
  "node_completed",
  "node_failed",
  "interrupted",
  "resumed",
  "run_completed",
  "run_failed",
  "run_cancelled",
]);

function parseWorkflowEvent(
  message: MessageEvent<string>,
): WorkflowEvent | null {
  const seq = Number(message.lastEventId);
  if (
    !Number.isInteger(seq) ||
    !workflowEventTypes.has(message.type as WorkflowEvent["type"])
  )
    return null;
  try {
    const payload: unknown = JSON.parse(message.data);
    if (!payload || typeof payload !== "object" || Array.isArray(payload))
      return null;
    return {
      seq,
      type: message.type as WorkflowEvent["type"],
      payload: payload as Record<string, unknown>,
    };
  } catch {
    return null;
  }
}

export function useWorkflows() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["workflows"],
    queryFn: () => listWorkflows(),
  });
  return { workflows: data?.workflows ?? [], isLoading, error, refetch };
}

export function useWorkflow(name: string | null | undefined) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["workflows", name],
    queryFn: () => getWorkflow(name!),
    enabled: !!name,
  });
  return { workflow: data ?? null, isLoading, error };
}

export function useCreateWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => createWorkflow(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["workflows"] });
    },
  });
}

export function useUpdateWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      name,
      data,
    }: {
      name: string;
      data: Record<string, unknown>;
    }) => updateWorkflow(name, data),
    onSuccess: (_data, { name }) => {
      void queryClient.invalidateQueries({ queryKey: ["workflows"] });
      void queryClient.invalidateQueries({ queryKey: ["workflows", name] });
    },
  });
}

export function useDeleteWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => deleteWorkflow(name),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["workflows"] });
    },
  });
}

export function useToggleWorkflowFavorite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => toggleWorkflowFavorite(name),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["workflows"] });
    },
  });
}

export function useRunWorkflow() {
  return useMutation({
    mutationFn: ({
      name,
      inputs,
    }: {
      name: string;
      inputs: Record<string, unknown>;
    }) => runWorkflow(name, inputs),
  });
}

export function useWorkflowRuns(name: string | null | undefined) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["workflows", name, "runs"],
    queryFn: () => listWorkflowRuns(name!),
    enabled: !!name,
  });
  return {
    runs: data?.runs ?? [],
    total: data?.total ?? 0,
    isLoading,
    error,
    refetch,
  };
}

export function useRunArtifacts(
  name: string | null | undefined,
  runId: string | null | undefined,
) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["workflows", name, "runs", runId, "artifacts"],
    queryFn: () => listRunArtifacts(name!, runId!),
    enabled: !!name && !!runId,
  });
  return {
    artifacts: data?.artifacts ?? [],
    isLoading,
    error,
    refetch,
  };
}

export function useRunArtifactContent(
  name: string | null | undefined,
  runId: string | null | undefined,
  path: string | null,
) {
  return useQuery({
    queryKey: ["workflows", name, "runs", runId, "artifacts", path],
    queryFn: () => getRunArtifactContent(name!, runId!, path!),
    enabled: !!name && !!runId && !!path,
  });
}

export function useRunStatus(
  name: string | null | undefined,
  runId: string | null | undefined,
) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["workflows", name, "runs", runId],
    queryFn: () => getRunStatus(name!, runId!),
    enabled: !!name && !!runId,
    refetchInterval: false,
  });
  const [streamedStatus, setStreamedStatus] = useState<RunStatus | null>(null);
  const [fallbackPolling, setFallbackPolling] = useState(false);
  const lastEventSeq = useRef(0);

  useEffect(() => {
    if (!data) return;
    setStreamedStatus((current) => {
      if (current?.run_id === data.run_id) return current;
      // A snapshot does not contain all events or node state. Replay from zero
      // once so a direct URL load can rebuild the complete run detail.
      lastEventSeq.current = 0;
      return { ...data, events: [] };
    });
  }, [data]);

  useEffect(() => {
    if (!name || !runId || !data) return;
    let source: EventSource | undefined;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let pollTimer: ReturnType<typeof setInterval> | undefined;
    let attempts = 0;
    let closed = false;

    const startPolling = () => {
      if (pollTimer) return;
      setFallbackPolling(true);
      pollTimer = setInterval(() => void refetch(), 2000);
    };
    const connect = () => {
      source = new EventSource(
        workflowEventsUrl(name, runId, lastEventSeq.current),
        { withCredentials: true },
      );
      source.onopen = () => {
        attempts = 0;
        setFallbackPolling(false);
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = undefined;
      };
      const onEvent = (message: MessageEvent<string>) => {
        const event = parseWorkflowEvent(message);
        if (!event || event.seq <= lastEventSeq.current) return;
        lastEventSeq.current = event.seq;
        setStreamedStatus((current) => {
          const base = current ?? { ...data, events: [] };
          return {
            ...applyWorkflowEvent(base, event),
            events: [...(base.events ?? []), event],
          };
        });
      };
      for (const type of [
        "node_started",
        "action_token",
        "action_progress",
        "node_completed",
        "node_failed",
        "interrupted",
        "resumed",
        "run_completed",
        "run_failed",
        "run_cancelled",
      ] as const)
        source.addEventListener(type, onEvent);
      source.onerror = () => {
        source?.close();
        if (closed) return;
        attempts += 1;
        if (attempts >= 3) startPolling();
        retryTimer = setTimeout(
          connect,
          Math.min(1000 * 2 ** (attempts - 1), 8000),
        );
      };
    };
    connect();
    return () => {
      closed = true;
      source?.close();
      if (retryTimer) clearTimeout(retryTimer);
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [data, name, refetch, runId]);

  return {
    runStatus: streamedStatus ?? data ?? null,
    isLoading,
    error,
    refetch,
    fallbackPolling,
  };
}

export function useSubmitWorkflowCommand() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      name,
      runId,
      command,
    }: {
      name: string;
      runId: string;
      command: {
        command_id: string;
        type: "resume" | "cancel";
        payload?: Record<string, unknown>;
      };
    }) => submitWorkflowCommand(name, runId, command),
    onSuccess: (_data, { name, runId }) => {
      // Invalidate the snapshot after a durable command is accepted.
      void queryClient.invalidateQueries({
        queryKey: ["workflows", name, "runs", runId],
      });
    },
  });
}
