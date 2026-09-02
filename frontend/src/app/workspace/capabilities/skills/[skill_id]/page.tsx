"use client";

import { Code2Icon, DownloadIcon, EditIcon } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  ResourceDetailCard,
  ResourceDetailLayout,
  ResourceDetailRow,
} from "@/components/workspace/resources/resource-detail-layout";
import { SkillApplyDialog } from "@/components/workspace/settings/skill-apply-dialog";
import { WorkspaceBreadcrumb } from "@/components/workspace/workspace-breadcrumb";
import { useI18n } from "@/core/i18n/hooks";
import { exportSkill, useSkill } from "@/core/skills";
import {
  changeResourceVisibility,
  createVisibilityApplication,
} from "@/core/visibility-applications/api";

export default function SkillDetailPage() {
  const { t } = useI18n();
  const { skill_id: skillId } = useParams<{ skill_id: string }>();
  const { skill, isLoading, error } = useSkill(skillId);
  const [applyOpen, setApplyOpen] = useState(false);
  if (isLoading)
    return <div className="text-muted-foreground p-6">{t.common.loading}</div>;
  if (error || !skill)
    return (
      <div className="text-muted-foreground p-6">
        {error?.message ?? t.settings.skills.notFound}
      </div>
    );
  const invocation = skill.slug ?? skill.name;
  const visibility =
    skill.visibility === "public"
      ? t.settings.skills.applyDialogVisibilityPublic
      : skill.visibility === "department"
        ? t.settings.skills.applyDialogVisibilityDepartment
        : t.settings.skills.applyDialogVisibilityPrivate;
  const download = async () => {
    try {
      const url = URL.createObjectURL(await exportSkill(skill.resource_id!));
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${invocation}.skill`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error(t.settings.skills.exportFailed);
    }
  };
  return (
    <ResourceDetailLayout
      breadcrumb={<WorkspaceBreadcrumb skill={skill} />}
      backHref="/workspace/capabilities/skills"
      icon={<Code2Icon className="h-5 w-5" />}
      typeLabel={t.resources.skills}
      title={skill.name}
      description={skill.summary ?? skill.description}
      status={visibility}
      actions={
        <>
          <Button asChild>
            <Link
              href={`/workspace/chats/new?prompt=${encodeURIComponent(`/${invocation} `)}`}
            >
              {t.settings.skills.use}
            </Link>
          </Button>
          {skill.category === "custom" && (
            <Button variant="outline" onClick={() => setApplyOpen(true)}>
              {t.settings.skills.applyVisibility}
            </Button>
          )}
          {skill.can_modify && (
            <>
              <Button variant="outline" asChild>
                <Link href={`/workspace/capabilities/skills/${skillId}/edit`}>
                  <EditIcon className="mr-1.5 h-4 w-4" />
                  {t.settings.skills.edit}
                </Link>
              </Button>
              <Button variant="outline" onClick={() => void download()}>
                <DownloadIcon className="mr-1.5 h-4 w-4" />
                {t.settings.skills.export}
              </Button>
            </>
          )}
        </>
      }
    >
      <ResourceDetailCard title={t.settings.skills.information}>
        <dl>
          <ResourceDetailRow
            label={t.settings.skills.category}
            value={
              skill.category === "custom" ? t.common.custom : t.common.public
            }
          />
          <ResourceDetailRow
            label={t.settings.skills.command}
            value={`/${invocation}`}
          />
          <ResourceDetailRow
            label={t.settings.skills.license}
            value={skill.license || t.settings.skills.notSpecified}
          />
          <ResourceDetailRow
            label={t.settings.skills.allowedTools}
            value={
              skill.allowed_tools?.join(", ") ?? t.settings.skills.notSpecified
            }
          />
          <ResourceDetailRow
            label={t.settings.skills.internet}
            value={
              skill.requires_internet
                ? t.settings.skills.required
                : t.settings.skills.notRequired
            }
          />
          <ResourceDetailRow
            label={t.settings.skills.version}
            value={`v${skill.latest_version ?? 1}`}
          />
        </dl>
      </ResourceDetailCard>
      <ResourceDetailCard title={t.settings.skills.usage}>
        <dl>
          <ResourceDetailRow
            label={t.settings.skills.command}
            value={`/${invocation}`}
          />
          <ResourceDetailRow
            label={t.settings.skills.input}
            value={t.settings.skills.inputDescription}
          />
          <ResourceDetailRow
            label={t.settings.skills.output}
            value={t.settings.skills.outputDescription}
          />
        </dl>
      </ResourceDetailCard>
      <ResourceDetailCard
        title={t.settings.skills.skillMd}
        className="lg:col-span-2"
      >
        <pre className="bg-muted type-body max-h-[30rem] overflow-auto rounded-xl p-4 whitespace-pre-wrap">
          {skill.skill_md ?? t.settings.skills.notSpecified}
        </pre>
      </ResourceDetailCard>
      <SkillApplyDialog
        skill={applyOpen ? skill : null}
        open={applyOpen}
        onOpenChange={setApplyOpen}
        onSubmit={async (targetVisibility, reason) => {
          await createVisibilityApplication({
            resource_type: "skill",
            resource_id: skill.resource_id ?? skill.name,
            target_visibility: targetVisibility,
            reason,
          });
          toast.success(t.settings.skills.applicationSubmitted);
          setApplyOpen(false);
        }}
        onChange={async (targetVisibility, cascade) => {
          await changeResourceVisibility({
            resource_id: skill.resource_id ?? skill.name,
            visibility: targetVisibility,
            cascade,
          });
          toast.success(t.settings.skills.visibilityUpdated);
          setApplyOpen(false);
        }}
      />
    </ResourceDetailLayout>
  );
}
