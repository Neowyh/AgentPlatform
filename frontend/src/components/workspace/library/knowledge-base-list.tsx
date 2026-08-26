"use client";

import { useKnowledgeBases } from "@/core/library";

export function KnowledgeBaseList() {
  const { knowledgeBases, isLoading } = useKnowledgeBases();

  if (isLoading) {
    return <div className="text-muted-foreground">Loading...</div>;
  }

  if (!knowledgeBases || knowledgeBases.length === 0) {
    return (
      <div className="text-muted-foreground">No knowledge bases found</div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {knowledgeBases.map((kb) => (
        <div key={kb.id} className="rounded-lg border p-4">
          <h3 className="font-medium">{kb.name}</h3>
          <p className="text-muted-foreground text-sm">{kb.description}</p>
          <div className="mt-2">
            <span className="text-muted-foreground text-xs">
              {kb.document_count} documents
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
