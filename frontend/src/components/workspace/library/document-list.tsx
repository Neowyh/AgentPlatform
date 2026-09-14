"use client";

import type { ChangeEvent } from "react";

import { useKnowledgeCapability } from "@/core/features";
import {
  useDocuments,
  useRebuildKnowledgeDocumentIndex,
  useDeleteKnowledgeDocument,
  useRetryKnowledgeDocument,
  useUploadKnowledgeDocument,
  useKnowledgeBases,
  useEditKnowledgeDocument,
} from "@/core/library";
import type { KnowledgeDocument } from "@/core/library";

export function DocumentList({
  knowledgeBaseId,
}: {
  knowledgeBaseId?: string;
}) {
  const { documents, isLoading, error } = useDocuments(knowledgeBaseId);
  const { knowledgeBases } = useKnowledgeBases();
  const capability = useKnowledgeCapability();
  const canModify =
    knowledgeBases.find((base) => base.id === knowledgeBaseId)?.can_modify ??
    false;
  const upload = useUploadKnowledgeDocument(knowledgeBaseId ?? "");
  const retry = useRetryKnowledgeDocument(knowledgeBaseId ?? "");
  const rebuild = useRebuildKnowledgeDocumentIndex(knowledgeBaseId ?? "");
  const remove = useDeleteKnowledgeDocument(knowledgeBaseId ?? "");
  const edit = useEditKnowledgeDocument(knowledgeBaseId ?? "");

  async function handleEdit(doc: KnowledgeDocument) {
    const title = window.prompt("Document title", doc.name);
    if (title === null) return;
    const rawMetadata = window.prompt(
      "Metadata JSON",
      JSON.stringify(doc.metadata ?? {}, null, 2),
    );
    if (rawMetadata === null) return;
    let metadata: Record<string, unknown>;
    try {
      const parsed: unknown = JSON.parse(rawMetadata);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Metadata must be an object");
      }
      metadata = parsed as Record<string, unknown>;
    } catch {
      window.alert("Metadata must be valid JSON object");
      return;
    }
    await edit.mutateAsync({ documentId: doc.id, update: { title, metadata } });
  }

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !knowledgeBaseId) return;
    await upload.mutateAsync(file);
  }

  if (!knowledgeBaseId) {
    return (
      <div className="text-muted-foreground">
        Select a knowledge base to view documents
      </div>
    );
  }

  if (isLoading) {
    return <div className="text-muted-foreground">Loading...</div>;
  }

  if (error) {
    return (
      <div className="text-muted-foreground">Unable to load documents.</div>
    );
  }

  if (!documents || documents.length === 0) {
    return (
      <div className="space-y-3">
        {!capability.isLoading &&
        (!capability.enabled || !capability.workerRunning) ? (
          <div className="text-muted-foreground" role="status">
            Knowledge processing is currently unavailable.
          </div>
        ) : null}
        {canModify && capability.enabled && capability.workerRunning ? (
          <div className="space-y-1">
            <UploadControl pending={upload.isPending} onChange={handleUpload} />
            {capability.maxFileSize > 0 ? (
              <p className="text-muted-foreground type-body">
                Max {Math.round(capability.maxFileSize / (1024 * 1024))} MB;
                formats: {capability.supportedExtensions.join(", ")}
              </p>
            ) : null}
          </div>
        ) : null}
        {upload.error ? (
          <div role="alert" className="text-destructive">
            Unable to upload document.
          </div>
        ) : null}
        <div className="text-muted-foreground">No documents found</div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {!capability.isLoading &&
      (!capability.enabled || !capability.workerRunning) ? (
        <div className="text-muted-foreground" role="status">
          Knowledge processing is currently unavailable.
        </div>
      ) : null}
      {canModify && capability.enabled && capability.workerRunning ? (
        <div className="space-y-1">
          <UploadControl pending={upload.isPending} onChange={handleUpload} />
          {capability.maxFileSize > 0 ? (
            <p className="text-muted-foreground type-body">
              Max {Math.round(capability.maxFileSize / (1024 * 1024))} MB;
              formats: {capability.supportedExtensions.join(", ")}
            </p>
          ) : null}
        </div>
      ) : null}
      {upload.error ? (
        <div role="alert" className="text-destructive">
          Unable to upload document.
        </div>
      ) : null}
      {retry.error || rebuild.error || remove.error ? (
        <div role="alert" className="text-destructive">
          Unable to update document.
        </div>
      ) : null}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {documents.map((doc) => (
          <div key={doc.id} className="rounded-lg border p-4">
            <h3 className="type-section-title font-medium">{doc.name}</h3>
            <p className="text-muted-foreground type-body">{doc.id}</p>
            <div className="mt-2 flex items-center justify-between">
              <span
                className={`type-body rounded-full px-2 py-1 ${
                  doc.status === "ready"
                    ? "bg-green-100 text-green-800"
                    : "bg-yellow-100 text-yellow-800"
                }`}
              >
                {doc.status}
              </span>
              {canModify && doc.can_modify && doc.status === "failed" ? (
                <button
                  type="button"
                  onClick={() => void retry.mutateAsync(doc.id)}
                >
                  Retry
                </button>
              ) : null}
              {canModify && doc.can_modify && doc.status === "ready" ? (
                <button
                  type="button"
                  onClick={() => void rebuild.mutateAsync(doc.id)}
                >
                  Rebuild index
                </button>
              ) : null}
              {canModify && doc.can_modify && doc.status !== "deleted" ? (
                <button
                  type="button"
                  disabled={remove.isPending}
                  aria-busy={remove.isPending}
                  onClick={() => void remove.mutateAsync(doc.id)}
                >
                  {remove.isPending ? "Deleting..." : "Delete"}
                </button>
              ) : null}
              {canModify && doc.can_modify && doc.status !== "deleted" ? (
                <button
                  type="button"
                  disabled={edit.isPending}
                  onClick={() => void handleEdit(doc)}
                >
                  Edit
                </button>
              ) : null}
              <span className="text-muted-foreground type-body">
                {doc.created_at ?? ""}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function UploadControl({
  pending,
  onChange,
}: {
  pending: boolean;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <label className="bg-primary text-primary-foreground inline-flex cursor-pointer rounded-md px-4 py-2">
      {pending ? "Uploading..." : "Upload document"}
      <input
        className="sr-only"
        type="file"
        data-knowledge-upload="true"
        disabled={pending}
        onChange={onChange}
      />
    </label>
  );
}
