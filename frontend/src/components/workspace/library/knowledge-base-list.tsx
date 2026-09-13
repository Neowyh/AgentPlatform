"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCreateKnowledgeBase, useKnowledgeBases } from "@/core/library";

export function KnowledgeBaseList({
  onSelect,
}: {
  onSelect?: (id: string) => void;
}) {
  const { knowledgeBases, isLoading, error } = useKnowledgeBases();
  const createKnowledgeBase = useCreateKnowledgeBase();
  const [displayName, setDisplayName] = useState("");
  const [slug, setSlug] = useState("");

  async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!displayName.trim() || !slug.trim()) return;
    await createKnowledgeBase.mutateAsync({
      displayName: displayName.trim(),
      slug: slug.trim(),
    });
    setDisplayName("");
    setSlug("");
  }

  if (isLoading) {
    return (
      <div className="text-muted-foreground">Loading knowledge bases...</div>
    );
  }

  if (error) {
    return (
      <div className="text-muted-foreground">
        Unable to load knowledge bases.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <form className="flex flex-wrap gap-2" onSubmit={handleCreate}>
        <Input
          aria-label="Knowledge base name"
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
          placeholder="Knowledge base name"
          required
        />
        <Input
          aria-label="Knowledge base slug"
          value={slug}
          onChange={(event) => setSlug(event.target.value)}
          placeholder="knowledge-base-slug"
          required
        />
        <Button type="submit" disabled={createKnowledgeBase.isPending}>
          {createKnowledgeBase.isPending
            ? "Creating..."
            : "Create knowledge base"}
        </Button>
      </form>
      {createKnowledgeBase.error ? (
        <div className="text-muted-foreground">
          Unable to create knowledge base.
        </div>
      ) : null}
      {knowledgeBases.length === 0 ? (
        <div className="text-muted-foreground">No knowledge bases found</div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {knowledgeBases.map((kb) => (
            <button
              key={kb.id}
              type="button"
              onClick={() => onSelect?.(kb.id)}
              className="w-full rounded-lg border p-4 text-left"
            >
              <h3 className="type-section-title font-medium">
                {kb.display_name}
              </h3>
              <p className="text-muted-foreground type-body">{kb.slug}</p>
              <div className="mt-2">
                <span className="text-muted-foreground type-body">
                  {kb.visibility}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
