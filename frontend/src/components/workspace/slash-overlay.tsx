"use client";

import { useEffect, useRef } from "react";

import type { Skill } from "@/core/skills/type";
import { cn } from "@/lib/utils";

import { getMatchingSkillSuggestions } from "./slash-suggestions";

export type SlashOverlayProps = {
  skills: Skill[];
  query: string;
  activeIndex: number;
  onSelect: (skill: Skill) => void;
  onClose: () => void;
};

export function SlashOverlay({
  skills,
  query,
  activeIndex,
  onSelect,
  onClose,
}: SlashOverlayProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const suggestions = getMatchingSkillSuggestions(skills, query);

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
      className="bg-popover absolute bottom-full left-0 z-50 mb-1 max-h-60 w-full overflow-y-auto rounded-md border p-1 shadow-md"
    >
      {suggestions.map((skill, i) => (
        <button
          key={skill.name}
          type="button"
          data-testid={`slash-option-${skill.name}`}
          className={cn(
            "flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm outline-none",
            i === activeIndex
              ? "bg-accent text-accent-foreground"
              : "hover:bg-accent/50",
          )}
          onMouseDown={(e) => {
            e.preventDefault();
            onSelect(skill);
          }}
        >
          <span className="font-medium">{skill.name}</span>
          <span className="text-muted-foreground truncate text-xs">
            {skill.description}
          </span>
        </button>
      ))}
    </div>
  );
}
