"use client";

import { useCallback, useRef } from "react";

import type { TaskChip as TaskChipType } from "@/core/scenarios/types";
import { cn } from "@/lib/utils";

interface TaskChipBarProps {
  chips: TaskChipType[];
  selectedSkillName: string | null;
  onSelect: (skillName: string) => void;
}

export function TaskChipBar({
  chips,
  selectedSkillName,
  onSelect,
}: TaskChipBarProps) {
  const buttonRefs = useRef<Map<string, HTMLButtonElement>>(new Map());

  const focusButton = useCallback((skillName: string) => {
    buttonRefs.current.get(skillName)?.focus();
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (chips.length === 0) return;
      const names = chips.map((c) => c.skillName);
      const current = selectedSkillName ? names.indexOf(selectedSkillName) : 0;
      let next: number | null = null;

      switch (e.key) {
        case "ArrowRight":
          next = (current + 1) % names.length;
          break;
        case "ArrowLeft":
          next = (current - 1 + names.length) % names.length;
          break;
        case "Home":
          next = 0;
          break;
        case "End":
          next = names.length - 1;
          break;
        default:
          return;
      }

      e.preventDefault();
      const nextName = names[next]!;
      onSelect(nextName);
      focusButton(nextName);
    },
    [chips, selectedSkillName, onSelect, focusButton],
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
        const isActive = selectedSkillName === chip.skillName;
        return (
          <button
            key={chip.skillName}
            ref={(el) => {
              if (el) buttonRefs.current.set(chip.skillName, el);
            }}
            role="tab"
            aria-selected={isActive}
            tabIndex={isActive ? 0 : -1}
            data-state={isActive ? "active" : "inactive"}
            className={cn(
              "shrink-0 rounded-full border px-3 py-1 text-xs font-medium transition-all",
              isActive
                ? "border-accent bg-accent/10 text-accent-foreground"
                : "bg-muted/30 text-muted-foreground hover:bg-muted/60 hover:text-foreground border-transparent",
            )}
            onClick={() => onSelect(chip.skillName)}
          >
            {chip.label}
          </button>
        );
      })}
    </div>
  );
}
