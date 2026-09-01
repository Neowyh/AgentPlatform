"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { WorkspaceBreadcrumb } from "@/components/workspace/workspace-breadcrumb";
import { useI18n } from "@/core/i18n/hooks";
import { useSkills } from "@/core/skills";

export default function SkillDetailPage() {
  const { t } = useI18n();
  const { skill_id: skillId } = useParams<{ skill_id: string }>();
  const { skills, isLoading } = useSkills();
  if (isLoading)
    return <div className="text-muted-foreground p-6">{t.common.loading}</div>;
  const skill = skills.find(
    (item) => (item.resource_id ?? item.slug ?? item.name) === skillId,
  );
  if (!skill)
    return (
      <div className="text-muted-foreground p-6">
        {t.settings.skills.notFound}
      </div>
    );
  const invocation = skill.slug ?? skill.name;
  return (
    <main className="workbench-resource-surface flex size-full flex-col">
      <WorkspaceBreadcrumb />
      <div className="border-b px-6 py-4">
        <Link
          className="text-muted-foreground type-body"
          href="/workspace/capabilities/skills"
        >
          {t.settings.skills.backToSkills}
        </Link>
        <h1 className="type-page-title mt-2 font-semibold">{skill.name}</h1>
        <p className="text-muted-foreground type-body mt-1">
          {skill.description}
        </p>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        <Card className="mx-auto max-w-3xl">
          <CardHeader>
            <CardTitle>技能信息</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Badge>{skill.category}</Badge>
              <Badge variant="outline">{skill.visibility ?? "private"}</Badge>
              <Badge variant="outline">/{invocation}</Badge>
              {skill.read_only && <Badge variant="outline">只读</Badge>}
            </div>
            <Button asChild>
              <Link
                href={`/workspace/chats/new?prompt=${encodeURIComponent(`/${invocation} `)}`}
              >
                {t.settings.skills.use}
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
