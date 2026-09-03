"use client";

import { useI18n } from "@/core/i18n/hooks";
import {
  findSkillForChip,
  skillDescription,
} from "@/core/scenarios/descriptions";
import type { TaskChip as TaskChipType } from "@/core/scenarios/types";
import { useSkills } from "@/core/skills/hooks";

import { ChipBar } from "./chip-bar";

interface TaskChipBarProps {
  chips: TaskChipType[];
  selectedTaskId: string | null;
  onSelect: (taskId: string) => void;
}

export function TaskChipBar({
  chips,
  selectedTaskId,
  onSelect,
}: TaskChipBarProps) {
  const { skills } = useSkills();
  const { locale } = useI18n();
  return (
    <ChipBar
      items={chips.map((chip) => {
        const skill = findSkillForChip(skills, chip.skillName);
        return {
          id: chip.taskId,
          label: chip.label,
          description: skill ? skillDescription(skill, locale) : undefined,
        };
      })}
      selectedId={selectedTaskId}
      onSelect={onSelect}
      variant="chip"
      testId="task-chip-bar"
    />
  );
}
