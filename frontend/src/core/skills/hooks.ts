import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { enableSkill, getSkill, loadSkills, updateSkill } from "./api";

export function useSkills() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["skills"],
    queryFn: () => loadSkills(),
  });
  return { skills: data ?? [], isLoading, error, refetch };
}

export function useEnableSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      skillName,
      enabled,
    }: {
      skillName: string;
      enabled: boolean;
    }) => {
      await enableSkill(skillName, enabled);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["skills"] });
    },
  });
}

export function useSkill(resourceId: string | null | undefined) {
  const query = useQuery({
    queryKey: ["skills", resourceId],
    queryFn: () => getSkill(resourceId!),
    enabled: !!resourceId,
  });
  return {
    skill: query.data ?? null,
    isLoading: query.isLoading,
    error: query.error,
  };
}

export function useUpdateSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      resourceId,
      content,
      expectedRevision,
    }: {
      resourceId: string;
      content: string;
      expectedRevision: number;
    }) => updateSkill(resourceId, content, expectedRevision),
    onSuccess: (_data, { resourceId }) => {
      void queryClient.invalidateQueries({ queryKey: ["skills"] });
      void queryClient.invalidateQueries({ queryKey: ["skills", resourceId] });
    },
  });
}
