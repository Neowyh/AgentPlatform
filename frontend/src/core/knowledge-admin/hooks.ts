import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getKnowledgeReconciliation, runKnowledgeReconciliation } from "./api";

export function useKnowledgeReconciliation(
  knowledgeBaseId: string | undefined,
) {
  return useQuery({
    queryKey: ["knowledge-reconciliation", knowledgeBaseId],
    queryFn: () => getKnowledgeReconciliation(knowledgeBaseId),
  });
}

export function useRunKnowledgeReconciliation(knowledgeBaseId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => runKnowledgeReconciliation(knowledgeBaseId),
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-reconciliation", knowledgeBaseId],
      }),
  });
}
