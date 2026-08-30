"use client";

import type { TaskChip as TaskChipType } from "@/core/scenarios/types";

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
  return (
    <ChipBar
      items={chips.map((chip) => ({ id: chip.taskId, label: chip.label }))}
      selectedId={selectedTaskId}
      onSelect={onSelect}
      variant="chip"
      testId="task-chip-bar"
    />
  );
}
