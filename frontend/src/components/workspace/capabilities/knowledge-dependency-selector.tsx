"use client";

import { useEffect, useState } from "react";

import { listKnowledgeRevisions } from "@/core/library/api";
import type { KnowledgeRevision } from "@/core/library/api";

export interface KnowledgeDependencyOption {
  resource_id: string;
  dependency_mode?: "live" | "pinned";
  revision_id?: string | null;
  required?: boolean;
  purpose?: string | null;
}

export interface KnowledgeDependencyKnowledgeBase {
  id: string;
  slug: string;
  display_name: string;
}

type PublishedRevisionsByKnowledgeBase = Record<string, KnowledgeRevision[]>;

export function KnowledgeDependencySelector({
  knowledgeBases,
  dependencies,
  onChange,
  loadError,
  onRevisionsLoadError,
}: {
  knowledgeBases: KnowledgeDependencyKnowledgeBase[];
  dependencies: KnowledgeDependencyOption[];
  onChange: (next: KnowledgeDependencyOption[]) => void;
  loadError?: boolean;
  onRevisionsLoadError?: (failed: boolean) => void;
}) {
  const [publishedRevisions, setPublishedRevisions] =
    useState<PublishedRevisionsByKnowledgeBase>({});
  const [revisionsLoadFailed, setRevisionsLoadFailed] = useState(false);

  useEffect(() => {
    if (knowledgeBases.length === 0) {
      setPublishedRevisions({});
      onRevisionsLoadError?.(false);
      return;
    }
    let cancelled = false;
    void Promise.all(
      knowledgeBases.map(async (knowledgeBase) => {
        const revisions = await listKnowledgeRevisions(knowledgeBase.id);
        return [
          knowledgeBase.id,
          revisions.filter((revision) => revision.status === "published"),
        ] as const;
      }),
    )
      .then((entries) => {
        if (cancelled) return;
        setPublishedRevisions(Object.fromEntries(entries));
        setRevisionsLoadFailed(false);
        onRevisionsLoadError?.(false);
      })
      .catch(() => {
        if (cancelled) return;
        // A failed revision read must never look like "no published
        // revisions", so PINNED selection is blocked instead.
        setRevisionsLoadFailed(true);
        onRevisionsLoadError?.(true);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [knowledgeBases]);

  function toggle(knowledgeBaseId: string) {
    onChange(
      dependencies.some((item) => item.resource_id === knowledgeBaseId)
        ? dependencies.filter((item) => item.resource_id !== knowledgeBaseId)
        : [
            ...dependencies,
            {
              resource_id: knowledgeBaseId,
              dependency_mode: "live",
              revision_id: null,
              required: true,
              purpose: null,
            },
          ],
    );
  }

  function update(
    knowledgeBaseId: string,
    patch: Partial<KnowledgeDependencyOption>,
  ) {
    onChange(
      dependencies.map((item) =>
        item.resource_id === knowledgeBaseId ? { ...item, ...patch } : item,
      ),
    );
  }

  return (
    <div className="space-y-2">
      {loadError && (
        <div role="alert" className="text-destructive type-body">
          Knowledge dependencies could not be loaded. Reload before saving.
        </div>
      )}
      {knowledgeBases.length > 0 && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {knowledgeBases.map((knowledgeBase) => {
            const dependency = dependencies.find(
              (item) => item.resource_id === knowledgeBase.id,
            );
            const dependencyMode = dependency?.dependency_mode ?? "live";
            const revisions = publishedRevisions[knowledgeBase.id] ?? [];
            return (
              <div
                key={knowledgeBase.id}
                className="space-y-2 rounded-md border p-3"
              >
                <label className="flex cursor-pointer items-center gap-2">
                  <input
                    type="checkbox"
                    checked={dependency !== undefined}
                    onChange={() => toggle(knowledgeBase.id)}
                    className="h-4 w-4 rounded border-gray-300"
                  />
                  <span className="type-body truncate font-medium">
                    {knowledgeBase.display_name || knowledgeBase.slug}
                  </span>
                </label>
                {dependency && (
                  <div className="flex gap-2">
                    <select
                      value={dependencyMode}
                      onChange={(event) =>
                        update(knowledgeBase.id, {
                          dependency_mode: event.target.value as
                            | "live"
                            | "pinned",
                          revision_id:
                            event.target.value === "live"
                              ? null
                              : (dependency.revision_id ?? null),
                        })
                      }
                      className="type-compact h-8 rounded border px-2"
                      aria-label={`${knowledgeBase.slug} dependency mode`}
                    >
                      <option value="live">LIVE</option>
                      <option value="pinned">PINNED</option>
                    </select>
                    {dependencyMode === "pinned" && (
                      <select
                        value={dependency.revision_id ?? ""}
                        onChange={(event) =>
                          update(knowledgeBase.id, {
                            revision_id: event.target.value || null,
                          })
                        }
                        className="type-compact h-8 min-w-0 rounded border px-2"
                        aria-label={`${knowledgeBase.slug} published revision`}
                      >
                        <option value="">
                          {revisionsLoadFailed
                            ? "Revisions unavailable"
                            : "Select published revision"}
                        </option>
                        {revisions.map((revision) => (
                          <option key={revision.id} value={revision.id}>
                            v{revision.revision_no} ·{" "}
                            {revision.manifest_hash.slice(0, 8)}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                )}
                {dependencyMode === "pinned" &&
                  !revisionsLoadFailed &&
                  revisions.length === 0 && (
                    <div className="text-destructive type-body">
                      No published revisions available
                    </div>
                  )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
