"use client";

import { XIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export interface SelectedTag {
  id: string;
  label: string;
  icon?: React.ReactNode;
}

interface SelectedTagsProps {
  tags: SelectedTag[];
  onRemove: (id: string) => void;
  className?: string;
}

export function SelectedTags({ tags, onRemove, className }: SelectedTagsProps) {
  if (tags.length === 0) return null;

  return (
    <div
      className={cn("flex flex-wrap items-center gap-2", className)}
      data-testid="selected-tags"
    >
      {tags.map((tag) => (
        <span
          key={tag.id}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-medium",
            "border-primary/30 bg-primary/10 text-primary",
          )}
        >
          {tag.icon && (
            <span className="flex size-3.5 items-center justify-center">
              {tag.icon}
            </span>
          )}
          <span>{tag.label}</span>
          <button
            type="button"
            className={cn(
              "ml-0.5 flex size-4 items-center justify-center rounded-full",
              "text-primary/70 hover:bg-primary/20 hover:text-primary",
              "transition-colors",
            )}
            onClick={() => onRemove(tag.id)}
            aria-label={`Remove ${tag.label}`}
          >
            <XIcon className="size-3" />
          </button>
        </span>
      ))}
    </div>
  );
}

interface InlineSelectedTagProps {
  tag: SelectedTag;
  onRemove: (id: string) => void;
}

export function InlineSelectedTag({ tag, onRemove }: InlineSelectedTagProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium",
        "bg-primary/15 text-primary whitespace-nowrap shadow-sm",
        "cursor-default select-none",
      )}
      contentEditable={false}
      data-testid="inline-selected-tag"
      role="group"
      aria-label={`Scenario: ${tag.label}`}
    >
      {tag.icon && (
        <span className="flex size-3.5 items-center justify-center">
          {tag.icon}
        </span>
      )}
      <span>{tag.label}</span>
      <button
        type="button"
        className={cn(
          "ml-0.5 flex size-4 items-center justify-center rounded-full",
          "text-primary/60 hover:bg-primary/25 hover:text-primary",
          "transition-colors",
        )}
        onClick={(e) => {
          e.stopPropagation();
          onRemove(tag.id);
        }}
        aria-label={`Remove ${tag.label}`}
      >
        <XIcon className="size-3" />
      </button>
    </span>
  );
}
