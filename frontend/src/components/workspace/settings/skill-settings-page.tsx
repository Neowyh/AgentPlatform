"use client";

import { SparklesIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  Item,
  ItemContent,
  ItemDescription,
  ItemTitle,
} from "@/components/ui/item";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/core/i18n/hooks";
import { useSkills } from "@/core/skills/hooks";
import type { Skill } from "@/core/skills/type";
import { createVisibilityApplication } from "@/core/visibility-applications/api";

import { SettingsSection } from "./settings-section";
import { SkillApplyDialog } from "./skill-apply-dialog";

export function SkillSettingsPage() {
  const { t } = useI18n();
  const { skills, isLoading, error } = useSkills();
  return (
    <SettingsSection
      title={t.settings.skills.title}
      description={t.settings.skills.description}
    >
      {isLoading ? (
        <div className="text-muted-foreground text-sm">{t.common.loading}</div>
      ) : error ? (
        <div>Error: {error.message}</div>
      ) : (
        <SkillSettingsList skills={skills} />
      )}
    </SettingsSection>
  );
}

function SkillSettingsList({ skills }: { skills: Skill[] }) {
  const { t } = useI18n();
  const [filter, setFilter] = useState<string>("public");
  const [applySkill, setApplySkill] = useState<Skill | null>(null);

  const filteredSkills = useMemo(
    () => skills.filter((skill) => skill.category === filter),
    [skills, filter],
  );

  const handleApplySubmit = async (
    targetVisibility: string,
    reason: string,
  ) => {
    if (!applySkill) return;
    try {
      await createVisibilityApplication({
        resource_type: "skill",
        resource_id: applySkill.name,
        target_visibility: targetVisibility,
        reason,
      });
      toast.success(t.settings.skills.applicationSubmitted);
      setApplySkill(null);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to submit application",
      );
    }
  };

  return (
    <div className="flex w-full flex-col gap-4">
      <header className="flex justify-between">
        <div className="flex gap-2">
          <Tabs defaultValue="public" onValueChange={setFilter}>
            <TabsList variant="line">
              <TabsTrigger value="public">{t.common.public}</TabsTrigger>
              <TabsTrigger value="custom">{t.common.custom}</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </header>
      {filteredSkills.length === 0 && <EmptySkill />}
      {filteredSkills.length > 0 &&
        filteredSkills.map((skill) => (
          <Item className="w-full" variant="outline" key={skill.name}>
            <ItemContent>
              <ItemTitle>
                <div className="flex items-center gap-2">
                  <span className="font-medium">{skill.name}</span>
                  <Badge variant="outline" className="text-xs">
                    {skill.category}
                  </Badge>
                </div>
              </ItemTitle>
              <ItemDescription className="line-clamp-4">
                {skill.description}
              </ItemDescription>
            </ItemContent>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setApplySkill(skill)}
            >
              {t.settings.skills.applyVisibility}
            </Button>
          </Item>
        ))}
      <SkillApplyDialog
        skill={applySkill}
        open={applySkill !== null}
        onOpenChange={(open) => !open && setApplySkill(null)}
        onSubmit={handleApplySubmit}
      />
    </div>
  );
}

function EmptySkill() {
  const { t } = useI18n();
  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <SparklesIcon />
        </EmptyMedia>
        <EmptyTitle>{t.settings.skills.emptyTitle}</EmptyTitle>
        <EmptyDescription>
          {t.settings.skills.emptyDescription}
        </EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}
