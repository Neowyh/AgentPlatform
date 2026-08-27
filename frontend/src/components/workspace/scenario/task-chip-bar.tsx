"use client";

import { useCallback, useRef } from "react";

import type { TaskChip as TaskChipType } from "@/core/scenarios/types";
import { cn } from "@/lib/utils";

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
  const buttonRefs = useRef<Map<string, HTMLButtonElement>>(new Map());

  const focusButton = useCallback((taskId: string) => {
    buttonRefs.current.get(taskId)?.focus();
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (chips.length === 0) return;
      const taskIds = chips.map((c) => c.taskId);
      const current = selectedTaskId ? taskIds.indexOf(selectedTaskId) : 0;
      let next: number | null = null;

      switch (e.key) {
        case "ArrowRight":
          next = (current + 1) % taskIds.length;
          break;
        case "ArrowLeft":
          next = (current - 1 + taskIds.length) % taskIds.length;
          break;
        case "Home":
          next = 0;
          break;
        case "End":
          next = taskIds.length - 1;
          break;
        default:
          return;
      }

      e.preventDefault();
      const nextTaskId = taskIds[next]!;
      onSelect(nextTaskId);
      focusButton(nextTaskId);
    },
    [chips, selectedTaskId, onSelect, focusButton],
  );

  if (chips.length === 0) return null;

  return (
    <div
      className="flex items-center gap-1.5 overflow-x-auto [&::-webkit-scrollbar]:hidden"
      role="tablist"
      data-testid="task-chip-bar"
      onKeyDown={handleKeyDown}
    >
      {chips.map((chip) => {
        const isActive = selectedTaskId === chip.taskId;
        return (
          <button
            key={chip.taskId}
            ref={(el) => {
              if (el) buttonRefs.current.set(chip.taskId, el);
            }}
            role="tab"
            aria-selected={isActive}
            tabIndex={isActive ? 0 : -1}
            data-state={isActive ? "active" : "inactive"}
            className={cn(
              "shrink-0 rounded-full border px-5 py-2.5 text-base font-medium transition-all",
              isActive
                ? "border-accent bg-accent/10 text-accent-foreground"
                : "bg-muted/30 text-muted-foreground hover:bg-muted/60 hover:text-foreground border-transparent",
            )}
            onClick={() => onSelect(chip.taskId)}
          >
            {chip.label}
          </button>
        );
      })}
    </div>
  );
}
