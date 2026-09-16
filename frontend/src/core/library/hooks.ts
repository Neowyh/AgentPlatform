import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createKnowledgeBase,
  createKnowledgeEvalCase,
  createKnowledgeRevision,
  deleteKnowledgeEvalCase,
  getEvalCaseRevisionApplicability,
  getKnowledgeEvalCase,
  getKnowledgeRevision,
  getRetrievalTest,
  listKnowledgeBases,
  listKnowledgeDocuments,
  listKnowledgeEvalCases,
  listKnowledgeRevisions,
  listRetrievalTests,
  listKnowledgeEvaluations,
  getKnowledgeEvaluation,
  retryKnowledgeEvaluation,
  startKnowledgeEvaluation,
  startKnowledgeEvaluationComparison,
  getKnowledgeEvaluationComparison,
  getKnowledgeEvaluationPolicy,
  publishKnowledgeRevision,
  prepareKnowledgeRevision,
  runRetrievalTest,
  updateKnowledgeEvalCase,
  updateKnowledgeEvaluationPolicy,
  uploadKnowledgeDocument,
  retryKnowledgeDocument,
  rebuildKnowledgeDocumentIndex,
  deleteKnowledgeDocument,
  editKnowledgeDocument,
} from "./api";
import type { RunRetrievalTestRequest } from "./api";
import type { UpdateKnowledgeEvaluationPolicyRequest } from "./api";
import type {
  CreateKnowledgeBaseRequest,
  CreateKnowledgeEvalCaseRequest,
  KnowledgeRevision,
  UpdateKnowledgeEvalCaseRequest,
} from "./api";

export function useKnowledgeBases() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["knowledge-bases"],
    queryFn: listKnowledgeBases,
    refetchInterval: (current) =>
      current.state.data?.some(
        (base) => base.knowledge_initialization_status === "initializing",
      )
        ? 2000
        : false,
  });
  return { knowledgeBases: data ?? [], isLoading, error, refetch };
}

export function useCreateKnowledgeBase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: CreateKnowledgeBaseRequest) =>
      createKnowledgeBase(request),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] }),
  });
}

export function useDocuments(resourceId: string | undefined) {
  const query = useQuery({
    queryKey: ["knowledge-documents", resourceId],
    queryFn: () => listKnowledgeDocuments(resourceId!),
    enabled: Boolean(resourceId),
    refetchInterval: (current) =>
      current.state.data?.some((document) =>
        ["uploaded", "processing", "deleting"].includes(document.status),
      )
        ? 2000
        : false,
  });
  return { documents: query.data ?? [], ...query };
}

export function useUploadKnowledgeDocument(resourceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadKnowledgeDocument(resourceId, file),
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-documents", resourceId],
      }),
  });
}

function useDocumentAction(
  action: (resourceId: string, documentId: string) => Promise<unknown>,
  resourceId: string,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => action(resourceId, documentId),
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-documents", resourceId],
      }),
  });
}

export const useRetryKnowledgeDocument = (resourceId: string) =>
  useDocumentAction(retryKnowledgeDocument, resourceId);

export const useRebuildKnowledgeDocumentIndex = (resourceId: string) =>
  useDocumentAction(rebuildKnowledgeDocumentIndex, resourceId);

export const useDeleteKnowledgeDocument = (resourceId: string) =>
  useDocumentAction(deleteKnowledgeDocument, resourceId);

export function useKnowledgeRevisions(resourceId: string | undefined) {
  const query = useQuery({
    queryKey: ["knowledge-revisions", resourceId],
    queryFn: () => listKnowledgeRevisions(resourceId!),
    enabled: Boolean(resourceId),
    refetchInterval: (query) => {
      const revisions = query.state.data;
      return revisions?.some((revision) => revision.status === "indexing")
        ? 2000
        : false;
    },
  });
  return { revisions: query.data ?? [], ...query };
}

