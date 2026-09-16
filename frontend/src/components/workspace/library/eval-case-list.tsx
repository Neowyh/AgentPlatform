"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/core/i18n/hooks";
import {
  useCreateKnowledgeEvalCase,
  useDeleteKnowledgeEvalCase,
  useDocuments,
  useEvalCaseRevisionApplicability,
  useKnowledgeEvalCase,
  useKnowledgeEvalCases,
  useKnowledgeRevisions,
  useUpdateKnowledgeEvalCase,
} from "@/core/library";
import type {
  EvalCaseRevisionApplicability,
  KnowledgeEvalCase,
  KnowledgeDocument,
} from "@/core/library";

function parseTags(raw: string): string[] {
  return raw
    .split(",")
    .map((tag) => tag.trim())
    .filter((tag) => tag.length > 0);
}

function documentLabel(
  documentId: string,
  names: Record<string, string>,
): string {
  return names[documentId] ?? documentId;
}

function DocumentCheckboxList({
  documents,
  selectedIds,
  onToggle,
}: {
  documents: KnowledgeDocument[];
  selectedIds: string[];
  onToggle: (documentId: string) => void;
}) {
  return (
    <div className="mt-1 space-y-1">
      {documents.map((document) => (
        <label key={document.id} className="type-body flex items-center gap-2">
          <input
            type="checkbox"
            checked={selectedIds.includes(document.id)}
            onChange={() => onToggle(document.id)}
          />
          {document.name}
        </label>
      ))}
    </div>
  );
}

