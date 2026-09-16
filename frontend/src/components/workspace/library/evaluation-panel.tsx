"use client";

import { useState } from "react";

import {
  useKnowledgeEvaluation,
  useKnowledgeEvaluations,
  useKnowledgeRevisions,
  useKnowledgeEvalCases,
  useRetryKnowledgeEvaluation,
  useStartKnowledgeEvaluation,
  useKnowledgeEvaluationComparison,
  useStartKnowledgeEvaluationComparison,
} from "@/core/library";

export function EvaluationPanel({
  knowledgeBaseId,
  canModify,
}: {
  knowledgeBaseId?: string;
  canModify?: boolean;
}) {
  const { revisions } = useKnowledgeRevisions(knowledgeBaseId);
  const { evalCases } = useKnowledgeEvalCases(knowledgeBaseId);
  const { evaluations } = useKnowledgeEvaluations(knowledgeBaseId);
  const [revisionId, setRevisionId] = useState("");
  const [rightRevisionId, setRightRevisionId] = useState("");
  const [profileId, setProfileId] = useState<"frozen" | "configured">("frozen");
  const [rightProfileId, setRightProfileId] = useState<"frozen" | "configured">(
    "configured",
  );
  const [caseSet, setCaseSet] = useState<"all" | "selected">("all");
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([]);
  const [topK, setTopK] = useState(8);
  const [selectedId, setSelectedId] = useState<string>();
  const start = useStartKnowledgeEvaluation(knowledgeBaseId ?? "");
  const retry = useRetryKnowledgeEvaluation(knowledgeBaseId ?? "");
  const detail = useKnowledgeEvaluation(knowledgeBaseId, selectedId);
  const [comparisonId, setComparisonId] = useState<string>();
  const comparison = useKnowledgeEvaluationComparison(
    knowledgeBaseId,
    comparisonId,
  );
  const compare = useStartKnowledgeEvaluationComparison(knowledgeBaseId ?? "");
  const published = revisions.filter((revision) =>
    ["published", "superseded"].includes(revision.status),
  );
  const comparisonRevisions = revisions.filter((revision) =>
    ["published", "superseded", "ready"].includes(revision.status),
  );

  if (!knowledgeBaseId)
    return (
      <p className="text-muted-foreground p-4">
        Select a knowledge base to evaluate.
      </p>
    );
  return (
    <div className="space-y-4 p-4">
      <div className="rounded-lg border p-4">
        <h2 className="font-semibold">Single-profile evaluation</h2>
        <p className="type-supporting text-muted-foreground">
          Run the frozen case set against a published revision. Results are
          durable and can be inspected after refresh.
        </p>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="type-supporting">
            Revision
            <select
              className="mt-1 block rounded border p-2"
              value={revisionId}
              onChange={(event) => setRevisionId(event.target.value)}
            >
              <option value="">Select revision</option>
              {published.map((revision) => (
                <option key={revision.id} value={revision.id}>
                  v{revision.revision_no} · {revision.status}
                </option>
              ))}
            </select>
          </label>
          <label className="type-supporting">
            K
            <input
              className="mt-1 block w-20 rounded border p-2"
              type="number"
              min={1}
              max={20}
              value={topK}
              onChange={(event) => setTopK(Number(event.target.value))}
            />
          </label>
          <label className="type-supporting">
            Profile
            <select
              className="mt-1 block rounded border p-2"
              value={profileId}
              onChange={(event) =>
                setProfileId(event.target.value as "frozen" | "configured")
              }
            >
              <option value="frozen">Frozen</option>
              <option value="configured">Configured</option>
            </select>
          </label>
          <label className="type-supporting">
            Case set
            <select
              className="mt-1 block rounded border p-2"
              value={caseSet}
              onChange={(event) =>
                setCaseSet(event.target.value as "all" | "selected")
              }
            >
              <option value="all">All cases ({evalCases.length})</option>
              <option value="selected">
                Selected cases ({selectedCaseIds.length})
              </option>
            </select>
          </label>
          <button
            type="button"
            className="bg-primary text-primary-foreground rounded px-3 py-2 disabled:opacity-50"
            disabled={
              !canModify ||
              !revisionId ||
              evalCases.length === 0 ||
              (caseSet === "selected" && selectedCaseIds.length === 0) ||
              start.isPending
            }
            onClick={() =>
              void start.mutateAsync({
                revisionId,
                profileId,
                topK,
                ...(caseSet === "selected" ? { caseIds: selectedCaseIds } : {}),
              })
            }
          >
            {start.isPending
              ? "Starting…"
              : `Evaluate ${caseSet === "selected" ? selectedCaseIds.length : evalCases.length} cases`}
          </button>
        </div>
        {evalCases.length === 0 && (
          <p className="type-supporting text-muted-foreground mt-2">
            Create at least one evaluation case first.
          </p>
        )}
        {caseSet === "selected" && (
          <div className="type-supporting mt-2 space-y-1">
            {evalCases.map((item) => (
              <label key={item.id} className="block">
                <input
                  type="checkbox"
                  checked={selectedCaseIds.includes(item.id)}
                  onChange={(event) =>
                    setSelectedCaseIds((current) =>
                      event.target.checked
                        ? [...current, item.id]
                        : current.filter((id) => id !== item.id),
                    )
                  }
                />{" "}
                {item.question}
              </label>
            ))}
          </div>
        )}
      </div>
      <div className="rounded-lg border p-4">
        <h2 className="font-semibold">A/B comparison</h2>
        <p className="type-supporting text-muted-foreground">
          Both sides use the same frozen cases, K, and metric version.
        </p>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="type-supporting">
            Side A revision
            <select
              aria-label="Side A revision"
              className="mt-1 block rounded border p-2"
              value={revisionId}
              onChange={(event) => setRevisionId(event.target.value)}
            >
              <option value="">Select revision</option>
              {comparisonRevisions.map((revision) => (
                <option key={revision.id} value={revision.id}>
                  v{revision.revision_no} · {revision.status}
                </option>
              ))}
            </select>
          </label>
          <label className="type-supporting">
            Side A profile
            <select
              aria-label="Side A profile"
              className="mt-1 block rounded border p-2"
              value={profileId}
              onChange={(event) =>
                setProfileId(event.target.value as "frozen" | "configured")
              }
            >
              <option value="frozen">Frozen</option>
              <option value="configured">Configured</option>
            </select>
          </label>
          <label className="type-supporting">
            Side B revision
            <select
              aria-label="Side B revision"
              className="mt-1 block rounded border p-2"
              value={rightRevisionId}
              onChange={(event) => setRightRevisionId(event.target.value)}
            >
              <option value="">Select revision</option>
              {comparisonRevisions.map((revision) => (
                <option key={revision.id} value={revision.id}>
                  v{revision.revision_no} · {revision.status}
                </option>
              ))}
            </select>
          </label>
          <label className="type-supporting">
            Side B profile
            <select
              aria-label="Side B profile"
              className="mt-1 block rounded border p-2"
              value={rightProfileId}
              onChange={(event) =>
                setRightProfileId(event.target.value as "frozen" | "configured")
              }
            >
              <option value="frozen">Frozen</option>
              <option value="configured">Configured</option>
            </select>
          </label>
          <button
            type="button"
            className="bg-primary text-primary-foreground rounded px-3 py-2 disabled:opacity-50"
            disabled={
              !canModify ||
              !revisionId ||
              !rightRevisionId ||
              evalCases.length === 0 ||
              compare.isPending
            }
            onClick={async () => {
              const result = await compare.mutateAsync({
                leftRevisionId: revisionId,
                leftProfileId: profileId,
                rightRevisionId,
                rightProfileId,
                topK,
              });
              setComparisonId(result.id);
            }}
          >
            Compare
          </button>
        </div>
        {comparison.data && (
          <div className="mt-4 space-y-2" aria-live="polite">
            {!comparison.data.comparison.eligible && (
              <p className="text-destructive">
                Comparison unavailable: {comparison.data.comparison.reason}
              </p>
            )}
            {comparison.data.comparison.eligible && (
              <>
                <p>
                  Recall@K Δ{" "}
                  {comparison.data.comparison.delta.recall_at_k?.toFixed(3) ??
                    "—"}
                  ; MRR@K Δ{" "}
                  {comparison.data.comparison.delta.mrr_at_k?.toFixed(3) ?? "—"}
                </p>
                {comparison.data.comparison.cases.map((item) => (
                  <div className="rounded border p-2" key={item.case_id}>
                    <span>
                      {item.case_id}: {item.outcome}
                    </span>
                    {item.left?.ranked_items?.[0] && (
                      <span className="type-supporting ml-2">
                        A:{" "}
                        {item.left.ranked_items[0].display_name ??
                          item.left.ranked_items[0].document_id}
                      </span>
                    )}
                    {item.right?.ranked_items?.[0] && (
                      <span className="type-supporting ml-2">
                        B:{" "}
                        {item.right.ranked_items[0].display_name ??
                          item.right.ranked_items[0].document_id}
                      </span>
                    )}
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>
      <div className="space-y-2">
        {evaluations.map((run) => (
          <button
            type="button"
            key={run.id}
            className={`w-full rounded border p-3 text-left ${selectedId === run.id ? "border-primary" : ""}`}
            onClick={() => setSelectedId(run.id)}
          >
            <div className="flex justify-between">
              <span>
                v{run.revision_no} · K{run.top_k}
              </span>
              <span>{run.status}</span>
            </div>
            <div className="type-supporting text-muted-foreground">
              {run.completed_cases}/{run.total_cases} cases · denominator{" "}
              {run.aggregate.denominator ?? "—"} · Recall@K{" "}
              {run.aggregate.recall_at_k == null
                ? "—"
                : run.aggregate.recall_at_k.toFixed(3)}
            </div>
          </button>
        ))}
      </div>
      {detail.data && (
        <div className="rounded-lg border p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-semibold">
              Evidence · {detail.data.id.slice(0, 8)}
            </h3>
            {(detail.data.status === "partial" ||
              detail.data.status === "failed") && (
              <button
                type="button"
                className="rounded border px-3 py-1"
                onClick={() => void retry.mutateAsync(detail.data.id)}
              >
                Retry
              </button>
            )}
          </div>
          <div className="space-y-3">
            {detail.data.results?.map((result) => (
              <div key={result.id} className="rounded border p-3">
                <div className="flex justify-between">
                  <span>{result.query}</span>
                  <span>{result.status}</span>
                </div>
                <div className="type-supporting text-muted-foreground">
                  Expected hit: {result.expected_hit ? "yes" : "no"} · Recall@K:{" "}
                  {result.recall_at_k ?? "—"} · MRR@K: {result.mrr_at_k ?? "—"}
                </div>
                {result.ranked_items.map((item) => (
                  <div
                    className="type-supporting mt-1"
                    key={`${result.id}-${item.rank}`}
                  >
                    #{item.rank}{" "}
                    {item.display_name ??
                      item.document_id ??
                      "unknown document"}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
