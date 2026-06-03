import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createWorkflow,
  deleteWorkflow,
  getRunStatus,
  getWorkflow,
  listWorkflows,
  runWorkflow,
  submitReview,
  updateWorkflow,
} from "./api";
import type { ReviewData } from "./types";

export function useWorkflows() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["workflows"],
    queryFn: () => listWorkflows(),
  });
  return { workflows: data ?? [], isLoading, error, refetch };
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
      if (status === "running" || status === "pending") return 2000;
      return false;
    },
  });
  return { runStatus: data ?? null, isLoading, error, refetch };
}

export function useSubmitReview() {
  return useMutation({
    mutationFn: ({
      name,
      runId,
      data,
    }: {
      name: string;
      runId: string;
      data: ReviewData;
    }) => submitReview(name, runId, data),
  });
}
