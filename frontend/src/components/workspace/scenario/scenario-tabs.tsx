"use client";

import { Briefcase, Palette, ShieldCheck, type LucideIcon } from "lucide-react";

import { useI18n } from "@/core/i18n/hooks";
import { SCENARIO_ICONS, SCENARIO_IDS } from "@/core/scenarios/config";
import type { ScenarioId } from "@/core/scenarios/types";
import { cn } from "@/lib/utils";

import { useRovingTabIndex } from "./chip-bar";

const ICONS: Record<string, LucideIcon> = {
  Briefcase,
  Palette,
  ShieldCheck,
};

interface ScenarioTabsProps {
  selected: ScenarioId | null;
  onSelect: (id: ScenarioId | null) => void;
}

export function ScenarioTabs({ selected, onSelect }: ScenarioTabsProps) {
  const { t } = useI18n();
  const { buttonRefs, onKeyDown } = useRovingTabIndex(
    SCENARIO_IDS,
    selected,
    onSelect,
  );

  return (
    <div
      className="bg-background/80 border-border/50 flex items-center justify-center gap-2 rounded-full border p-1.5 shadow-sm backdrop-blur-md"
      role="tablist"
      data-testid="scenario-tabs"
      onKeyDown={onKeyDown}
    >
      {SCENARIO_IDS.map((id) => {
        const Icon = ICONS[SCENARIO_ICONS[id]] ?? Palette;
        const isActive = selected === id;
        return (
          <button
            key={id}
            ref={(el) => {
              if (el) buttonRefs.current.set(id, el);
            }}
            role="tab"
            aria-selected={isActive}
            tabIndex={isActive ? 0 : -1}
            data-state={isActive ? "active" : "inactive"}
            className={cn(
              "type-body flex items-center gap-2 rounded-full border px-6 py-3 font-medium transition-all",
              isActive
                ? "bg-muted text-foreground border-transparent font-semibold shadow-sm"
                : "text-muted-foreground hover:bg-muted/60 hover:text-foreground border-transparent",
              "hover:shadow-sm active:scale-95",
            )}
            onClick={() => onSelect(isActive ? null : id)}
          >
            <Icon className="size-5" />
            {t.scenarios[id]}
          </button>
        );
      })}
    </div>
  );
}
