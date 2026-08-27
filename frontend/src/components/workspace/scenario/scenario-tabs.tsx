"use client";

import { Briefcase, Palette, ShieldCheck, type LucideIcon } from "lucide-react";
import { useCallback, useRef } from "react";

import { useI18n } from "@/core/i18n/hooks";
import type { ScenarioId } from "@/core/scenarios/types";
import { cn } from "@/lib/utils";

const ICONS: Record<ScenarioId, LucideIcon> = {
  daily: Briefcase,
  creative: Palette,
  professional: ShieldCheck,
};

const SCENARIO_IDS: ScenarioId[] = ["daily", "creative", "professional"];

interface ScenarioTabsProps {
  selected: ScenarioId | null;
  onSelect: (id: ScenarioId | null) => void;
}

export function ScenarioTabs({ selected, onSelect }: ScenarioTabsProps) {
  const { t } = useI18n();
  const tabRefs = useRef<Map<ScenarioId, HTMLButtonElement>>(new Map());

  const focusTab = useCallback((id: ScenarioId) => {
    tabRefs.current.get(id)?.focus();
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const current = selected ? SCENARIO_IDS.indexOf(selected) : 0;
      let next: number | null = null;

      switch (e.key) {
        case "ArrowRight":
          next = (current + 1) % SCENARIO_IDS.length;
          break;
        case "ArrowLeft":
          next = (current - 1 + SCENARIO_IDS.length) % SCENARIO_IDS.length;
          break;
        case "Home":
          next = 0;
          break;
        case "End":
          next = SCENARIO_IDS.length - 1;
          break;
        default:
          return;
      }

      e.preventDefault();
      const nextId = SCENARIO_IDS[next]!;
      onSelect(nextId);
      focusTab(nextId);
    },
    [selected, onSelect, focusTab],
  );

  return (
    <div
      className="bg-background/80 border-border/50 flex items-center justify-center gap-2 rounded-full border p-1 shadow-sm backdrop-blur-md"
      role="tablist"
      data-testid="scenario-tabs"
      onKeyDown={handleKeyDown}
    >
      {SCENARIO_IDS.map((id) => {
        const Icon = ICONS[id];
        const isActive = selected === id;
        return (
          <button
            key={id}
            ref={(el) => {
              if (el) tabRefs.current.set(id, el);
            }}
            role="tab"
            aria-selected={isActive}
            tabIndex={isActive ? 0 : -1}
            data-state={isActive ? "active" : "inactive"}
            className={cn(
              "flex items-center gap-1.5 rounded-full border px-5 py-2.5 text-sm font-medium transition-all",
              isActive
                ? "bg-muted text-foreground border-transparent font-semibold shadow-sm"
                : "text-muted-foreground hover:bg-muted/60 hover:text-foreground border-transparent",
              "hover:shadow-sm active:scale-95",
            )}
            onClick={() => onSelect(isActive ? null : id)}
          >
            <Icon className="size-4" />
            {t.scenarios[id]}
          </button>
        );
      })}
    </div>
  );
}
