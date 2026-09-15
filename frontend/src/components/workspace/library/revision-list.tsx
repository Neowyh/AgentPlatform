"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/core/i18n/hooks";
import {
  useCreateKnowledgeRevision,
  useKnowledgeRevision,
  useKnowledgeRevisions,
  usePublishKnowledgeRevision,
} from "@/core/library";

const STATUS_BADGE_CLASSES: Record<string, string> = {
  published: "bg-green-100 text-green-800",
  draft: "bg-blue-100 text-blue-800",
  indexing: "bg-yellow-100 text-yellow-800",
  ready: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  superseded: "bg-gray-100 text-gray-600",
  archived: "bg-gray-100 text-gray-600",
};

// Reconciliation statuses that mean confirmed drift (mirrors the backend
// knowledge.integrity.UNUSABLE_INTEGRITY set).
const UNUSABLE_INTEGRITY_STATUSES = new Set([
  "drifted",
  "missing_provider_dataset",
]);

export function RevisionList({
  knowledgeBaseId,
  canModify,
}: {
  knowledgeBaseId?: string;
  canModify?: boolean;
}) {
  const { t } = useI18n();
  const i = t.library.revisionList;
  const { revisions, isLoading, error } =
    useKnowledgeRevisions(knowledgeBaseId);
  const create = useCreateKnowledgeRevision(knowledgeBaseId ?? "");
  const publish = usePublishKnowledgeRevision(knowledgeBaseId ?? "");
  const [expandedId, setExpandedId] = useState<string>();

  if (!knowledgeBaseId) {
    return <div className="text-muted-foreground">{i.selectKnowledgeBase}</div>;
  }

  if (isLoading) {
    return <div className="text-muted-foreground">{i.loading}</div>;
  }

  if (error) {
    return (
      <div role="alert" className="text-muted-foreground">
        {i.loadFailed}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {canModify ? (
        <div className="space-y-2">
          <Button
            type="button"
            disabled={create.isPending}
            aria-busy={create.isPending}
            onClick={() => void create.mutateAsync()}
          >
            {create.isPending ? i.creating : i.createCandidate}
          </Button>
          {create.error ? (
            <div role="alert" className="text-destructive">
              {i.createFailed}
            </div>
          ) : null}
        </div>
      ) : null}
      {publish.error ? (
        <div role="alert" className="text-destructive">
          {i.publishFailed}
        </div>
      ) : null}
      {revisions.length === 0 ? (
        <div className="text-muted-foreground">{i.empty}</div>
      ) : (
        <div className="space-y-3">
          {revisions.map((revision) => (
            <div key={revision.id} className="rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <h3 className="type-section-title font-medium">
                  v{revision.revision_no}
                </h3>
                <span
                  className={`type-body rounded-full px-2 py-1 ${
                    STATUS_BADGE_CLASSES[revision.status] ??
                    "bg-yellow-100 text-yellow-800"
                  }`}
                >
                  {revision.status === "indexing" && canModify
                    ? i.publishingStatus
                    : revision.status}
                </span>
              </div>
              <p className="text-muted-foreground type-body">
                {i.documentsAndManifest(
                  revision.document_count,
                  revision.manifest_hash.slice(0, 12),
                )}
              </p>
              {revision.integrity_status &&
              UNUSABLE_INTEGRITY_STATUSES.has(revision.integrity_status) ? (
                <div role="alert" className="text-destructive type-body">
                  {i.integrityFlagged(revision.integrity_status)}
                </div>
              ) : null}
              {revision.failure_message ? (
                <div role="alert" className="text-destructive type-body">
                  {revision.failure_message}
                </div>
              ) : null}
              <div className="mt-2 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    aria-expanded={expandedId === revision.id}
                    onClick={() =>
                      setExpandedId(
                        expandedId === revision.id ? undefined : revision.id,
                      )
                    }
                  >
                    {expandedId === revision.id ? i.hideDetails : i.viewDetails}
                  </button>
                  {canModify &&
                  (revision.status === "draft" ||
                    revision.status === "failed") ? (
                    <button
                      type="button"
                      aria-label={i.publishAria(revision.revision_no)}
                      disabled={publish.isPending}
                      aria-busy={publish.isPending}
                      onClick={() => void publish.mutateAsync(revision.id)}
                    >
                      {publish.isPending ? i.publishingAction : i.publish}
                    </button>
                  ) : null}
                </div>
                <span className="text-muted-foreground type-body">
                  {revision.published_at ?? revision.created_at ?? ""}
                </span>
              </div>
              {expandedId === revision.id ? (
                <RevisionDetail
                  knowledgeBaseId={knowledgeBaseId}
                  revisionId={revision.id}
                />
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function RevisionDetail({
  knowledgeBaseId,
  revisionId,
}: {
  knowledgeBaseId: string;
  revisionId: string;
}) {
  const { t } = useI18n();
  const { data, isLoading, error } = useKnowledgeRevision(
    knowledgeBaseId,
    revisionId,
  );

  if (isLoading) {
    return (
      <div className="text-muted-foreground mt-3">
        {t.library.revisionList.loading}
      </div>
    );
  }
  if (error || !data) {
    return (
      <div role="alert" className="text-muted-foreground mt-3">
        {t.library.revisionList.loadFailed}
      </div>
    );
  }
  return (
    <ul className="mt-3 space-y-2">
      {data.documents.map((document) => (
        <li
          key={document.document_id}
          className="text-muted-foreground type-body"
        >
          {document.filename} · {document.content_hash.slice(0, 12)} ·{" "}
          {document.size_bytes} bytes
        </li>
      ))}
    </ul>
  );
}
