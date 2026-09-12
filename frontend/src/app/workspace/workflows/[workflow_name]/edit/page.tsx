"use client";

import { yaml } from "@codemirror/lang-yaml";
import { basicLightInit } from "@uiw/codemirror-theme-basic";
import { monokaiInit } from "@uiw/codemirror-theme-monokai";
import CodeMirror from "@uiw/react-codemirror";
import { ArrowLeftIcon, SaveIcon } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { WorkspaceBreadcrumb } from "@/components/workspace/workspace-breadcrumb";
import { useAuth } from "@/core/auth/AuthProvider";
import { useI18n } from "@/core/i18n/hooks";
import { listKnowledgeBases } from "@/core/resources/api";
import { useUpdateWorkflow, useWorkflow } from "@/core/workflows";
import type { WorkflowDetail } from "@/core/workflows/types";
import { validateYaml } from "@/core/workflows/validate";

const customDarkTheme = monokaiInit({
  settings: {
    background: "transparent",
    gutterBackground: "transparent",
    gutterForeground: "#555",
    gutterActiveForeground: "#fff",
    fontSize: "var(--type-body)",
  },
});

const customLightTheme = basicLightInit({
  settings: {
    background: "transparent",
    fontSize: "var(--type-body)",
  },
});

export default function WorkflowEditPage() {
  const router = useRouter();
  const { workflow_name } = useParams<{ workflow_name: string }>();
  const { workflow, isLoading: isLoadingWorkflow } = useWorkflow(workflow_name);
  const updateWorkflow = useUpdateWorkflow();
  const { resolvedTheme } = useTheme();
  const { t } = useI18n();
  const { user } = useAuth();

  const isOwner = !workflow?.owner_id || workflow.owner_id === user?.id;

  const [content, setContent] = useState("");
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<
    Array<{ id: string; slug: string; display_name: string }>
  >([]);
  const [knowledgeDependencies, setKnowledgeDependencies] = useState<
    NonNullable<WorkflowDetail["knowledge_dependencies"]>
  >([]);

  useEffect(() => {
    if (workflow) {
      setContent(workflow.yaml_content);
      setKnowledgeDependencies(workflow.knowledge_dependencies ?? []);
    }
  }, [workflow]);

  useEffect(() => {
    void listKnowledgeBases()
      .then(setKnowledgeBases)
      .catch(() => undefined);
  }, []);

  const extensions = useMemo(() => [yaml()], []);

  const handleChange = useCallback((value: string) => {
    setContent(value);
    setValidationErrors(validateYaml(value));
  }, []);

  const workflowResourceId = workflow?.resource_id;
  const workflowDraftRevision = workflow?.draft_revision;
  const workflowVersion = workflow?.version;

  const handleSave = useCallback(async () => {
    const errors = validateYaml(content);
    setValidationErrors(errors);
    if (errors.length > 0) return;

    try {
      await updateWorkflow.mutateAsync({
        name: workflow_name,
        data: workflowResourceId
          ? {
              yaml_content: content,
              draft_revision: workflowDraftRevision,
              knowledge_dependencies: knowledgeDependencies,
            }
          : { yaml_content: content, version: Number(workflowVersion) },
      });
      toast.success(t.workflows.updated);
      router.push(`/workspace/workflows/${workflow_name}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }, [
    content,
    router,
    updateWorkflow,
    workflow_name,
    t,
    workflowDraftRevision,
    workflowResourceId,
    workflowVersion,
    knowledgeDependencies,
  ]);

  if (isLoadingWorkflow) {
    return (
      <div className="flex size-full items-center justify-center">
        <div className="text-muted-foreground type-body">
          {t.common.loading}
        </div>
      </div>
    );
  }

  if (!workflow) {
    return (
      <div className="flex size-full flex-col items-center justify-center gap-4">
        <div className="text-destructive type-body">{t.workflows.notFound}</div>
        <Button
          variant="outline"
          onClick={() => router.push("/workspace/workflows")}
        >
          {t.workflows.backToWorkflows}
        </Button>
      </div>
    );
  }

  if (!isOwner) {
    return (
      <div className="flex size-full flex-col items-center justify-center gap-4">
        <div className="text-destructive type-body">{t.workflows.notOwner}</div>
        <Button
          variant="outline"
          onClick={() => router.push(`/workspace/workflows/${workflow_name}`)}
        >
          {t.workflows.backToWorkflows}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex size-full flex-col">
      <WorkspaceBreadcrumb />
      {/* Header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => router.push(`/workspace/workflows/${workflow_name}`)}
          >
            <ArrowLeftIcon className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="type-page-title font-semibold">
              {t.workflows.edit}
            </h1>
            <p className="text-muted-foreground type-body mt-0.5">
              {workflow_name}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => router.push(`/workspace/workflows/${workflow_name}`)}
          >
            {t.common.cancel}
          </Button>
          <Button onClick={handleSave} disabled={updateWorkflow.isPending}>
            <SaveIcon className="mr-1.5 h-4 w-4" />
            {updateWorkflow.isPending
              ? t.workflows.saving
              : t.workflows.saveChanges}
          </Button>
        </div>
      </div>

      {/* Validation errors */}
      {validationErrors.length > 0 && (
        <div className="border-b px-6 py-2">
          <Alert variant="destructive">
            <AlertDescription>
              <ul className="list-inside list-disc">
                {validationErrors.map((error, i) => (
                  <li key={i}>{error}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        </div>
      )}

      {knowledgeBases.length > 0 && (
        <div className="border-b px-6 py-3">
          <div className="mx-auto max-w-2xl space-y-2">
            <div className="type-body font-medium">KnowledgeBases</div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {knowledgeBases.map((knowledgeBase) => {
                const dependency = knowledgeDependencies.find(
                  (item) => item.resource_id === knowledgeBase.id,
                );
                return (
                  <label
                    key={knowledgeBase.id}
                    className="hover:bg-accent flex cursor-pointer items-center gap-2 rounded-md border p-3"
                  >
                    <input
                      type="checkbox"
                      checked={dependency !== undefined}
                      onChange={() =>
                        setKnowledgeDependencies((previous) =>
                          dependency
                            ? previous.filter(
                                (item) => item.resource_id !== knowledgeBase.id,
                              )
                            : [
                                ...previous,
                                {
                                  resource_id: knowledgeBase.id,
                                  dependency_mode: "live",
                                  revision_id: null,
                                  required: true,
                                  purpose: null,
                                },
                              ],
                        )
                      }
                      className="h-4 w-4 rounded border-gray-300"
                    />
                    <span className="type-body truncate">
                      {knowledgeBase.display_name || knowledgeBase.slug}
                    </span>
                    {dependency && (
                      <div className="flex gap-2">
                        <select
                          value={dependency.dependency_mode}
                          onChange={(event) =>
                            setKnowledgeDependencies((previous) =>
                              previous.map((item) =>
                                item.resource_id === knowledgeBase.id
                                  ? {
                                      ...item,
                                      dependency_mode: event.target.value as
                                        | "live"
                                        | "pinned",
                                      revision_id:
                                        event.target.value === "live"
                                          ? null
                                          : item.revision_id,
                                    }
                                  : item,
                              ),
                            )
                          }
                          className="type-compact h-8 rounded border px-2"
                          aria-label={`${knowledgeBase.slug} dependency mode`}
                        >
                          <option value="live">LIVE</option>
                          <option value="pinned">PINNED</option>
                        </select>
                        {dependency.dependency_mode === "pinned" && (
                          <input
                            value={dependency.revision_id ?? ""}
                            onChange={(event) =>
                              setKnowledgeDependencies((previous) =>
                                previous.map((item) =>
                                  item.resource_id === knowledgeBase.id
                                    ? {
                                        ...item,
                                        revision_id: event.target.value || null,
                                      }
                                    : item,
                                ),
                              )
                            }
                            placeholder="Revision ID"
                            className="type-compact h-8 min-w-0 rounded border px-2"
                            aria-label={`${knowledgeBase.slug} revision ID`}
                          />
                        )}
                      </div>
                    )}
                  </label>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Editor */}
      <div className="flex min-h-0 flex-1">
        <div className="flex w-full flex-col">
          <div className="border-b px-4 py-2">
            <span className="type-body font-medium">
              {t.workflows.yamlEditor}
            </span>
          </div>
          <div className="flex-1 overflow-auto">
            <CodeMirror
              value={content}
              onChange={handleChange}
              extensions={extensions}
              theme={
                resolvedTheme === "dark" ? customDarkTheme : customLightTheme
              }
              className="h-full [&_.cm-editor]:h-full [&_.cm-focused]:outline-none!"
              basicSetup={{
                lineNumbers: true,
                foldGutter: true,
                highlightActiveLine: true,
                highlightActiveLineGutter: true,
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
