"use client";

interface KnowledgeRevisionInfo {
  revision_id?: string | null;
  revision_no?: number | null;
  manifest_hash?: string | null;
}

function extractRevisions(
  snapshot?: Record<string, unknown>,
): Record<string, KnowledgeRevisionInfo> {
  if (!snapshot) return {};
  const evidence = snapshot.run_evidence;
  if (typeof evidence !== "object" || evidence === null) return {};
  const scope = (evidence as Record<string, unknown>).knowledge_scope;
  if (typeof scope !== "object" || scope === null) return {};
  const revisions = (scope as Record<string, unknown>).revisions;
  if (typeof revisions !== "object" || revisions === null) return {};
  return revisions as Record<string, KnowledgeRevisionInfo>;
}

export function KnowledgeSnapshotCard({
  snapshot,
}: {
  snapshot?: Record<string, unknown>;
}) {
  const revisions = extractRevisions(snapshot);
  const knowledgeBaseIds = Object.keys(revisions);
  if (knowledgeBaseIds.length === 0) return null;

  return (
    <div className="rounded-lg border p-4" data-testid="knowledge-snapshot">
      <h2 className="type-section-title font-medium">
        Knowledge used by this run
      </h2>
      <ul className="mt-2 space-y-1">
        {knowledgeBaseIds.map((knowledgeBaseId) => {
          const revision = revisions[knowledgeBaseId] ?? {};
          return (
            <li
              key={knowledgeBaseId}
              className="text-muted-foreground type-body"
            >
              KB {knowledgeBaseId.slice(0, 8)} · v{revision.revision_no ?? "?"}{" "}
              · manifest {(revision.manifest_hash ?? "").slice(0, 12)}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