export function EvalCaseList({
  knowledgeBaseId,
  canModify,
}: {
  knowledgeBaseId?: string;
  canModify?: boolean;
}) {
  const { t } = useI18n();
  const i = t.library.evalCaseList;
  const { evalCases, isLoading, error } =
    useKnowledgeEvalCases(knowledgeBaseId);
  const { documents } = useDocuments(knowledgeBaseId);
  const { revisions } = useKnowledgeRevisions(knowledgeBaseId);
  const create = useCreateKnowledgeEvalCase(knowledgeBaseId ?? "");
  const [expandedId, setExpandedId] = useState<string>();
  const [selectedRevisionId, setSelectedRevisionId] = useState<string>();

  const documentNames: Record<string, string> = {};
  for (const document of documents) {
    documentNames[document.id] = document.name;
  }

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
    <div className="space-y-6">
      {canModify ? (
        <CreateEvalCaseForm
          knowledgeBaseId={knowledgeBaseId}
          documentNames={documentNames}
        />
      ) : (
        <div className="text-muted-foreground" role="note">
          {i.restricted}
        </div>
      )}

      <ApplicabilityPanel
        knowledgeBaseId={knowledgeBaseId}
        revisions={revisions}
        selectedRevisionId={selectedRevisionId}
        onSelectRevision={setSelectedRevisionId}
      />

      {evalCases.length === 0 ? (
        <div className="text-muted-foreground">{i.empty}</div>
      ) : (
        <div className="space-y-3">
          {evalCases.map((evalCase) => (
            <div key={evalCase.id} className="rounded-lg border p-4">
              <div className="flex items-start justify-between gap-3">
                <p className="type-body whitespace-pre-wrap">
                  {evalCase.question}
                </p>
                <span className="type-body text-muted-foreground shrink-0">
                  {i.versionAndHash(
                    evalCase.version_no,
                    evalCase.content_hash.slice(0, 12),
                  )}
                </span>
              </div>
              <p className="text-muted-foreground type-body">
                {i.expectedDocsCount(evalCase.expected_document_ids.length)}
                {evalCase.expected_document_ids.length > 0
                  ? ` · ${evalCase.expected_document_ids
                      .map((id) => documentLabel(id, documentNames))
                      .join(", ")}`
                  : ""}
              </p>
              {evalCase.tags.length > 0 ? (
                <div className="mt-1 flex flex-wrap gap-2">
                  {evalCase.tags.map((tag) => (
                    <span
                      key={tag}
                      className="type-body bg-muted rounded-full px-2 py-1"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              ) : null}
              <div className="mt-2 flex items-center gap-3">
                <button
                  type="button"
                  aria-expanded={expandedId === evalCase.id}
                  onClick={() =>
                    setExpandedId(
                      expandedId === evalCase.id ? undefined : evalCase.id,
                    )
                  }
                >
                  {expandedId === evalCase.id ? i.hideDetails : i.viewDetails}
                </button>
                {canModify ? (
                  <EvalCaseActions
                    knowledgeBaseId={knowledgeBaseId}
                    evalCase={evalCase}
                  />
                ) : null}
              </div>
              {expandedId === evalCase.id ? (
                <EvalCaseVersions
                  knowledgeBaseId={knowledgeBaseId}
                  caseId={evalCase.id}
                />
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CreateEvalCaseForm({
  knowledgeBaseId,
  documentNames,
}: {
  knowledgeBaseId: string;
  documentNames: Record<string, string>;
}) {
  const { t } = useI18n();
  const i = t.library.evalCaseList;
  const { documents } = useDocuments(knowledgeBaseId);
  const create = useCreateKnowledgeEvalCase(knowledgeBaseId);
  const [question, setQuestion] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [tags, setTags] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const emptyQuestion = question.trim().length === 0;
  const emptyExpected = selectedIds.length === 0;
  const invalid = emptyQuestion || emptyExpected;

  const toggleDocument = (documentId: string) => {
    setSelectedIds((current) =>
      current.includes(documentId)
        ? current.filter((id) => id !== documentId)
        : [...current, documentId],
    );
  };

  const submit = async () => {
    setSubmitted(true);
    if (invalid || create.isPending) return;
    try {
      await create.mutateAsync({
        question,
        expectedDocumentIds: selectedIds,
        tags: parseTags(tags),
      });
      setQuestion("");
      setSelectedIds([]);
      setTags("");
      setSubmitted(false);
    } catch {
      // surfaced via create.error below
    }
  };

  return (
    <form
      className="space-y-3 rounded-lg border p-4"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <h3 className="type-section-title font-medium">{i.createTitle}</h3>
      <div>
        <label htmlFor="eval-case-question" className="type-body">
          {i.questionLabel}
        </label>
        <textarea
          id="eval-case-question"
          value={question}
          placeholder={i.questionPlaceholder}
          className="bg-background mt-1 w-full rounded-md border p-2"
          rows={2}
          maxLength={4000}
          onChange={(event) => setQuestion(event.target.value)}
        />
      </div>
      <fieldset>
        <legend className="type-body">{i.expectedDocsLabel}</legend>
        {documents.length === 0 ? (
          <div className="text-muted-foreground type-body">
            {i.expectedDocsEmpty}
          </div>
        ) : (
          <DocumentCheckboxList
            documents={documents}
            selectedIds={selectedIds}
            onToggle={toggleDocument}
          />
        )}
      </fieldset>
      <div>
        <label htmlFor="eval-case-tags" className="type-body">
          {i.tagsLabel}
        </label>
        <input
          id="eval-case-tags"
          type="text"
          value={tags}
          placeholder={i.tagsPlaceholder}
          className="bg-background mt-1 w-full rounded-md border p-2"
          onChange={(event) => setTags(event.target.value)}
        />
      </div>
      {submitted && invalid ? (
        <div role="alert" className="text-destructive type-body">
          {i.createFailed}
        </div>
      ) : null}
      {create.error ? (
        <div role="alert" className="text-destructive type-body">
          {i.createFailed}
        </div>
      ) : null}
      <Button
        type="submit"
        disabled={create.isPending}
        aria-busy={create.isPending}
      >
        {create.isPending ? i.creating : i.create}
      </Button>
    </form>
  );
}

function EvalCaseActions({
  knowledgeBaseId,
  evalCase,
}: {
  knowledgeBaseId: string;
  evalCase: KnowledgeEvalCase;
}) {
  const { t } = useI18n();
  const i = t.library.evalCaseList;
  const update = useUpdateKnowledgeEvalCase(knowledgeBaseId);
  const remove = useDeleteKnowledgeEvalCase(knowledgeBaseId);
  const [editing, setEditing] = useState(false);
  const [question, setQuestion] = useState(evalCase.question);
  const [selectedIds, setSelectedIds] = useState<string[]>(
    evalCase.expected_document_ids,
  );
  const [tags, setTags] = useState(evalCase.tags.join(","));
  const { documents } = useDocuments(knowledgeBaseId);

  const save = async () => {
    try {
      await update.mutateAsync({
        caseId: evalCase.id,
        update: {
          question,
          expectedDocumentIds: selectedIds,
          tags: parseTags(tags),
        },
      });
      setEditing(false);
    } catch {
      // surfaced via update.error below
    }
  };

  const removeCase = async () => {
    if (!window.confirm(i.deleteConfirm)) return;
    try {
      await remove.mutateAsync(evalCase.id);
    } catch {
      // surfaced via remove.error below
    }
  };

  if (editing) {
    return (
      <form
        className="w-full space-y-2"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <label
          htmlFor={`eval-case-edit-question-${evalCase.id}`}
          className="sr-only"
        >
          {i.questionLabel}
        </label>
        <textarea
          id={`eval-case-edit-question-${evalCase.id}`}
          value={question}
          className="bg-background w-full rounded-md border p-2"
          rows={2}
          maxLength={4000}
          onChange={(event) => setQuestion(event.target.value)}
        />
        <fieldset>
          <legend className="type-body">{i.expectedDocsLabel}</legend>
          <DocumentCheckboxList
            documents={documents}
            selectedIds={selectedIds}
            onToggle={(documentId) =>
              setSelectedIds((current) =>
                current.includes(documentId)
                  ? current.filter((id) => id !== documentId)
                  : [...current, documentId],
              )
            }
          />
        </fieldset>
        <label
          htmlFor={`eval-case-edit-tags-${evalCase.id}`}
          className="type-body block"
        >
          {i.tagsLabel}
        </label>
        <input
          id={`eval-case-edit-tags-${evalCase.id}`}
          type="text"
          value={tags}
          className="bg-background w-full rounded-md border p-2"
          onChange={(event) => setTags(event.target.value)}
        />
        {update.error ? (
          <div role="alert" className="text-destructive type-body">
            {i.updateFailed}
          </div>
        ) : null}
        <div className="flex items-center gap-3">
          <Button
            type="submit"
            disabled={update.isPending}
            aria-busy={update.isPending}
          >
            {update.isPending ? i.saving : i.save}
          </Button>
          <button type="button" onClick={() => setEditing(false)}>
            {i.cancel}
          </button>
        </div>
      </form>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <button type="button" onClick={() => setEditing(true)}>
        {i.edit}
      </button>
      <button
        type="button"
        aria-label={`${i.delete}`}
        disabled={remove.isPending}
        aria-busy={remove.isPending}
        onClick={() => void removeCase()}
      >
        {remove.isPending ? i.deleting : i.delete}
      </button>
      {remove.error ? (
        <span role="alert" className="text-destructive type-body">
          {i.deleteFailed}
        </span>
      ) : null}
    </div>
  );
}

function EvalCaseVersions({
  knowledgeBaseId,
  caseId,
}: {
  knowledgeBaseId: string;
  caseId: string;
}) {
  const { t } = useI18n();
  const i = t.library.evalCaseList;
  const { data, isLoading, error } = useKnowledgeEvalCase(
    knowledgeBaseId,
    caseId,
  );

  if (isLoading) {
    return <div className="text-muted-foreground mt-3">{i.loading}</div>;
  }
  if (error || !data) {
    return (
      <div role="alert" className="text-muted-foreground mt-3">
        {i.loadFailed}
      </div>
    );
  }
  return (
    <div className="mt-3 space-y-2">
      <h4 className="type-body text-muted-foreground">{i.versionsTitle}</h4>
      <ul className="space-y-1">
        {data.versions.map((version) => (
          <li
            key={version.version_no}
            className="text-muted-foreground type-body"
          >
            {i.versionAndHash(
              version.version_no,
              version.content_hash.slice(0, 12),
            )}{" "}
            · {version.change_type} · {version.changed_at ?? ""}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ApplicabilityPanel({
  knowledgeBaseId,
  revisions,
  selectedRevisionId,
  onSelectRevision,
}: {
  knowledgeBaseId: string;
  revisions: { id: string; revision_no: number; status: string }[];
  selectedRevisionId: string | undefined;
  onSelectRevision: (revisionId: string | undefined) => void;
}) {
  const { t } = useI18n();
  const i = t.library.evalCaseList;
  const { data, isLoading, error } = useEvalCaseRevisionApplicability(
    knowledgeBaseId,
    selectedRevisionId,
  );

  return (
    <section className="space-y-2 rounded-lg border p-4">
      <h3 className="type-section-title font-medium">{i.applicabilityTitle}</h3>
      <label htmlFor="eval-case-revision-select" className="sr-only">
        {i.applicabilityTitle}
      </label>
      <select
        id="eval-case-revision-select"
        value={selectedRevisionId ?? ""}
        className="bg-background w-full rounded-md border p-2"
        onChange={(event) => onSelectRevision(event.target.value || undefined)}
      >
        <option value="">{i.applicabilityPlaceholder}</option>
        {revisions.map((revision) => (
          <option key={revision.id} value={revision.id}>
            {i.revisionOption(revision.revision_no, revision.status)}
          </option>
        ))}
      </select>
      {selectedRevisionId && isLoading ? (
        <div className="text-muted-foreground type-body">
          {i.applicabilityLoading}
        </div>
      ) : null}
      {selectedRevisionId && error ? (
        <div role="alert" className="text-destructive type-body">
          {i.applicabilityLoadFailed}
        </div>
      ) : null}
      {selectedRevisionId && data ? (
        <ApplicabilityResults report={data} />
      ) : null}
    </section>
  );
}

function ApplicabilityResults({
  report,
}: {
  report: EvalCaseRevisionApplicability;
}) {
  const { t } = useI18n();
  const i = t.library.evalCaseList;
  if (report.items.length === 0) {
    return <div className="text-muted-foreground type-body">{i.empty}</div>;
  }
  return (
    <ul className="space-y-1">
      {report.items.map((item) => (
        <li
          key={item.case_id}
          className="type-body flex items-start justify-between gap-3"
        >
          <span className="whitespace-pre-wrap">{item.question}</span>
          {item.applicable ? (
            <span className="type-body shrink-0 rounded-full bg-green-100 px-2 py-1 text-green-800">
              {i.applicable}
            </span>
          ) : (
            <span
              role="alert"
              className="type-body shrink-0 rounded-full bg-red-100 px-2 py-1 text-red-800"
            >
              {i.notApplicable(item.missing_document_ids.length)}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}
