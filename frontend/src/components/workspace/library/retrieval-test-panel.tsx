"use client";

import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/core/i18n/hooks";
import {
  RetrievalTestAccessError,
  useKnowledgeRevisions,
  useRetrievalTest,
  useRetrievalTests,
  useRunRetrievalTest,
} from "@/core/library";
import type { RetrievalTestItem, RetrievalTestRecord } from "@/core/library";

const RETRIEVABLE_STATUSES = new Set(["published", "superseded", "ready"]);

function formatScore(score: number | null): string {
  return score === null ? "—" : String(score);
}

function formatPosition(position: Record<string, unknown>): string | null {
  const raw = position.page ?? position.page_number;
  const page =
    typeof raw === "string" && raw.trim()
      ? raw.trim()
      : typeof raw === "number"
        ? String(raw)
        : null;
  if (page) return `Page ${page}`;
  const section = position.section;
  if (typeof section === "string" && section.trim()) return section.trim();
  const rawPosition = position.position;
  if (typeof rawPosition === "string" && rawPosition.trim())
    return rawPosition.trim();
  if (typeof rawPosition === "number") return String(rawPosition);
  return null;
}

export function RetrievalTestPanel({
  knowledgeBaseId,
  canModify,
}: {
  knowledgeBaseId?: string;
  canModify?: boolean;
}) {
  const { t } = useI18n();
  const i = t.library.retrievalTest;
  const { revisions, isLoading, error } =
    useKnowledgeRevisions(knowledgeBaseId);
  const retrievable = useMemo(
    () =>
      revisions.filter(
        (revision) =>
          RETRIEVABLE_STATUSES.has(revision.status) &&
          (revision.status !== "ready" || canModify),
      ),
    [canModify, revisions],
  );
  const [selectedRevisionId, setSelectedRevisionId] = useState<string>();
  const [profileId, setProfileId] = useState<"frozen" | "configured">("frozen");
  const revisionId =
    selectedRevisionId ?? retrievable[retrievable.length - 1]?.id;
  const selectedRevision = retrievable.find(
    (revision) => revision.id === revisionId,
  );
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState("8");
  const [selectedTestId, setSelectedTestId] = useState<string>();
  const run = useRunRetrievalTest(knowledgeBaseId ?? "");
  const archived = useRetrievalTests(knowledgeBaseId);
  const record = useRetrievalTest(knowledgeBaseId, selectedTestId);

  if (!knowledgeBaseId) {
    return <div className="text-muted-foreground">{i.selectKnowledgeBase}</div>;
  }
  if (isLoading) {
    return <div className="text-muted-foreground">{i.loading}</div>;
  }
  if (error) {
    return (
      <div role="alert" className="text-muted-foreground">
        {i.revisionsLoadFailed}
      </div>
    );
  }
  if (retrievable.length === 0) {
    return <div className="text-muted-foreground">{i.noPublishedRevision}</div>;
  }

  const frozenProfile = selectedRevision?.knowledge_profiles as
    | { retrieval?: Record<string, unknown> }
    | undefined;

  const submit = () => {
    if (!revisionId || !query.trim() || run.isPending) return;
    const parsedK = Number.parseInt(topK, 10);
    void run.mutateAsync({
      revisionId,
      profileId,
      query: query.trim(),
      topK: Number.isFinite(parsedK) ? parsedK : undefined,
    });
  };

  return (
    <div className="space-y-6">
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className="type-body text-muted-foreground">
              {i.revisionLabel}
            </span>
            <select
              className="bg-background rounded-md border px-3 py-2"
              value={revisionId ?? ""}
              onChange={(event) => setSelectedRevisionId(event.target.value)}
            >
              {retrievable.map((revision) => (
                <option key={revision.id} value={revision.id}>
                  v{revision.revision_no} ·{" "}
                  {i.manifest(revision.manifest_hash.slice(0, 12))}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="type-body text-muted-foreground">
              {i.questionLabel}
            </span>
            <input
              type="text"
              aria-label={i.questionLabel}
              placeholder={i.questionPlaceholder}
              maxLength={500}
              className="bg-background w-80 rounded-md border px-3 py-2"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="type-body text-muted-foreground">
              {i.topKLabel}
            </span>
            <input
              type="number"
              aria-label={i.topKLabel}
              min={1}
              max={20}
              className="bg-background w-24 rounded-md border px-3 py-2"
              value={topK}
              onChange={(event) => setTopK(event.target.value)}
            />
          </label>
          <Button
            type="submit"
            disabled={run.isPending || !query.trim()}
            aria-busy={run.isPending}
          >
            {run.isPending ? i.running : i.run}
          </Button>
        </div>
        <label className="flex max-w-xs flex-col gap-1">
          <span className="type-body text-muted-foreground">
            {i.profileLabel}
          </span>
          <select
            className="bg-background rounded-md border px-3 py-2"
            value={profileId}
            onChange={(event) =>
              setProfileId(event.target.value as "frozen" | "configured")
            }
          >
            <option value="frozen">{i.frozenProfile}</option>
            <option value="configured">{i.configuredProfile}</option>
          </select>
        </label>
        {profileId === "frozen" && frozenProfile?.retrieval ? (
          <p className="text-muted-foreground type-body">
            {JSON.stringify(frozenProfile.retrieval)}
          </p>
        ) : null}
        {run.error ? (
          <div role="alert" className="text-destructive type-body">
            {run.error instanceof RetrievalTestAccessError
              ? i.restricted
              : i.runFailed}
          </div>
        ) : null}
      </form>

      <RunResult record={run.data} />

      <div className="space-y-2">
        <h3 className="type-section-title font-medium">{i.archivedTitle}</h3>
        {archived.error ? (
          <div role="alert" className="text-muted-foreground">
            {i.archivedLoadFailed}
          </div>
        ) : archived.isLoading ? (
          <div className="text-muted-foreground">{i.loading}</div>
        ) : archived.tests.length === 0 ? (
          <div className="text-muted-foreground">{i.archivedEmpty}</div>
        ) : (
          <ul className="space-y-2">
            {archived.tests.map((test) => (
              <li key={test.id} className="rounded-lg border p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="type-body truncate">{test.query}</p>
                    <p className="text-muted-foreground type-body">
                      v{test.revision_no} · {test.result_status} ·{" "}
                      {test.created_at ?? ""}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSelectedTestId(test.id)}
                    aria-pressed={selectedTestId === test.id}
                  >
                    {i.viewRecord}
                  </button>
                </div>
                {selectedTestId === test.id ? (
                  <ArchivedRecord state={record} />
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function RunResult({ record }: { record: RetrievalTestRecord | undefined }) {
  const { t } = useI18n();
  const i = t.library.retrievalTest;
  if (!record) return null;
  if (record.result_status === "empty_hit") {
    return (
      <div role="status" className="text-muted-foreground">
        {i.emptyResult}
      </div>
    );
  }
  if (record.result_status === "provider_error") {
    return (
      <div role="alert" className="text-destructive type-body">
        {i.providerFailed(record.error_code ?? "error")}
      </div>
    );
  }
  const items = record.items ?? [];
  return (
    <div className="space-y-2">
      {record.applied_parameters ? (
        <p className="text-muted-foreground type-body">
          {i.appliedParameters}:{" "}
          {Object.entries(record.applied_parameters)
            .map(([key, value]) => `${key}: ${value}`)
            .join(" · ")}
        </p>
      ) : null}
      <h3 className="type-section-title font-medium">
        {i.hitsTitle(record.returned_count)}
      </h3>
      <ul className="space-y-2">
        {items.map((item) => (
          <HitItem
            key={`${item.rank}-${item.chunk_ref ?? item.rank}`}
            item={item}
          />
        ))}
      </ul>
    </div>
  );
}

function HitItem({ item }: { item: RetrievalTestItem }) {
  const position = formatPosition(item.position ?? {});
  return (
    <li className="rounded-lg border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="type-body font-medium">#{item.rank}</span>
        <span className="type-body">{item.display_name ?? "—"}</span>
        {position ? (
          <span className="text-muted-foreground type-body">{position}</span>
        ) : null}
        <span className="text-muted-foreground type-body">
          score {formatScore(item.score)} · rerank{" "}
          {formatScore(item.rerank_score)}
        </span>
      </div>
      <p className="type-body mt-1 break-words whitespace-pre-wrap">
        {item.content}
      </p>
    </li>
  );
}

function ArchivedRecord({
  state,
}: {
  state: {
    data?: RetrievalTestRecord;
    isLoading: boolean;
    error: Error | null;
  };
}) {
  const { t } = useI18n();
  const i = t.library.retrievalTest;
  if (state.isLoading) {
    return <div className="text-muted-foreground mt-2">{i.loading}</div>;
  }
  if (state.error) {
    return (
      <div role="alert" className="text-destructive type-body mt-2">
        {state.error instanceof RetrievalTestAccessError
          ? i.recordLoadFailed
          : i.archivedLoadFailed}
      </div>
    );
  }
  if (!state.data) return null;
  return (
    <div className="mt-2">
      <RunResult record={state.data} />
    </div>
  );
}
