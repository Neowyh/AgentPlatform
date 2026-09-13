import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createKnowledgeBase,
  listKnowledgeBases,
  listKnowledgeDocuments,
  uploadKnowledgeDocument,
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
