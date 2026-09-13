import { extractError } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

export interface KnowledgeRevisionIntegrity {
  revision_id: string;
  revision_no: number;
  integrity_status: string | null;
  integrity_checked_at: string | null;
}

export interface KnowledgeReconciliationCheck {
  id: string;
  revision_id: string | null;
  trigger: string;
  outcome: string;
  findings: Array<Record<string, unknown>>;
  checked_by: string | null;
  checked_at: string | null;
  duration_ms: number | null;
}

export interface KnowledgeReconciliationState {
  knowledge_base_id: string;
  revisions: KnowledgeRevisionIntegrity[];
  checks: KnowledgeReconciliationCheck[];
}

export interface KnowledgeReconciliationSummary {
  knowledge_base_id: string;
  revision_id: string | null;
  revision_no: number | null;
  outcome: string;
  check_id: string;
  findings: Array<Record<string, unknown>>;
}

export async function runKnowledgeReconciliation(
  knowledgeBaseId?: string,
): Promise<KnowledgeReconciliationSummary[]> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/admin/knowledge/reconciliation/run`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ knowledge_base_id: knowledgeBaseId ?? null }),
    },
  );
  if (!res.ok) await extractError(res, "Failed to run reconciliation");
  const data = (await res.json()) as {
    items: KnowledgeReconciliationSummary[];
  };
  return data.items;
}

export async function getKnowledgeReconciliation(
  knowledgeBaseId: string,
): Promise<KnowledgeReconciliationState> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/admin/knowledge/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/reconciliation`,
  );
  if (!res.ok) await extractError(res, "Failed to load reconciliation state");
  return (await res.json()) as KnowledgeReconciliationState;
}
