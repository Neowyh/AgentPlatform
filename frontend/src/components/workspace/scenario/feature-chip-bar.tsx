"use client";

import { useCallback, useRef } from "react";

import { cn } from "@/lib/utils";

export interface FeatureChipItem {
  id: string;
  label: string;
  icon?: React.ReactNode;
  description?: string;
}

interface FeatureChipBarProps {
  items: FeatureChipItem[];
  onSelect: (id: string) => void;
  className?: string;
}

export function FeatureChipBar({
  items,
  onSelect,
  className,
}: FeatureChipBarProps) {
  const buttonRefs = useRef<Map<string, HTMLButtonElement>>(new Map());

  const focusButton = useCallback((id: string) => {
    buttonRefs.current.get(id)?.focus();
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (items.length === 0) return;
      const ids = items.map((item) => item.id);
      const currentIndex = 0;
      let next: number | null = null;

      switch (e.key) {
        case "ArrowRight":
          next = (currentIndex + 1) % ids.length;
          break;
        case "ArrowLeft":
          next = (currentIndex - 1 + ids.length) % ids.length;
          break;
        case "Home":
          next = 0;
          break;
        case "End":
          next = ids.length - 1;
          break;
        default:
          return;
      }

      e.preventDefault();
      const nextId = ids[next]!;
      onSelect(nextId);
      focusButton(nextId);
    },
    [items, onSelect, focusButton],
  );

  if (items.length === 0) return null;

  return (
    <div
      className={cn(
        "flex items-center gap-2 overflow-x-auto py-2 [&::-webkit-scrollbar]:hidden",
        className,
      )}
      role="tablist"
      data-testid="feature-chip-bar"
      onKeyDown={handleKeyDown}
    >
      {items.map((item) => (
        <button
          key={item.id}
          ref={(el) => {
            if (el) buttonRefs.current.set(item.id, el);
          }}
          role="tab"
          tabIndex={0}
          data-state="inactive"
          className={cn(
            "flex shrink-0 items-center gap-1.5 rounded-full border px-4 py-2 text-sm font-medium transition-all",
            "bg-muted/30 text-muted-foreground hover:bg-muted/60 hover:text-foreground border-transparent",
            "hover:shadow-sm active:scale-95",
          )}
          onClick={() => onSelect(item.id)}
        >
          {item.icon && (
            <span className="flex size-4 items-center justify-center">
              {item.icon}
            </span>
          )}
          <span>{item.label}</span>
          {item.description && (
            <span className="text-muted-foreground/60 text-xs">
              {item.description}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