export function useKnowledgeEvaluationPolicy(resourceId: string | undefined) {
  return useQuery({
    queryKey: ["knowledge-evaluation-policy", resourceId],
    queryFn: () => getKnowledgeEvaluationPolicy(resourceId!),
    enabled: Boolean(resourceId),
  });
}

export function useUpdateKnowledgeEvaluationPolicy(resourceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: UpdateKnowledgeEvaluationPolicyRequest) =>
      updateKnowledgeEvaluationPolicy(resourceId, request),
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-evaluation-policy", resourceId],
      }),
  });
}

export function useKnowledgeRevision(
  resourceId: string | undefined,
  revisionId: string | undefined,
) {
  const query = useQuery({
    queryKey: ["knowledge-revisions", resourceId, revisionId],
    queryFn: () => getKnowledgeRevision(resourceId!, revisionId!),
    enabled: Boolean(resourceId && revisionId),
  });
  return query;
}

export function usePublishedKnowledgeRevisions(knowledgeBaseIds: string[]) {
  const query = useQuery({
    queryKey: ["knowledge-revisions-published", knowledgeBaseIds],
    queryFn: async () => {
      const entries = await Promise.all(
        knowledgeBaseIds.map(async (id) => {
          const revisions = await listKnowledgeRevisions(id);
          return [
            id,
            revisions.filter((revision) => revision.status === "published"),
          ] as const;
        }),
      );
      return Object.fromEntries(entries);
    },
    enabled: knowledgeBaseIds.length > 0,
  });
  return {
    ...query,
    publishedRevisions: (query.data ?? {}) as Record<
      string,
      KnowledgeRevision[]
    >,
    isError: query.isError,
  };
}

export function useCreateKnowledgeRevision(resourceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => createKnowledgeRevision(resourceId),
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-revisions", resourceId],
      }),
  });
}

export function usePublishKnowledgeRevision(resourceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (revisionId: string) =>
      publishKnowledgeRevision(resourceId, revisionId),
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-revisions", resourceId],
      }),
  });
}

export function usePrepareKnowledgeRevision(resourceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (revisionId: string) =>
      prepareKnowledgeRevision(resourceId, revisionId),
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-revisions", resourceId],
      }),
  });
}

export function useEditKnowledgeDocument(resourceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      documentId,
      update,
    }: {
      documentId: string;
      update: { title?: string; metadata?: Record<string, unknown> };
    }) => editKnowledgeDocument(resourceId, documentId, update),
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-documents", resourceId],
      }),
  });
}

export function useKnowledgeEvalCases(resourceId: string | undefined) {
  const query = useQuery({
    queryKey: ["knowledge-eval-cases", resourceId],
    queryFn: () => listKnowledgeEvalCases(resourceId!),
    enabled: Boolean(resourceId),
  });
  return { evalCases: query.data ?? [], ...query };
}

export function useKnowledgeEvalCase(
  resourceId: string | undefined,
  caseId: string | undefined,
) {
  const query = useQuery({
    queryKey: ["knowledge-eval-cases", resourceId, caseId],
    queryFn: () => getKnowledgeEvalCase(resourceId!, caseId!),
    enabled: Boolean(resourceId && caseId),
  });
  return query;
}

function useInvalidateEvalCases(resourceId: string) {
  const queryClient = useQueryClient();
  return () =>
    void queryClient.invalidateQueries({
      queryKey: ["knowledge-eval-cases", resourceId],
    });
}

export function useCreateKnowledgeEvalCase(resourceId: string) {
  const invalidate = useInvalidateEvalCases(resourceId);
  return useMutation({
    mutationFn: (request: CreateKnowledgeEvalCaseRequest) =>
      createKnowledgeEvalCase(resourceId, request),
    onSuccess: invalidate,
  });
}

