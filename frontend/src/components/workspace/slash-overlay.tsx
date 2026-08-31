"use client";

import { useEffect, useRef } from "react";

import type { Skill } from "@/core/skills/type";
import { cn } from "@/lib/utils";

import { getMatchingSkillSuggestions } from "./slash-suggestions";

export type SkillPickerProps = {
  skills: Skill[];
  allowedSkillNames?: readonly string[];
  query: string;
  activeIndex: number;
  onSelect: (skill: Skill) => void;
  onClose: () => void;
  title?: string;
};

export function SkillPicker({
  skills,
  allowedSkillNames,
  query,
  activeIndex,
  onSelect,
  onClose,
  title,
}: SkillPickerProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const suggestions = getMatchingSkillSuggestions(
    skills,
    query,
    allowedSkillNames,
  );

  useEffect(() => {
    if (suggestions.length === 0) {
      onClose();
    }
  }, [suggestions.length, onClose]);

  useEffect(() => {
    const active = listRef.current?.children[activeIndex] as
      | HTMLElement
      | undefined;
    active?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  if (suggestions.length === 0) return null;

  return (
    <div
      ref={listRef}
      data-testid="slash-overlay"
      className="workbench-slash-overlay bg-popover absolute right-0 bottom-full left-0 z-50 mb-2 box-border max-h-72 w-full min-w-0 overflow-y-auto rounded-2xl border p-2 shadow-lg"
    >
      {title ? (
        <div className="text-muted-foreground type-body px-2 py-1 font-medium">
          {title} ({suggestions.length})
        </div>
      ) : null}
      {suggestions.map((skill, i) => (
        <button
          key={skill.name}
          type="button"
          data-testid={`slash-option-${skill.name}`}
          className={cn(
            "type-body flex w-full min-w-0 items-center gap-2 rounded-lg px-2 py-2 text-left outline-none",
            i === activeIndex
              ? "bg-accent text-accent-foreground"
              : "hover:bg-accent/50",
          )}
          onMouseDown={(e) => {
            e.preventDefault();
            onSelect(skill);
          }}
        >
          <span className="shrink-0 font-medium">{skill.name}</span>
          <span className="text-muted-foreground type-supporting min-w-0 flex-1 truncate">
            {skill.description}
          </span>
        </button>
      ))}
    </div>
  );
}

export const SlashOverlay = SkillPicker;
