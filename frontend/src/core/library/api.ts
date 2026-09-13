import { extractError } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

export interface KnowledgeBase {
  id: string;
  type: "knowledge_base";
  slug: string;
  display_name: string;
  visibility: "private" | "department" | "public";
  can_modify: boolean;
}

export interface KnowledgeDocument {
  id: string;
  resource_id: string;
  name: string;
  size: number;
  mime_type: string;
  content_hash: string;
  source: "upload";
  status:
    | "uploaded"
    | "processing"
    | "ready"
    | "failed"
    | "deleting"
    | "delete_failed"
    | "deleted";
  failure_code?: string | null;
  failure_message?: string | null;
  ingestion_attempt?: number;
  can_modify?: boolean;
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export interface CreateKnowledgeBaseRequest {
  slug: string;
  displayName: string;
}

export type KnowledgeRevisionStatus =
  | "draft"
  | "indexing"
  | "ready"
  | "published"
  | "failed"
  | "superseded"
  | "archived";

export interface KnowledgeRevision {
  id: string;
  resource_id: string;
  revision_no: number;
  status: KnowledgeRevisionStatus;
  manifest_hash: string;
  document_count: number;
  failure_code?: string | null;
  failure_message?: string | null;
  created_at: string | null;
  published_at: string | null;
}

export interface KnowledgeRevisionDocument {
  document_id: string;
  content_hash: string;
  filename: string;
  size_bytes: number;
  mime_type: string;
  metadata: Record<string, unknown>;
}

export interface KnowledgeRevisionDetail extends KnowledgeRevision {
  documents: KnowledgeRevisionDocument[];
}

export async function listKnowledgeRevisions(
  resourceId: string,
): Promise<KnowledgeRevision[]> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resourceId)}/knowledge-revisions`,
  );
  if (!res.ok) await extractError(res, "Failed to load revisions");
  const data = (await res.json()) as { items: KnowledgeRevision[] };
  return data.items;
}

export async function getKnowledgeRevision(
  resourceId: string,
  revisionId: string,
): Promise<KnowledgeRevisionDetail> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resourceId)}/knowledge-revisions/${encodeURIComponent(revisionId)}`,
  );
  if (!res.ok) await extractError(res, "Failed to load revision");
  return (await res.json()) as KnowledgeRevisionDetail;
}

export async function createKnowledgeRevision(
  resourceId: string,
): Promise<KnowledgeRevision> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resourceId)}/knowledge-revisions`,
    { method: "POST" },
  );
  if (!res.ok) await extractError(res, "Failed to create revision");
  return (await res.json()) as KnowledgeRevision;
}

export async function listKnowledgeBases(): Promise<KnowledgeBase[]> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources?type=knowledge_base&limit=200`,
  );
  if (!res.ok) await extractError(res, "Failed to load KnowledgeBases");
  const data = (await res.json()) as { items: KnowledgeBase[] };
  return data.items;
}

export async function createKnowledgeBase(
  request: CreateKnowledgeBaseRequest,
): Promise<KnowledgeBase> {
  const res = await fetch(`${getBackendBaseURL()}/api/resources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      type: "knowledge_base",
      slug: request.slug,
      display_name: request.displayName,
      storage_kind: "database",
    }),
  });
  if (!res.ok) await extractError(res, "Failed to create KnowledgeBase");
  return (await res.json()) as KnowledgeBase;
}

export async function listKnowledgeDocuments(
  resourceId: string,
): Promise<KnowledgeDocument[]> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resourceId)}/documents`,
  );
  if (!res.ok) await extractError(res, "Failed to load documents");
  const data = (await res.json()) as { items: KnowledgeDocument[] };
  return data.items;
}

export async function uploadKnowledgeDocument(
  resourceId: string,
  file: File,
): Promise<KnowledgeDocument> {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resourceId)}/documents`,
    { method: "POST", body },
  );
  if (!res.ok) await extractError(res, "Failed to upload document");
  return (await res.json()) as KnowledgeDocument;
}

async function updateKnowledgeDocument(
  resourceId: string,
  documentId: string,
  action: "retry" | "rebuild-index",
): Promise<KnowledgeDocument> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resourceId)}/documents/${encodeURIComponent(documentId)}/${action}`,
    { method: "POST" },
  );
  if (!res.ok) await extractError(res, "Failed to update document");
  return (await res.json()) as KnowledgeDocument;
}

export const retryKnowledgeDocument = (
  resourceId: string,
  documentId: string,
) => updateKnowledgeDocument(resourceId, documentId, "retry");

export const rebuildKnowledgeDocumentIndex = (
  resourceId: string,
  documentId: string,
) => updateKnowledgeDocument(resourceId, documentId, "rebuild-index");

export async function deleteKnowledgeDocument(
  resourceId: string,
  documentId: string,
): Promise<KnowledgeDocument> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resourceId)}/documents/${encodeURIComponent(documentId)}`,
    { method: "DELETE" },
  );
  if (!res.ok) await extractError(res, "Failed to delete document");
  return (await res.json()) as KnowledgeDocument;
}
