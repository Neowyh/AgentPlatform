"use client";

import { ArrowLeftIcon } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { SkillEditor } from "@/components/workspace/settings/skill-editor";
import { WorkspaceBreadcrumb } from "@/components/workspace/workspace-breadcrumb";
import { useI18n } from "@/core/i18n/hooks";
import { useSkill, useUpdateSkill } from "@/core/skills";

export default function SkillEditPage() {
  const { t } = useI18n();
  const router = useRouter();
  const { skill_id: skillId } = useParams<{ skill_id: string }>();
  const { skill, isLoading, error } = useSkill(skillId);
  const update = useUpdateSkill();
  const close = useCallback(
    () => router.push(`/workspace/capabilities/skills/${skillId}`),
    [router, skillId],
  );
  if (isLoading)
    return <div className="text-muted-foreground p-6">{t.common.loading}</div>;
  if (error || !skill)
    return (
      <div className="text-muted-foreground p-6">
        {error?.message ?? t.settings.skills.notFound}
      </div>
    );
  if (!skill.can_modify || skill.read_only)
    return (
      <div className="flex size-full items-center justify-center">
        <div className="space-y-4 text-center">
          <p>{t.settings.skills.readOnly}</p>
          <Button variant="outline" onClick={close}>
            <ArrowLeftIcon className="mr-1.5 h-4 w-4" />
            {t.settings.skills.backToSkills}
          </Button>
        </div>
      </div>
    );
  return (
    <div className="flex size-full flex-col">
      <WorkspaceBreadcrumb skill={skill} />
      <SkillEditor
        skillName={skill.name}
        initialContent={skill.skill_md ?? ""}
        onClose={close}
        onSave={async (content) => {
          try {
            await update.mutateAsync({
              resourceId: skill.resource_id!,
              content,
              expectedRevision: skill.draft_revision ?? 0,
            });
            toast.success(t.settings.skills.saved);
            close();
          } catch (err) {
            toast.error(
              err instanceof Error ? err.message : t.settings.skills.saveFailed,
            );
            throw err;
          }
        }}
      />
    </div>
  );
}
