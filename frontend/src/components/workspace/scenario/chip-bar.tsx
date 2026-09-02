"use client";

import { useCallback, useRef } from "react";

import { cn } from "@/lib/utils";

export function useRovingTabIndex<T extends string>(
  ids: T[],
  selectedId: T | null,
  onSelect: (id: T) => void,
) {
  const buttonRefs = useRef<Map<T, HTMLButtonElement>>(new Map());
  const focus = useCallback((id: T) => buttonRefs.current.get(id)?.focus(), []);
  const onKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (ids.length === 0) return;
      const current = selectedId ? ids.indexOf(selectedId) : 0;
      const deltas: Record<string, number> = {
        ArrowRight: 1,
        ArrowLeft: -1,
        Home: -current,
        End: ids.length - 1 - current,
      };
      if (!(event.key in deltas)) return;
      event.preventDefault();
      const next = (current + deltas[event.key]! + ids.length) % ids.length;
      const nextId = ids[next]!;
      onSelect(nextId);
      focus(nextId);
    },
    [focus, ids, onSelect, selectedId],
  );
  return { buttonRefs, onKeyDown };
}

interface ChipBarProps<T extends string> {
  items: Array<{ id: T; label: string }>;
  selectedId: T | null;
  onSelect: (id: T) => void;
  variant: "pill" | "chip";
  testId?: string;
}

export function ChipBar<T extends string>({
  items,
  selectedId,
  onSelect,
  variant,
  testId,
}: ChipBarProps<T>) {
  const ids = items.map((item) => item.id);
  const { buttonRefs, onKeyDown } = useRovingTabIndex(
    ids,
    selectedId,
    onSelect,
  );
  if (items.length === 0) return null;

  return (
    <div
      className="flex w-max min-w-full items-center justify-center gap-2 overflow-x-auto [&::-webkit-scrollbar]:hidden"
      role="tablist"
      data-testid={testId}
      onKeyDown={onKeyDown}
    >
      {items.map((item) => {
        const active = selectedId === item.id;
        return (
          <button
            key={item.id}
            ref={(element) => {
              if (element) buttonRefs.current.set(item.id, element);
            }}
            role="tab"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            data-state={active ? "active" : "inactive"}
            className={cn(
              "type-body shrink-0 rounded-full border px-5 py-2.5 font-medium transition-all",
              variant === "pill"
                ? active
                  ? "border-primary bg-primary/10 text-primary"
                  : "bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground border-transparent"
                : active
                  ? "border-accent bg-accent/10 text-accent-foreground"
                  : "bg-muted/30 text-muted-foreground hover:bg-muted/60 hover:text-foreground border-transparent",
            )}
            onClick={() => onSelect(item.id)}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
