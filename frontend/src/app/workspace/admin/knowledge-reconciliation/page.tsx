"use client";

import { ArrowLeftIcon, PlayIcon } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/core/i18n/hooks";
import type { KnowledgeReconciliationCheck } from "@/core/knowledge-admin/api";
import {
  useKnowledgeReconciliation,
  useRunKnowledgeReconciliation,
} from "@/core/knowledge-admin/hooks";

const OUTCOME_BADGE_CLASSES: Record<string, string> = {
  HEALTHY: "bg-green-100 text-green-800",
  UNVERIFIED: "bg-yellow-100 text-yellow-800",
  MISSING_DOCUMENT: "bg-red-100 text-red-800",
  HASH_MISMATCH: "bg-red-100 text-red-800",
  MISSING_PROVIDER_DATASET: "bg-red-100 text-red-800",
  ORPHAN_PROVIDER_RESOURCE: "bg-purple-100 text-purple-800",
};

export default function KnowledgeReconciliationPage() {
  const searchParams = useSearchParams();
  const knowledgeBaseId = searchParams.get("knowledge_base_id") ?? undefined;
  const { t } = useI18n();
  const i = t.admin.knowledgeReconciliation;
  const {
    data: state,
    isLoading,
    isError,
  } = useKnowledgeReconciliation(knowledgeBaseId);
  const runReconciliation = useRunKnowledgeReconciliation(knowledgeBaseId);

  function handleRun() {
    runReconciliation.mutate(undefined, {
      onSuccess: (items) => {
        if (items.length === 0) {
          toast.success(i.noPublished);
        } else {
          toast.success(i.recorded(items.length));
        }
      },
      onError: (error) => {
        toast.error(error instanceof Error ? error.message : String(error));
      },
    });
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
            <h1 className="type-page-title font-semibold">{i.title}</h1>
            <p className="text-muted-foreground type-body">{i.description}</p>
          </div>
        </div>
        <Button onClick={handleRun} disabled={runReconciliation.isPending}>
          <PlayIcon className="mr-2 h-4 w-4" />
          {runReconciliation.isPending ? i.running : i.run}
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-4xl space-y-4">
          {isLoading ? (
            <p className="text-muted-foreground type-body">{i.loading}</p>
          ) : isError ? (
            <p className="text-destructive type-body">{i.loadFailed}</p>
          ) : !state ? (
            <p className="text-muted-foreground type-body">
              {i.emptyHint(knowledgeBaseId ?? "all knowledge bases")}
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
                      <span>
                        v{revision.revision_no} ·{" "}
                        {revision.status ?? "published"}
                      </span>
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
                      {revision.integrity_status ?? i.unknown}
                    </span>
                  </div>
                  <p className="text-muted-foreground type-body">
                    {i.lastChecked(revision.integrity_checked_at ?? "never")}
                  </p>
                </div>
              ))}
              <Card>
                <CardHeader>
                  <CardTitle>{i.checkHistory}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {state.checks.length === 0 ? (
                    <p className="text-muted-foreground type-body">
                      {i.noChecks}
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
