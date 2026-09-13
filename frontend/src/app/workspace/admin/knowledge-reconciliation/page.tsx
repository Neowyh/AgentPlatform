"use client";

import { ArrowLeftIcon, PlayIcon } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getKnowledgeReconciliation,
  runKnowledgeReconciliation,
} from "@/core/knowledge-admin/api";
import type {
  KnowledgeReconciliationCheck,
  KnowledgeReconciliationState,
} from "@/core/knowledge-admin/api";

const OUTCOME_BADGE_CLASSES: Record<string, string> = {
  HEALTHY: "bg-green-100 text-green-800",
  UNVERIFIED: "bg-yellow-100 text-yellow-800",
  MISSING_DOCUMENT: "bg-red-100 text-red-800",
  HASH_MISMATCH: "bg-red-100 text-red-800",
  MISSING_PROVIDER_DATASET: "bg-red-100 text-red-800",
  ORPHAN_PROVIDER_RESOURCE: "bg-purple-100 text-purple-800",
};

export default function KnowledgeReconciliationPage() {
  const { knowledge_base_id } = useParams<{ knowledge_base_id: string }>();
  const [state, setState] = useState<KnowledgeReconciliationState | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  async function handleRun() {
    setIsRunning(true);
    try {
      const items = await runKnowledgeReconciliation(knowledge_base_id);
      if (items.length === 0) {
        toast.success("Reconciliation found no published revisions to check");
      } else {
        toast.success(`Reconciliation recorded ${items.length} check(s)`);
      }
      setState(await getKnowledgeReconciliation(knowledge_base_id));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <div className="flex size-full flex-col">
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon-sm" asChild>
            <Link href="/workspace/admin">
              <ArrowLeftIcon className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="type-page-title font-semibold">
              Knowledge reconciliation
            </h1>
            <p className="text-muted-foreground type-body">
              Read-only drift checks for published knowledge revisions
            </p>
          </div>
        </div>
        <Button onClick={() => void handleRun()} disabled={isRunning}>
          <PlayIcon className="mr-2 h-4 w-4" />
          {isRunning ? "Running..." : "Run reconciliation"}
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-4xl space-y-4">
          {state === null ? (
            <p className="text-muted-foreground type-body">
              Run a reconciliation to see the latest drift findings for KB{" "}
              {knowledge_base_id}.
            </p>
          ) : (
            <>
              {state.revisions.map((revision) => (
                <div
                  key={revision.revision_id}
                  className="rounded-lg border p-4"
                >
                  <div className="flex items-center justify-between">
                    <span className="type-body font-medium">
                      v{revision.revision_no}
                    </span>
                    <span
                      className={`type-body rounded-full px-2 py-1 ${
                        revision.integrity_status === "healthy"
                          ? "bg-green-100 text-green-800"
                          : revision.integrity_status === "unverified"
                            ? "bg-yellow-100 text-yellow-800"
                            : "bg-red-100 text-red-800"
                      }`}
                    >
                      {revision.integrity_status ?? "unknown"}
                    </span>
                  </div>
                  <p className="text-muted-foreground type-body">
                    Last checked: {revision.integrity_checked_at ?? "never"}
                  </p>
                </div>
              ))}
              <Card>
                <CardHeader>
                  <CardTitle>Check history</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {state.checks.length === 0 ? (
                    <p className="text-muted-foreground type-body">
                      No reconciliation checks recorded yet
                    </p>
                  ) : (
                    state.checks.map((check: KnowledgeReconciliationCheck) => (
                      <div
                        key={check.id}
                        className="type-body rounded-md border p-3"
                      >
                        <div className="flex items-center justify-between">
                          <span
                            className={`rounded-full px-2 py-1 ${
                              OUTCOME_BADGE_CLASSES[check.outcome] ??
                              "bg-yellow-100 text-yellow-800"
                            }`}
                          >
                            {check.outcome}
                          </span>
                          <span className="text-muted-foreground">
                            {check.trigger} · {check.checked_at ?? ""}
                          </span>
                        </div>
                        {check.revision_id ? (
                          <p className="text-muted-foreground mt-1">
                            revision {check.revision_id.slice(0, 8)}
                          </p>
                        ) : null}
                        {check.findings.length > 0 ? (
                          <ul className="text-muted-foreground mt-1 list-inside list-disc">
                            {check.findings.map((finding, index) => {
                              const parts = [
                                typeof finding.kind === "string"
                                  ? finding.kind
                                  : "finding",
                                typeof finding.verdict === "string"
                                  ? finding.verdict
                                  : null,
                                typeof finding.provider_document_id === "string"
                                  ? finding.provider_document_id
                                  : null,
                              ].filter(Boolean);
                              return <li key={index}>{parts.join(" · ")}</li>;
                            })}
                          </ul>
                        ) : null}
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
