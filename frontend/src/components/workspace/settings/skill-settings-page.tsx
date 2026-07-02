"use client";

import { EditIcon, PlayIcon, ShareIcon, SparklesIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemTitle,
} from "@/components/ui/item";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useAuth } from "@/core/auth/AuthProvider";
import { useI18n } from "@/core/i18n/hooks";
import { submitSkillApplication } from "@/core/skills/api";
import { useEnableSkill, useSkills } from "@/core/skills/hooks";
import type { Skill } from "@/core/skills/type";
import { env } from "@/env";

import { SettingsSection } from "./settings-section";
import { SkillApplyDialog } from "./skill-apply-dialog";
import { SkillEditor } from "./skill-editor";

export function SkillSettingsPage({ onClose }: { onClose?: () => void } = {}) {
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
        <SkillSettingsList skills={skills} onClose={onClose} />
      )}
    </SettingsSection>
  );
}

function SkillSettingsList({
  skills,
  onClose,
}: {
  skills: Skill[];
  onClose?: () => void;
}) {
  const { t } = useI18n();
  const router = useRouter();
  const { user } = useAuth();
  const [filter, setFilter] = useState<string>("public");
  const { mutate: enableSkill } = useEnableSkill();
  const [editingSkill, setEditingSkill] = useState<Skill | null>(null);
  const [testingSkill, setTestingSkill] = useState<Skill | null>(null);
  const [applyingSkill, setApplyingSkill] = useState<Skill | null>(null);

  const filteredSkills = useMemo(
    () => skills.filter((skill) => skill.category === filter),
    [skills, filter],
  );

  const handleCreateSkill = () => {
    onClose?.();
    router.push("/workspace/chats/new?mode=skill");
  };

  const handleEditSkill = (skill: Skill) => {
    setEditingSkill(skill);
  };

  const handleTestSkill = (skill: Skill) => {
    setTestingSkill(skill);
  };

  const handleApplyOpen = (skill: Skill) => {
    setApplyingSkill(skill);
  };

  const handleSubmitApplication = async (
    requestLevel: string,
    reason: string,
  ) => {
    if (!applyingSkill) return;
    try {
      await submitSkillApplication(applyingSkill.name, {
        request_level: requestLevel as "department" | "public",
        reason,
      });
      toast.success(t.settings.skills.applicationSubmitted);
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : t.settings.skills.applicationSubmitFailed,
      );
    }
    setApplyingSkill(null);
  };

  const handleSaveSkill = async (content: string) => {
    // TODO: Implement save skill content API
    console.log("Saving skill:", editingSkill?.name, content);
    setEditingSkill(null);
  };

  const isSkillOwner = (skill: Skill) => {
    if (skill.category !== "custom") return false;
    if (!skill.owner_id) return false;
    return skill.owner_id === user?.id;
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
        <div>
          <Button size="sm" onClick={handleCreateSkill}>
            <SparklesIcon className="size-4" />
            {t.settings.skills.createSkill}
          </Button>
        </div>
      </header>
      {filteredSkills.length === 0 && (
        <EmptySkill onCreateSkill={handleCreateSkill} />
      )}
      {filteredSkills.length > 0 &&
        filteredSkills.map((skill) => (
          <Item className="w-full" variant="outline" key={skill.name}>
            <ItemContent>
              <ItemTitle>
                <div className="flex items-center gap-2">
                  <button
                    className="text-left font-medium hover:underline"
                    onClick={() => handleEditSkill(skill)}
                  >
                    {skill.name}
                  </button>
                  <Badge variant="outline" className="text-xs">
                    {skill.category}
                  </Badge>
                  {skill.license === "requires_internet" && (
                    <Tooltip>
                      <TooltipTrigger>
                        <Badge variant="secondary" className="text-xs">
                          Requires Internet
                        </Badge>
                      </TooltipTrigger>
                      <TooltipContent>
                        This skill requires an internet connection to function
                      </TooltipContent>
                    </Tooltip>
                  )}
                </div>
              </ItemTitle>
              <ItemDescription className="line-clamp-4">
                {skill.description}
              </ItemDescription>
            </ItemContent>
            <ItemActions>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => handleEditSkill(skill)}
                  title="Edit skill"
                >
                  <EditIcon className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => handleTestSkill(skill)}
                  title="Test skill"
                >
                  <PlayIcon className="h-4 w-4" />
                </Button>
                {/* Apply Open Button - only for custom skills owned by the user */}
                {skill.category === "custom" && isSkillOwner(skill) && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => handleApplyOpen(skill)}
                        title={t.settings.skills.applyOpen}
                      >
                        <ShareIcon className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      {t.settings.skills.applyOpenTooltip}
                    </TooltipContent>
                  </Tooltip>
                )}
                <Switch
                  checked={skill.enabled}
                  disabled={
                    env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true" ||
                    skill.category === "public"
                  }
                  onCheckedChange={(checked) =>
                    enableSkill({ skillName: skill.name, enabled: checked })
                  }
                />
                {skill.category === "public" && (
                  <Tooltip>
                    <TooltipTrigger>
                      <Badge variant="secondary" className="text-xs">
                        {t.settings.skills.locked}
                      </Badge>
                    </TooltipTrigger>
                    <TooltipContent>
                      {t.settings.skills.lockedTooltip}
                    </TooltipContent>
                  </Tooltip>
                )}
              </div>
            </ItemActions>
          </Item>
        ))}

      {/* Skill Editor Dialog */}
      <Dialog
        open={!!editingSkill}
        onOpenChange={(open) => !open && setEditingSkill(null)}
      >
        <DialogContent className="flex h-[75vh] max-w-[calc(100%-2rem)] flex-col p-0 sm:max-w-4xl">
          {editingSkill && (
            <SkillEditor
              skillName={editingSkill.name}
              initialContent={`---
name: ${editingSkill.name}
description: ${editingSkill.description}
---

# ${editingSkill.name}

${editingSkill.description}
`}
              onSave={handleSaveSkill}
              onClose={() => setEditingSkill(null)}
            />
          )}
        </DialogContent>
      </Dialog>

      {/* Test Skill Dialog */}
      <Dialog
        open={!!testingSkill}
        onOpenChange={(open) => !open && setTestingSkill(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Test Skill: {testingSkill?.name}</DialogTitle>
            <DialogDescription>
              Test this skill by sending a message. The skill will be available
              in the conversation context.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <p className="text-muted-foreground text-sm">
              To test this skill, start a new conversation with the skill
              enabled. You can do this by:
            </p>
            <ol className="text-muted-foreground list-inside list-decimal space-y-2 text-sm">
              <li>Going to a new chat</li>
              <li>Enabling the skill in the chat settings</li>
              <li>Sending a message that uses the skill</li>
            </ol>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setTestingSkill(null)}>
                Close
              </Button>
              <Button
                onClick={() => {
                  setTestingSkill(null);
                  router.push("/workspace/chats/new");
                }}
              >
                Start New Chat
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Skill Apply Dialog */}
      <SkillApplyDialog
        skill={applyingSkill}
        open={!!applyingSkill}
        onOpenChange={(open) => !open && setApplyingSkill(null)}
        onSubmit={handleSubmitApplication}
      />
    </div>
  );
}

function EmptySkill({ onCreateSkill }: { onCreateSkill: () => void }) {
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
      <EmptyContent>
        <Button onClick={onCreateSkill}>{t.settings.skills.emptyButton}</Button>
      </EmptyContent>
    </Empty>
  );
}
