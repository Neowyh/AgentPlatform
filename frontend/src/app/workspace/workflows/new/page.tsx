"use client";

import { yaml } from "@codemirror/lang-yaml";
import { basicLightInit } from "@uiw/codemirror-theme-basic";
import { monokaiInit } from "@uiw/codemirror-theme-monokai";
import CodeMirror from "@uiw/react-codemirror";
import { ArrowLeftIcon, SaveIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { WorkspaceBreadcrumb } from "@/components/workspace/workspace-breadcrumb";
import { useI18n } from "@/core/i18n/hooks";
import { useCreateWorkflow } from "@/core/workflows";
import { validateYaml } from "@/core/workflows/validate";

const DEFAULT_YAML = `schema_version: 2
name: my-workflow
description: ""
inputs: {}
state: {}
entrypoint: start
nodes:
  - id: start
    type: action
    action:
      kind: agent
      name: ""
      params:
        prompt: ""
edges: []
`;

const customDarkTheme = monokaiInit({
  settings: {
    background: "transparent",
    gutterBackground: "transparent",
    gutterForeground: "#555",
    gutterActiveForeground: "#fff",
    fontSize: "var(--text-sm)",
  },
});

const customLightTheme = basicLightInit({
  settings: {
    background: "transparent",
    fontSize: "var(--text-sm)",
  },
});

export default function NewWorkflowPage() {
  const router = useRouter();
  const createWorkflow = useCreateWorkflow();
  const { resolvedTheme } = useTheme();
  const { t } = useI18n();

  const [content, setContent] = useState(DEFAULT_YAML);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  const extensions = useMemo(() => [yaml()], []);

  const handleChange = useCallback((value: string) => {
    setContent(value);
    setValidationErrors(validateYaml(value));
  }, []);

  const handleSave = useCallback(async () => {
    const errors = validateYaml(content);
    setValidationErrors(errors);
    if (errors.length > 0) return;

    try {
      await createWorkflow.mutateAsync({ yaml_content: content });
      toast.success(t.workflows.created);
      router.push("/workspace/workflows");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }, [content, createWorkflow, router, t]);

  return (
    <div className="flex size-full flex-col">
      <WorkspaceBreadcrumb />
      {/* Header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => router.push("/workspace/workflows")}
          >
            <ArrowLeftIcon className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-xl font-semibold">{t.workflows.newWorkflow}</h1>
            <p className="text-muted-foreground mt-0.5 text-sm">
              {t.workflows.createSubtitle}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => router.push("/workspace/workflows")}
          >
            {t.common.cancel}
          </Button>
          <Button onClick={handleSave} disabled={createWorkflow.isPending}>
            <SaveIcon className="mr-1.5 h-4 w-4" />
            {createWorkflow.isPending
              ? t.workflows.creating
              : t.workflows.newWorkflow}
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

      {/* Editor */}
      <div className="flex min-h-0 flex-1">
        <div className="flex w-full flex-col">
          <div className="border-b px-4 py-2">
            <span className="text-sm font-medium">
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
