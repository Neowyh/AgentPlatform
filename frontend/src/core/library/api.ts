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
  status: "uploaded" | "processing" | "ready" | "failed";
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export interface CreateKnowledgeBaseRequest {
  slug: string;
  displayName: string;
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
