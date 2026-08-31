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
# 工作流名称（必填，1-60 字符，需唯一）
name: my-workflow
# 可选描述
description: "请修改此模板以适配你的场景"
# 输入参数——运行时会弹窗让用户填写
inputs:
  topic:
    type: string
    required: true
    description: "需要处理的任务或问题"
state: {}
# 起始节点 ID（必须匹配下方某个节点的 id）
entrypoint: start
nodes:
  - id: start
    type: action
    action:
      # kind: "agent" 使用 AI agent；"tool" 直接调用工具
      kind: agent
      # 在"设置 → Agents"中创建 agent 后，将名称填写在此处
      name: my-agent
      params:
        # prompt 支持 {{inputs.*}} / {{state.*}} 引用
        prompt: "请处理以下任务：{{inputs.topic}}"
edges: []
`;

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
            <h1 className="type-page-title font-semibold">
              {t.workflows.newWorkflow}
            </h1>
            <p className="text-muted-foreground type-body mt-0.5">
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
