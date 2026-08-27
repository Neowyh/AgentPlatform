"use client";

import { useCallback, useRef } from "react";

import type { AgentPill } from "@/core/scenarios/types";
import { cn } from "@/lib/utils";

interface AgentPillBarProps {
  pills: AgentPill[];
  selectedSlug: string | null;
  onSelect: (agentSlug: string) => void;
}

export function AgentPillBar({
  pills,
  selectedSlug,
  onSelect,
}: AgentPillBarProps) {
  const buttonRefs = useRef<Map<string, HTMLButtonElement>>(new Map());

  const focusButton = useCallback((slug: string) => {
    buttonRefs.current.get(slug)?.focus();
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (pills.length === 0) return;
      const slugs = pills.map((p) => p.agentSlug);
      const current = selectedSlug ? slugs.indexOf(selectedSlug) : 0;
      let next: number | null = null;

      switch (e.key) {
        case "ArrowRight":
          next = (current + 1) % slugs.length;
          break;
        case "ArrowLeft":
          next = (current - 1 + slugs.length) % slugs.length;
          break;
        case "Home":
          next = 0;
          break;
        case "End":
          next = slugs.length - 1;
          break;
        default:
          return;
      }

      e.preventDefault();
      const nextSlug = slugs[next]!;
      onSelect(nextSlug);
      focusButton(nextSlug);
    },
    [pills, selectedSlug, onSelect, focusButton],
  );

  if (pills.length === 0) return null;

  return (
    <div
      className="flex items-center gap-2 overflow-x-auto [&::-webkit-scrollbar]:hidden"
      role="tablist"
      data-testid="agent-pill-bar"
      onKeyDown={handleKeyDown}
    >
      {pills.map((pill) => {
        const isActive = selectedSlug === pill.agentSlug;
        return (
          <button
            key={pill.agentSlug}
            ref={(el) => {
              if (el) buttonRefs.current.set(pill.agentSlug, el);
            }}
            role="tab"
            aria-selected={isActive}
            tabIndex={isActive ? 0 : -1}
            data-state={isActive ? "active" : "inactive"}
            className={cn(
              "shrink-0 rounded-full border px-5 py-2.5 text-base font-medium transition-all",
              isActive
                ? "border-primary bg-primary/10 text-primary"
                : "bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground border-transparent",
            )}
            onClick={() => onSelect(pill.agentSlug)}
          >
            {pill.label}
          </button>
        );
      })}
    </div>
  );
}
