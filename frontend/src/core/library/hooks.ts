import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createKnowledgeBase,
  createKnowledgeRevision,
  getKnowledgeRevision,
  listKnowledgeBases,
  listKnowledgeDocuments,
  listKnowledgeRevisions,
  publishKnowledgeRevision,
  uploadKnowledgeDocument,
  retryKnowledgeDocument,
  rebuildKnowledgeDocumentIndex,
  deleteKnowledgeDocument,
} from "./api";
import type { CreateKnowledgeBaseRequest } from "./api";

export function useKnowledgeBases() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["knowledge-bases"],
    queryFn: listKnowledgeBases,
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
