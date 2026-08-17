"use client";

import {
  ArrowLeftIcon,
  DownloadIcon,
  EditIcon,
  PlayIcon,
  WorkflowIcon,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
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
  const [visibilityDialogOpen, setVisibilityDialogOpen] = useState(false);
  const [inputValues, setInputValues] = useState<Record<string, string>>({});
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

  if (isLoading) {
    return (
      <div className="flex size-full items-center justify-center">
        <div className="text-muted-foreground text-sm">{t.common.loading}</div>
      </div>
    );
  }

  if (error || !workflow) {
    return (
      <div className="flex size-full flex-col items-center justify-center gap-4">
        <div className="text-destructive text-sm">
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
      if (param.required && !inputValues[key]?.trim()) {
        toast.error(t.workflows.requiredMissing(key));
        return;
      }
    }

    const inputs: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(inputValues)) {
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
              <h1 className="text-xl font-semibold">{workflow.name}</h1>
              {workflow.description && (
                <p className="text-muted-foreground mt-0.5 text-sm">
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
                <p className="text-muted-foreground text-sm">
                  {t.workflows.noSteps}
                </p>
              ) : (
                <div className="space-y-3">
                  {workflow.steps.map((step, index) => (
                    <div
                      key={step.id}
                      className="flex items-start gap-3 rounded-md border p-3"
                    >
                      <div className="bg-muted flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-medium">
                        {index + 1}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{step.id}</span>
                          <Badge variant="outline" className="text-xs">
                            {step.type}
                          </Badge>
                          {step.action?.name && (
                            <Badge variant="secondary" className="text-xs">
                              {step.action.name}
                            </Badge>
                          )}
                        </div>
                        {typeof step.action?.params?.prompt === "string" && (
                          <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
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
                        <span className="font-mono text-sm font-medium">
                          {key}
                        </span>
                        {param.description && (
                          <p className="text-muted-foreground text-xs">
                            {param.description}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">
                          {param.type}
                        </Badge>
                        {param.required && (
                          <Badge variant="destructive" className="text-xs">
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
                <p className="text-muted-foreground text-sm">
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
                        <p className="truncate font-mono text-sm">
                          {run.run_id}
                        </p>
                        {run.error && (
                          <p className="text-destructive truncate text-xs">
                            {run.error}
                          </p>
                        )}
                      </div>
                      <div className="ml-3 flex shrink-0 items-center gap-2">
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
              <pre className="bg-muted max-h-96 overflow-auto rounded-md p-4 text-sm">
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
                  <p className="text-muted-foreground text-sm">
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
                  <p className="text-muted-foreground text-sm">
                    {t.workflows.visibilityUpgradeHint}
                  </p>
                )}
                {classifyVisibilityChange(
                  workflow.visibility,
                  targetVisibility,
                ) === "downgrade" && (
                  <p className="text-muted-foreground text-sm">
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
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t.workflows.runDialog}</DialogTitle>
            <DialogDescription>
              {t.workflows.runDialogDescription}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {Object.entries(workflow.inputs).map(([key, param]) => (
              <div key={key} className="space-y-2">
                <Label htmlFor={`input-${key}`}>
                  {key}
                  {param.required && (
                    <span className="text-destructive ml-1">*</span>
                  )}
                </Label>
                {param.description && (
                  <p className="text-muted-foreground text-xs">
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
              <p className="text-muted-foreground text-sm">
                {t.workflows.noInputs}
              </p>
            )}
          </div>
          <DialogFooter>
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
