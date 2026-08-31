"use client";

import { useEffect, useRef } from "react";

import type { Skill } from "@/core/skills/type";
import { cn } from "@/lib/utils";

import { getMatchingSkillSuggestions } from "./slash-suggestions";

export type SlashOverlayProps = {
  skills: Skill[];
  allowedSkillNames?: readonly string[];
  query: string;
  activeIndex: number;
  onSelect: (skill: Skill) => void;
  onClose: () => void;
};

export function SlashOverlay({
  skills,
  allowedSkillNames,
  query,
  activeIndex,
  onSelect,
  onClose,
}: SlashOverlayProps) {
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
      className="workbench-slash-overlay bg-popover absolute right-0 bottom-full left-0 z-50 mb-0 box-border max-h-72 w-full min-w-0 overflow-y-auto rounded-md border p-1 shadow-md"
    >
      {suggestions.map((skill, i) => (
        <button
          key={skill.name}
          type="button"
          data-testid={`slash-option-${skill.name}`}
          className={cn(
            "type-body flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left outline-none",
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
          <span className="text-muted-foreground type-body min-w-0 flex-1 truncate">
            {skill.description}
          </span>
        </button>
      ))}
    </div>
  );
}
