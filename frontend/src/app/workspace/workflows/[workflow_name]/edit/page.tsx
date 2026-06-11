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
import { useUpdateWorkflow, useWorkflow } from "@/core/workflows";
import { validateYaml } from "@/core/workflows/validate";

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

export default function WorkflowEditPage() {
  const router = useRouter();
  const { workflow_name } = useParams<{ workflow_name: string }>();
  const { workflow, isLoading: isLoadingWorkflow } = useWorkflow(workflow_name);
  const updateWorkflow = useUpdateWorkflow();
  const { resolvedTheme } = useTheme();

  const [content, setContent] = useState("");
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  useEffect(() => {
    if (workflow) {
      setContent(workflow.yaml_content);
    }
  }, [workflow]);

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
      await updateWorkflow.mutateAsync({
        name: workflow_name,
        data: { yaml_content: content },
      });
      toast.success("Workflow updated");
      router.push(`/workspace/workflows/${workflow_name}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }, [content, router, updateWorkflow, workflow_name]);

  if (isLoadingWorkflow) {
    return (
      <div className="flex size-full items-center justify-center">
        <div className="text-muted-foreground text-sm">Loading...</div>
      </div>
    );
  }

  if (!workflow) {
    return (
      <div className="flex size-full flex-col items-center justify-center gap-4">
        <div className="text-destructive text-sm">Workflow not found</div>
        <Button
          variant="outline"
          onClick={() => router.push("/workspace/workflows")}
        >
          Back to Workflows
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
            <h1 className="text-xl font-semibold">Edit Workflow</h1>
            <p className="text-muted-foreground mt-0.5 text-sm">
              {workflow_name}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => router.push(`/workspace/workflows/${workflow_name}`)}
          >
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={updateWorkflow.isPending}>
            <SaveIcon className="mr-1.5 h-4 w-4" />
            {updateWorkflow.isPending ? "Saving..." : "Save Changes"}
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
            <span className="text-sm font-medium">YAML Editor</span>
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
