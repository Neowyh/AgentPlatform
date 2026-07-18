import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createWorkflow,
  deleteWorkflow,
  getRunStatus,
  getWorkflow,
  listWorkflows,
  runWorkflow,
  submitWorkflowCommand,
  toggleWorkflowFavorite,
  updateWorkflow,
} from "./api";

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

export function useRunStatus(
  name: string | null | undefined,
  runId: string | null | undefined,
) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["workflows", name, "runs", runId],
    queryFn: () => getRunStatus(name!, runId!),
    enabled: !!name && !!runId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (
        status === "running" ||
        status === "pending" ||
        status === "waiting_human"
      )
        return 2000;
      return false;
    },
  });
  return { runStatus: data ?? null, isLoading, error, refetch };
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
