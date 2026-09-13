"use client";

import type { ChangeEvent } from "react";

import {
  useDocuments,
  useRebuildKnowledgeDocumentIndex,
  useRetryKnowledgeDocument,
  useUploadKnowledgeDocument,
} from "@/core/library";

export function DocumentList({
  knowledgeBaseId,
}: {
  knowledgeBaseId?: string;
}) {
  const { documents, isLoading, error } = useDocuments(knowledgeBaseId);
  const upload = useUploadKnowledgeDocument(knowledgeBaseId ?? "");
  const retry = useRetryKnowledgeDocument(knowledgeBaseId ?? "");
  const rebuild = useRebuildKnowledgeDocumentIndex(knowledgeBaseId ?? "");

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
        <UploadControl pending={upload.isPending} onChange={handleUpload} />
        {upload.error ? (
          <div className="text-destructive">Unable to upload document.</div>
        ) : null}
        <div className="text-muted-foreground">No documents found</div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <UploadControl pending={upload.isPending} onChange={handleUpload} />
      {upload.error ? (
        <div className="text-destructive">Unable to upload document.</div>
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
              {doc.can_modify && doc.status === "failed" ? (
                <button
                  type="button"
                  onClick={() => void retry.mutateAsync(doc.id)}
                >
                  Retry
                </button>
              ) : null}
              {doc.can_modify && doc.status === "ready" ? (
                <button
                  type="button"
                  onClick={() => void rebuild.mutateAsync(doc.id)}
                >
                  Rebuild index
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
        disabled={pending}
        onChange={onChange}
      />
    </label>
  );
}