export function useUpdateKnowledgeEvalCase(resourceId: string) {
  const invalidate = useInvalidateEvalCases(resourceId);
  return useMutation({
    mutationFn: ({
      caseId,
      update,
    }: {
      caseId: string;
      update: UpdateKnowledgeEvalCaseRequest;
    }) => updateKnowledgeEvalCase(resourceId, caseId, update),
    onSuccess: invalidate,
  });
}

export function useDeleteKnowledgeEvalCase(resourceId: string) {
  const invalidate = useInvalidateEvalCases(resourceId);
  return useMutation({
    mutationFn: (caseId: string) => deleteKnowledgeEvalCase(resourceId, caseId),
    onSuccess: invalidate,
  });
}

export function useEvalCaseRevisionApplicability(
  resourceId: string | undefined,
  revisionId: string | undefined,
) {
  const query = useQuery({
    queryKey: ["knowledge-eval-cases", resourceId, "applicability", revisionId],
    queryFn: () => getEvalCaseRevisionApplicability(resourceId!, revisionId!),
    enabled: Boolean(resourceId && revisionId),
  });
  return query;
}

export function useRetrievalTests(resourceId: string | undefined) {
  const query = useQuery({
    queryKey: ["knowledge-retrieval-tests", resourceId],
    queryFn: () => listRetrievalTests(resourceId!),
    enabled: Boolean(resourceId),
  });
  return { tests: query.data ?? [], ...query };
}

export function useRetrievalTest(
  resourceId: string | undefined,
  testId: string | undefined,
) {
  return useQuery({
    queryKey: ["knowledge-retrieval-tests", resourceId, testId],
    queryFn: () => getRetrievalTest(resourceId!, testId!),
    enabled: Boolean(resourceId && testId),
  });
}

export function useRunRetrievalTest(resourceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: RunRetrievalTestRequest) =>
      runRetrievalTest(resourceId, request),
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-retrieval-tests", resourceId],
      }),
  });
}

export function useKnowledgeEvaluations(resourceId: string | undefined) {
  const query = useQuery({
    queryKey: ["knowledge-evaluations", resourceId],
    queryFn: () => listKnowledgeEvaluations(resourceId!),
    enabled: Boolean(resourceId),
    refetchInterval: (current) =>
      current.state.data?.some(
        (run) => run.status === "queued" || run.status === "running",
      )
        ? 2000
        : false,
  });
  return { evaluations: query.data ?? [], ...query };
}

export function useKnowledgeEvaluation(
  resourceId: string | undefined,
  runId: string | undefined,
) {
  return useQuery({
    queryKey: ["knowledge-evaluations", resourceId, runId],
    queryFn: () => getKnowledgeEvaluation(resourceId!, runId!),
    enabled: Boolean(resourceId && runId),
    refetchInterval: (current) =>
      current.state.data?.status === "queued" ||
      current.state.data?.status === "running"
        ? 2000
        : false,
  });
}

export function useStartKnowledgeEvaluation(resourceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: startKnowledgeEvaluation.bind(null, resourceId),
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-evaluations", resourceId],
      }),
  });
}

export function useRetryKnowledgeEvaluation(resourceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => retryKnowledgeEvaluation(resourceId, runId),
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-evaluations", resourceId],
      }),
  });
}

export function useStartKnowledgeEvaluationComparison(resourceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (
      request: Parameters<typeof startKnowledgeEvaluationComparison>[1],
    ) => startKnowledgeEvaluationComparison(resourceId, request),
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-evaluation-comparisons", resourceId],
      }),
  });
}

export function useKnowledgeEvaluationComparison(
  resourceId: string | undefined,
  comparisonId: string | undefined,
) {
  return useQuery({
    queryKey: ["knowledge-evaluation-comparisons", resourceId, comparisonId],
    queryFn: () => getKnowledgeEvaluationComparison(resourceId!, comparisonId!),
    enabled: Boolean(resourceId && comparisonId),
    refetchInterval: (current) =>
      current.state.data?.status === "queued" ? 2000 : false,
  });
}
