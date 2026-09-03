"use client";

import {
  ArrowLeftIcon,
  DownloadIcon,
  EditIcon,
  PlusIcon,
  PlayIcon,
  WorkflowIcon,
  XIcon,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { VisibilityImpactPanel } from "@/components/workspace/resources/visibility-impact-panel";
import { WorkspaceBreadcrumb } from "@/components/workspace/workspace-breadcrumb";
import { useI18n } from "@/core/i18n/hooks";
import { useModels } from "@/core/models/hooks";
import { useLocalSettings } from "@/core/settings";
import {
  changeResourceVisibility,
  createVisibilityApplication,
} from "@/core/visibility-applications/api";
import { classifyVisibilityChange } from "@/core/visibility-applications/options";
import { useRunWorkflow, useWorkflow, useWorkflowRuns } from "@/core/workflows";

export default function WorkflowDetailPage() {
  const router = useRouter();
  const { workflow_name } = useParams<{ workflow_name: string }>();
  const { workflow, isLoading, error } = useWorkflow(workflow_name);
  const runWorkflowMutation = useRunWorkflow();
  const { t } = useI18n();

  const [runDialogOpen, setRunDialogOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const { models } = useModels({ enabled: runDialogOpen });
  const [settings] = useLocalSettings();
  useEffect(() => {
    if (!runDialogOpen) return;
    const current = settings.context.model_name;
    setSelectedModel(
      current && models.some((m) => m.name === current) ? current : "",
    );
  }, [runDialogOpen, settings.context.model_name, models]);
  const [visibilityDialogOpen, setVisibilityDialogOpen] = useState(false);
  const [inputValues, setInputValues] = useState<Record<string, string>>({});
  const [runFiles, setRunFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [targetVisibility, setTargetVisibility] = useState("department");
  const [visibilityReason, setVisibilityReason] = useState("");
  const [submittingApplication, setSubmittingApplication] = useState(false);
  const [confirmingDowngrade, setConfirmingDowngrade] = useState(false);
  const [cascadeDowngrade, setCascadeDowngrade] = useState(false);

  useEffect(() => {
    if (workflow?.resource_id && workflow_name !== workflow.resource_id) {
      router.replace(`/workspace/workflows/${workflow.resource_id}`);
    }
  }, [router, workflow, workflow_name]);

  useEffect(() => {
    if (workflow) {
      setTargetVisibility(workflow.visibility ?? "private");
      setVisibilityReason("");
      setConfirmingDowngrade(false);
    }
  }, [workflow]);

  const { runs } = useWorkflowRuns(workflow_name);

  function handleFilesSelected(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files ?? []);
    const incomingZips = selected.filter((file) =>
      file.name.toLowerCase().endsWith(".zip"),
    );
    const existingZip = runFiles.find((file) =>
      file.name.toLowerCase().endsWith(".zip"),
    );

    if (incomingZips.length > 1) {
      toast.error(t.workflows.singleSourceZip);
      event.target.value = "";
      return;
    }

    const accepted = selected.filter(
      (file) =>
        !existingZip ||
        !file.name.toLowerCase().endsWith(".zip") ||
        file.name === existingZip.name,
    );
    if (accepted.length !== selected.length) {
      toast.error(t.workflows.singleSourceZip);
    }

    setRunFiles((current) => {
      const next = [...current];
      for (const file of accepted) {
        const existingIndex = next.findIndex(
          (currentFile) => currentFile.name === file.name,
        );
        if (existingIndex === -1) next.push(file);
        else next[existingIndex] = file;
      }
      return next;
    });
    if (accepted.some((file) => file.name.toLowerCase().endsWith(".zip"))) {
      setInputValues((previous) => ({
        ...previous,
        evidence_mode: previous.evidence_mode ?? "hybrid",
      }));
    }
    event.target.value = "";
  }

  if (isLoading) {
    return (
      <div className="flex size-full items-center justify-center">
        <div className="text-muted-foreground type-body">
          {t.common.loading}
        </div>
      </div>
    );
  }

  if (error || !workflow) {
    return (
      <div className="flex size-full flex-col items-center justify-center gap-4">
        <div className="text-destructive type-body">
          {error?.message ?? t.workflows.notFound}
        </div>
        <Button
          variant="outline"
          onClick={() => router.push("/workspace/workflows")}
        >
          {t.workflows.backToWorkflows}
        </Button>
      </div>
    );
  }

  async function handleRun() {
    if (!workflow) return;
    // Validate required inputs
    for (const [key, param] of Object.entries(workflow.inputs)) {
      if (["code_package_source", "upload_dir"].includes(key)) continue;
      if (param.required && !inputValues[key]?.trim()) {
        toast.error(t.workflows.requiredMissing(key));
        return;
      }
    }

    const inputs: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(inputValues)) {
      if (["code_package_source", "upload_dir"].includes(key)) continue;
      if (value.trim()) {
        try {
          inputs[key] = JSON.parse(value);
        } catch {
          inputs[key] = value;
        }
      }
    }

    try {
      const result = await runWorkflowMutation.mutateAsync({
        name: workflow_name,
        inputs,
        modelName: selectedModel || undefined,
        ...(runFiles.length ? { files: runFiles } : {}),
      });
      setRunDialogOpen(false);
      toast.success(t.workflows.started);
      router.push(
        `/workspace/workflows/${encodeURIComponent(workflow_name)}/runs/${encodeURIComponent(result.run_id)}`,
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }

  const visibilityColor =
    workflow?.visibility === "public"
      ? "bg-green-100 text-green-800"
      : workflow?.visibility === "department"
        ? "bg-blue-100 text-blue-800"
        : "bg-gray-100 text-gray-800";

  function handleExport() {
    if (!workflow?.yaml_content) {
      toast.error(t.workflows.exportFailed);
      return;
    }
    const blob = new Blob([workflow.yaml_content], { type: "text/yaml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${workflow.name}.yaml`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success(t.workflows.exportSuccess);
  }

  async function handleSubmitVisibility() {
    if (!workflow) return;
    const change = classifyVisibilityChange(
      workflow.visibility,
      targetVisibility,
    );
    if (change === "unchanged") return;
    if (change === "downgrade") {
      setConfirmingDowngrade(true);
      return;
    }
    if (!visibilityReason.trim()) {
      toast.error(t.workflows.reasonRequired);
      return;
    }

    setSubmittingApplication(true);
    try {
      await createVisibilityApplication({
        resource_type: "workflow",
        resource_id: workflow.resource_id ?? workflow.name,
        target_visibility: targetVisibility,
        reason: visibilityReason.trim(),
      });
      toast.success(t.workflows.applicationSubmitted);
      setVisibilityDialogOpen(false);
      setVisibilityReason("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmittingApplication(false);
    }
  }

  async function handleConfirmDowngrade() {
    if (!workflow) return;
    setSubmittingApplication(true);
    try {
      await changeResourceVisibility({
        resource_id: workflow.resource_id ?? workflow.name,
        visibility: targetVisibility,
        cascade: cascadeDowngrade,
      });
      toast.success(t.workflows.visibilityUpdated);
      setVisibilityDialogOpen(false);
      setVisibilityReason("");
      setConfirmingDowngrade(false);
      setCascadeDowngrade(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmittingApplication(false);
    }
  }

  return (
    <div className="flex size-full flex-col">
      <WorkspaceBreadcrumb />
      {/* Page header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => router.push("/workspace/workflows")}
          >
            <ArrowLeftIcon className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-2">
            <div className="bg-primary/10 text-primary flex h-9 w-9 items-center justify-center rounded-lg">
              <WorkflowIcon className="h-5 w-5" />
            </div>
            <div>
              <h1 className="type-page-title font-semibold">{workflow.name}</h1>
              {workflow.description && (
                <p className="text-muted-foreground type-body mt-0.5">
                  {workflow.description}
                </p>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">v{workflow.version}</Badge>
          <Badge className={visibilityColor}>
            {t.workflows.visibility}: {workflow.visibility}
          </Badge>
          <Button variant="outline" onClick={handleExport}>
            <DownloadIcon className="mr-1.5 h-4 w-4" />
            {t.workflows.export}
          </Button>
          {!workflow.read_only && (
            <>
              <Button
                variant="outline"
                onClick={() => setVisibilityDialogOpen(true)}
              >
                {t.workflows.applyVisibility}
              </Button>
              <Button variant="outline" asChild>
                <Link
                  href={`/workspace/workflows/${encodeURIComponent(workflow_name)}/edit`}
                >
                  <EditIcon className="mr-1.5 h-4 w-4" />
                  {t.workflows.edit}
                </Link>
              </Button>
            </>
          )}
          <Button onClick={() => setRunDialogOpen(true)}>
            <PlayIcon className="mr-1.5 h-4 w-4" />
            {t.workflows.run}
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          {/* Steps overview */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <WorkflowIcon className="h-5 w-5" />
                {t.workflows.stepsTitle(workflow.steps_count)}
              </CardTitle>
              <CardDescription>{t.workflows.stepsDescription}</CardDescription>
            </CardHeader>
            <CardContent>
              {workflow.steps.length === 0 ? (
                <p className="text-muted-foreground type-body">
                  {t.workflows.noSteps}
                </p>
              ) : (
                <div className="space-y-3">
                  {workflow.steps.map((step, index) => (
                    <div
                      key={step.id}
                      className="flex items-start gap-3 rounded-md border p-3"
                    >
                      <div className="bg-muted type-body flex h-7 w-7 shrink-0 items-center justify-center rounded-full font-medium">
                        {index + 1}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{step.id}</span>
                          <Badge variant="outline" className="type-body">
                            {step.type}
                          </Badge>
                          {step.action?.name && (
                            <Badge variant="secondary" className="type-body">
                              {step.action.name}
                            </Badge>
                          )}
                        </div>
                        {typeof step.action?.params?.prompt === "string" && (
                          <p className="text-muted-foreground type-body mt-1 line-clamp-2">
                            {step.action.params.prompt}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Inputs */}
          {Object.keys(workflow.inputs).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>{t.workflows.inputsTitle}</CardTitle>
                <CardDescription>
                  {t.workflows.inputsDescription}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {Object.entries(workflow.inputs).map(([key, param]) => (
                    <div
                      key={key}
                      className="flex items-center justify-between rounded-md border p-3"
                    >
                      <div>
                        <span className="type-body font-mono font-medium">
                          {key}
                        </span>
                        {param.description && (
                          <p className="text-muted-foreground type-body">
                            {param.description}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="type-body">
                          {param.type}
                        </Badge>
                        {param.required && (
                          <Badge variant="destructive" className="type-body">
                            {t.workflows.required}
                          </Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>{t.workflows.runHistory}</CardTitle>
            </CardHeader>
            <CardContent>
              {runs.length === 0 ? (
                <p className="text-muted-foreground type-body">
                  {t.workflows.noRuns}
                </p>
              ) : (
                <div className="space-y-2">
                  {runs.map((run) => (
                    <Link
                      key={run.run_id}
                      href={`/workspace/workflows/${encodeURIComponent(workflow_name)}/runs/${encodeURIComponent(run.run_id)}`}
                      className="hover:bg-muted/50 flex items-center justify-between rounded-md border p-3"
                    >
                      <div className="min-w-0">
                        <p className="type-body truncate font-mono">
                          {run.run_id}
                        </p>
                        {run.error && (
                          <p className="text-destructive type-body truncate">
                            {run.error}
                          </p>
                        )}
                      </div>
                      <div className="ml-3 flex shrink-0 items-center gap-2">
                        {run.model_name && (
                          <Badge
                            variant="secondary"
                            title={t.workflows.modelLabel}
                          >
                            {run.model_name}
                          </Badge>
                        )}
                        <Badge variant="secondary">
                          v{run.definition_version ?? "-"}
                        </Badge>
                        <Badge variant="outline">{run.status}</Badge>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* YAML preview */}
          <Card>
            <CardHeader>
              <CardTitle>{t.workflows.yamlDefinition}</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="bg-muted type-body max-h-96 overflow-auto rounded-md p-4">
                {workflow.yaml_content}
              </pre>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Visibility change dialog */}
      <Dialog
        open={visibilityDialogOpen}
        onOpenChange={setVisibilityDialogOpen}
      >
        <DialogContent>
          {confirmingDowngrade ? (
            <>
              <DialogHeader>
                <DialogTitle>{t.workflows.downgradeConfirmTitle}</DialogTitle>
                <DialogDescription>
                  {t.workflows.downgradeConfirmDescription}
                </DialogDescription>
              </DialogHeader>
              {workflow && (
                <VisibilityImpactPanel
                  resourceId={workflow.resource_id ?? workflow.name}
                  currentVisibility={workflow.visibility}
                  targetVisibility={targetVisibility}
                  onCascadeChange={setCascadeDowngrade}
                />
              )}
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setConfirmingDowngrade(false)}
                >
                  {t.common.cancel}
                </Button>
                <Button
                  onClick={handleConfirmDowngrade}
                  disabled={submittingApplication}
                >
                  {submittingApplication
                    ? t.workflows.submitting
                    : t.workflows.confirm}
                </Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle>{t.workflows.applyVisibility}</DialogTitle>
                <DialogDescription>
                  {t.workflows.applyVisibilityDescription}
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>{t.workflows.currentTargetVisibility}</Label>
                  <p className="text-muted-foreground type-body">
                    {workflow.visibility}
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="target-visibility">
                    {t.workflows.targetVisibility}
                  </Label>
                  <Select
                    value={targetVisibility}
                    onValueChange={setTargetVisibility}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="private">
                        {t.workflows.private}
                      </SelectItem>
                      <SelectItem value="department">
                        {t.workflows.department}
                      </SelectItem>
                      <SelectItem value="public">
                        {t.workflows.public}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {classifyVisibilityChange(
                  workflow.visibility,
                  targetVisibility,
                ) === "upgrade" && (
                  <p className="text-muted-foreground type-body">
                    {t.workflows.visibilityUpgradeHint}
                  </p>
                )}
                {classifyVisibilityChange(
                  workflow.visibility,
                  targetVisibility,
                ) === "downgrade" && (
                  <p className="text-muted-foreground type-body">
                    {t.workflows.visibilityDowngradeHint}
                  </p>
                )}
                {classifyVisibilityChange(
                  workflow.visibility,
                  targetVisibility,
                ) !== "downgrade" && (
                  <div className="space-y-2">
                    <Label htmlFor="reason">{t.workflows.reason}</Label>
                    <Textarea
                      id="reason"
                      placeholder={t.workflows.reasonPlaceholder}
                      value={visibilityReason}
                      onChange={(e) => setVisibilityReason(e.target.value)}
                      rows={3}
                    />
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setVisibilityDialogOpen(false)}
                >
                  {t.common.cancel}
                </Button>
                <Button
                  onClick={handleSubmitVisibility}
                  disabled={
                    submittingApplication ||
                    classifyVisibilityChange(
                      workflow.visibility,
                      targetVisibility,
                    ) === "unchanged" ||
                    (classifyVisibilityChange(
                      workflow.visibility,
                      targetVisibility,
                    ) === "upgrade" &&
                      !visibilityReason.trim())
                  }
                >
                  {submittingApplication
                    ? t.workflows.submitting
                    : t.workflows.submit}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Run dialog */}
      <Dialog open={runDialogOpen} onOpenChange={setRunDialogOpen}>
        <DialogContent className="flex max-h-[calc(100dvh-2rem)] flex-col sm:max-w-xl">
          <DialogHeader className="shrink-0">
            <DialogTitle>{t.workflows.runDialog}</DialogTitle>
            <DialogDescription>
              {t.workflows.runDialogDescription}
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-y-auto py-4 pr-1">
            <div className="space-y-4">
              {Object.entries(workflow.inputs)
                .filter(
                  ([key]) =>
                    !["code_package_source", "upload_dir"].includes(key),
                )
                .map(([key, param]) => (
                  <div key={key} className="space-y-2">
                    <Label htmlFor={`input-${key}`}>
                      {key}
                      {param.required && (
                        <span className="text-destructive ml-1">*</span>
                      )}
                    </Label>
                    {param.description && (
                      <p className="text-muted-foreground type-body">
                        {param.description}
                      </p>
                    )}
                    <Input
                      id={`input-${key}`}
                      placeholder={
                        param.default !== undefined
                          ? `${t.workflows.defaultPrefix}${JSON.stringify(param.default)}`
                          : t.workflows.enterInput(key)
                      }
                      value={inputValues[key] ?? ""}
                      onChange={(e) =>
                        setInputValues((prev) => ({
                          ...prev,
                          [key]: e.target.value,
                        }))
                      }
                    />
                  </div>
                ))}
              {Object.keys(workflow.inputs).length === 0 && (
                <p className="text-muted-foreground type-body">
                  {t.workflows.noInputs}
                </p>
              )}
              <div className="space-y-2">
                <Label htmlFor="run-model">{t.workflows.modelLabel}</Label>
                <Select
                  value={selectedModel}
                  onValueChange={(value) =>
                    setSelectedModel(value === "__system__" ? "" : value)
                  }
                >
                  <SelectTrigger id="run-model">
                    <SelectValue placeholder={t.workflows.followSystemModel} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__system__">
                      {t.workflows.followSystemModel}
                    </SelectItem>
                    {models.map((model) => (
                      <SelectItem key={model.name} value={model.name}>
                        {model.display_name || model.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>源码 ZIP 与资料附件</Label>
                <div className="border-border/70 bg-muted/20 rounded-lg border p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="type-body font-medium">
                        {t.workflows.addFiles}
                      </p>
                      <p className="text-muted-foreground type-body">
                        {t.workflows.fileSelectionHint}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <PlusIcon className="mr-1.5 size-4" />
                      {t.workflows.addFiles}
                    </Button>
                  </div>
                </div>
                <input
                  ref={fileInputRef}
                  data-testid="workflow-file-input"
                  type="file"
                  multiple
                  className="sr-only"
                  onChange={handleFilesSelected}
                />
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>{t.workflows.selectedFiles}</Label>
                    <span className="text-muted-foreground type-body">
                      {t.workflows.fileCount(runFiles.length)}
                    </span>
                  </div>
                  {runFiles.length === 0 ? (
                    <p className="text-muted-foreground bg-muted/20 type-body rounded-md border border-dashed p-3 text-center">
                      {t.workflows.noSelectedFiles}
                    </p>
                  ) : (
                    <ul className="divide-border max-h-56 overflow-y-auto rounded-md border sm:max-h-60">
                      {runFiles.map((file) => (
                        <li
                          key={`${file.name}-${file.lastModified}`}
                          className="odd:bg-muted/20 flex items-center justify-between gap-3 px-3 py-2 first:rounded-t-md last:rounded-b-md"
                        >
                          <span
                            className="type-body min-w-0 truncate"
                            title={file.name}
                          >
                            {file.name}
                          </span>
                          <Button
                            type="button"
                            variant="ghost"
                            aria-label={t.workflows.removeFile(file.name)}
                            onClick={() =>
                              setRunFiles((current) =>
                                current.filter(
                                  (currentFile) =>
                                    currentFile.name !== file.name,
                                ),
                              )
                            }
                          >
                            <XIcon className="size-4" />
                          </Button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                {runFiles.some((file) =>
                  file.name.toLowerCase().endsWith(".zip"),
                ) && (
                  <p className="text-muted-foreground type-body">
                    源码包已就绪，提交后将安全展开并仅授权本次运行读取。
                  </p>
                )}
              </div>
            </div>
          </div>
          <DialogFooter className="shrink-0 border-t pt-4">
            <Button variant="outline" onClick={() => setRunDialogOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              onClick={handleRun}
              disabled={runWorkflowMutation.isPending}
            >
              {runWorkflowMutation.isPending
                ? t.workflows.starting
                : t.workflows.run}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
