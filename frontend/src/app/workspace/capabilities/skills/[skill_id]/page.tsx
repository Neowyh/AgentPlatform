"use client";

import { ArrowLeftIcon, Code2Icon, DownloadIcon, EditIcon } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  const download = async () => {
    const url = URL.createObjectURL(await exportSkill(skill.resource_id!));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${invocation}.skill`;
    anchor.click();
    URL.revokeObjectURL(url);
  };
  return (
    <main className="flex size-full flex-col">
      <WorkspaceBreadcrumb skill={skill} />
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon-sm" asChild>
            <Link
              href="/workspace/capabilities/skills"
              aria-label={t.settings.skills.backToSkills}
            >
              <ArrowLeftIcon className="h-4 w-4" />
            </Link>
          </Button>
          <div className="flex items-center gap-2">
            <div className="bg-primary/10 text-primary flex h-9 w-9 items-center justify-center rounded-lg">
              <Code2Icon className="h-5 w-5" />
            </div>
            <div>
              <h1 className="type-page-title font-semibold">{skill.name}</h1>
              <p className="text-muted-foreground type-body mt-0.5">
                {skill.summary ?? skill.description}
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
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
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto grid max-w-4xl gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>{t.settings.skills.information}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Badge>{skill.category}</Badge>
                <Badge variant="outline">{skill.visibility ?? "private"}</Badge>
                <Badge variant="outline">/{invocation}</Badge>
                {skill.read_only && (
                  <Badge variant="outline">{t.settings.skills.readOnly}</Badge>
                )}
              </div>
              <Detail
                label={t.settings.skills.license}
                value={skill.license || t.settings.skills.notSpecified}
              />
              <Detail
                label={t.settings.skills.allowedTools}
                value={
                  skill.allowed_tools?.join(", ") ??
                  t.settings.skills.notSpecified
                }
              />
              <Detail
                label={t.settings.skills.internet}
                value={
                  skill.requires_internet
                    ? t.settings.skills.required
                    : t.settings.skills.notRequired
                }
              />
              <Detail
                label={t.settings.skills.version}
                value={`v${skill.latest_version ?? 1}`}
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t.settings.skills.skillMd}</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="bg-muted type-body max-h-[28rem] overflow-auto rounded-md p-4 whitespace-pre-wrap">
                {skill.skill_md ?? t.settings.skills.notSpecified}
              </pre>
            </CardContent>
          </Card>
        </div>
      </div>
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
    </main>
  );
}
function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground type-caption">{label}</dt>
      <dd className="type-body mt-1">{value}</dd>
    </div>
  );
}
