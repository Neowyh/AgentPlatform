"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { Button } from "@/components/ui/button";
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
    <main className="workbench-resource-surface space-y-4 p-6">
      <Link href="/workspace/capabilities/skills">
        {t.settings.skills.backToSkills}
      </Link>
      <h1 className="type-page-title font-semibold">{skill.name}</h1>
      <p className="text-muted-foreground type-body">{skill.description}</p>
      <Button asChild>
        <Link
          href={`/workspace/chats/new?prompt=${encodeURIComponent(`/${invocation} `)}`}
        >
          {t.settings.skills.use}
        </Link>
      </Button>
    </main>
  );
}
