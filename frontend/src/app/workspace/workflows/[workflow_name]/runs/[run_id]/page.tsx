"use client";

import { ArrowLeftIcon, ChevronDownIcon, DownloadIcon } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { NodeDetailPanel } from "@/components/workspace/workflows/node-detail";
import { RunGraph } from "@/components/workspace/workflows/run-graph";
import { WorkspaceBreadcrumb } from "@/components/workspace/workspace-breadcrumb";
import { fetch as apiFetch } from "@/core/api/fetcher";
import { useI18n } from "@/core/i18n/hooks";
import {
  useRunArtifacts,
  useRunArtifactContent,
  useRunStatus,
  useSubmitWorkflowCommand,
  useWorkflow,
  workflowRunArtifactDownloadUrl,
  workflowRunRecordDownloadUrl,
} from "@/core/workflows";
import type { RunArtifact } from "@/core/workflows";
import { formatWorkflowRunError } from "@/core/workflows/errors";
import { cn } from "@/lib/utils";

function statusClass(status: string) {
  if (status === "completed") return "text-green-600 dark:text-green-400";
  if (status === "failed" || status === "cancelled") return "text-destructive";
  if (status === "running") return "text-blue-600 dark:text-blue-400";
  return "text-muted-foreground";
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

const PREVIEWABLE = /\.(md|json|svg|txt|yaml|yml|log|xml|html)$/i;

function prettyContent(path: string, content: string): string {
  if (path.toLowerCase().endsWith(".json")) {
    try {
      return JSON.stringify(JSON.parse(content), null, 2);
    } catch {
      return content;
    }
  }
  return content;
}

export default function WorkflowRunDetailPage() {
  const router = useRouter();
  const { workflow_name, run_id } = useParams<{
    workflow_name: string;
    run_id: string;
  }>();
  const { workflow } = useWorkflow(workflow_name);
  const { runStatus, isLoading, error, fallbackPolling } = useRunStatus(
    workflow_name,
    run_id,
  );
  const commandMutation = useSubmitWorkflowCommand();
  const { t } = useI18n();
  const {
    artifacts,
    error: artifactsError,
    refetch: refetchArtifacts,
  } = useRunArtifacts(workflow_name, run_id);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [eventsOpen, setEventsOpen] = useState(false);
  const { data: previewContent, isLoading: previewLoading } =
    useRunArtifactContent(workflow_name, run_id, selectedPath);
  const wasTerminal = useRef(false);

  const terminal = ["completed", "failed", "cancelled"].includes(
    runStatus?.status ?? "",
  );
  useEffect(() => {
    if (terminal && !wasTerminal.current) void refetchArtifacts();
    wasTerminal.current = terminal;
  }, [refetchArtifacts, terminal]);

  async function submitCommand(type: "resume" | "cancel") {
    try {
      await commandMutation.mutateAsync({
        name: workflow_name,
        runId: run_id,
        command: { command_id: crypto.randomUUID(), type, payload: {} },
      });
      toast.success(t.workflows.commandSubmitted);
    } catch (commandError) {
      toast.error(
        commandError instanceof Error
          ? commandError.message
          : String(commandError),
      );
    }
  }

  async function downloadArtifact(artifact: RunArtifact) {
    try {
      const res = await apiFetch(
        workflowRunArtifactDownloadUrl(workflow_name, run_id, artifact.path),
      );
      if (!res.ok) throw new Error("HTTP " + res.status);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = artifact.path.split("/").pop() ?? "artifact";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (downloadError) {
      toast.error(
        downloadError instanceof Error
          ? downloadError.message
          : String(downloadError),
      );
    }
  }

  async function downloadRecord(format: "jsonl" | "md") {
    try {
      const res = await apiFetch(
        workflowRunRecordDownloadUrl(workflow_name, run_id, format),
      );
      if (!res.ok) throw new Error("HTTP " + res.status);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `run_${run_id}.${format}`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (recordError) {
      toast.error(
        recordError instanceof Error
          ? recordError.message
          : String(recordError),
      );
    }
  }

  if (isLoading)
    return (
      <div className="text-muted-foreground flex size-full items-center justify-center text-sm">
        {t.common.loading}
      </div>
    );
  if (error || !runStatus)
    return (
      <div className="flex size-full flex-col items-center justify-center gap-4">
        <p className="text-destructive text-sm">
          {error?.message ?? t.workflows.runNotFound}
        </p>
        <Button
          variant="outline"
          onClick={() =>
            router.push(
              `/workspace/workflows/${encodeURIComponent(workflow_name)}`,
            )
          }
        >
          {t.workflows.backToWorkflows}
        </Button>
      </div>
    );

  const mayResume = runStatus.status === "paused";
  const mayCancel =
    runStatus.status === "queued" ||
    runStatus.status === "running" ||
    runStatus.status === "paused";

  return (
    <div className="flex size-full flex-col">
      <WorkspaceBreadcrumb />
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() =>
              router.push(
                `/workspace/workflows/${encodeURIComponent(workflow_name)}`,
              )
            }
          >
            <ArrowLeftIcon className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-xl font-semibold">
              {workflow?.name ?? workflow_name}
            </h1>
            <p className="text-muted-foreground text-sm">
              {t.workflows.runId}
              {runStatus.run_id}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">
            {t.workflows.definitionVersion}: v
            {runStatus.definition_version ?? "-"}
          </Badge>
          {runStatus.model_name && (
            <Badge variant="secondary" title={t.workflows.modelLabel}>
              {runStatus.model_name}
            </Badge>
          )}
          <Badge variant="outline" className={statusClass(runStatus.status)}>
            {runStatus.status}
          </Badge>
          {mayResume && (
            <Button
              onClick={() => void submitCommand("resume")}
              disabled={commandMutation.isPending}
            >
              {t.workflows.resume}
            </Button>
          )}
          {mayCancel && (
            <Button
              variant="destructive"
              onClick={() => void submitCommand("cancel")}
              disabled={commandMutation.isPending}
            >
              {t.workflows.cancelRun}
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => void downloadRecord("md")}
            title="运行记录 (Markdown)"
          >
            <DownloadIcon className="h-4 w-4" />
            MD
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void downloadRecord("jsonl")}
            title="事件日志 (JSONL)"
          >
            <DownloadIcon className="h-4 w-4" />
            JSONL
          </Button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-6xl space-y-6">
          {fallbackPolling && (
            <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-300">
              {t.workflows.streamFallback}
            </p>
          )}
          {runStatus.error && (
            <p className="text-destructive rounded-md border border-red-200 bg-red-50 p-3 text-sm dark:border-red-800 dark:bg-red-950/50">
              {formatWorkflowRunError(runStatus.error, runStatus.error_code)}
            </p>
          )}
          {workflow &&
            runStatus.definition_version != null &&
            workflow.version !== String(runStatus.definition_version) && (
              <p className="text-muted-foreground bg-muted/40 rounded-md border p-3 text-xs">
                {t.workflows.definitionMismatchHint}
              </p>
            )}
          <Card className="overflow-hidden">
            <CardHeader className="border-b">
              <CardTitle>{t.workflows.runStatus}</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {workflow ? (
                <div className="flex h-[480px]">
                  <div className="min-w-0 flex-1">
                    <RunGraph
                      workflow={workflow}
                      runStatus={runStatus}
                      selectedNodeId={selectedNodeId}
                      onSelect={setSelectedNodeId}
                    />
                  </div>
                  <div className="border-border bg-card/50 w-80 shrink-0 border-l">
                    <NodeDetailPanel
                      node={
                        workflow.nodes.find(
                          (node) => node.id === selectedNodeId,
                        ) ?? null
                      }
                      step={
                        selectedNodeId
                          ? (runStatus.steps?.[selectedNodeId] ?? null)
                          : null
                      }
                      progress={
                        selectedNodeId
                          ? runStatus.action_progress?.[selectedNodeId]
                          : undefined
                      }
                      tokens={
                        selectedNodeId
                          ? runStatus.action_tokens?.[selectedNodeId]
                          : undefined
                      }
                    />
                  </div>
                </div>
              ) : (
                <div className="text-muted-foreground flex h-48 items-center justify-center text-sm">
                  {t.common.loading}
                </div>
              )}
            </CardContent>
          </Card>
          <Card>
            <Collapsible open={eventsOpen} onOpenChange={setEventsOpen}>
              <CardHeader className="p-0">
                <CollapsibleTrigger asChild>
                  <button
                    type="button"
                    className="flex w-full items-center justify-between px-6 py-4 text-left"
                  >
                    <CardTitle>{t.workflows.eventTimeline}</CardTitle>
                    <ChevronDownIcon
                      className={cn(
                        "text-muted-foreground h-4 w-4 transition-transform",
                        eventsOpen && "rotate-180",
                      )}
                    />
                  </button>
                </CollapsibleTrigger>
              </CardHeader>
              <CollapsibleContent>
                <CardContent>
                  <ol className="space-y-2">
                    {(runStatus.events ?? []).map((event) => (
                      <li
                        key={event.seq}
                        className="rounded-md border p-2 text-sm"
                      >
                        <span className="text-muted-foreground mr-2 font-mono">
                          #{event.seq}
                        </span>
                        {event.type}
                        {typeof event.payload.node_id === "string" && (
                          <span className="text-muted-foreground ml-2 font-mono text-xs">
                            {event.payload.node_id}
                          </span>
                        )}
                        {event.type === "edge_selected" &&
                          typeof event.payload.from === "string" &&
                          typeof event.payload.to === "string" && (
                            <span className="text-muted-foreground ml-2 font-mono text-xs">
                              {event.payload.from} → {event.payload.to}
                            </span>
                          )}
                      </li>
                    ))}
                  </ol>
                </CardContent>
              </CollapsibleContent>
            </Collapsible>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t.workflows.artifacts}</CardTitle>
            </CardHeader>
            <CardContent>
              {artifactsError ? (
                <p className="text-destructive text-sm">
                  {t.workflows.artifactLoadError}
                </p>
              ) : artifacts.length === 0 ? (
                <p className="text-muted-foreground text-sm">
                  {t.workflows.noArtifacts}
                </p>
              ) : (
                <ul className="space-y-2">
                  {artifacts.map((artifact) => {
                    const name =
                      artifact.path.split("/").pop() ?? artifact.path;
                    const previewable = PREVIEWABLE.test(name);
                    return (
                      <li key={artifact.path} className="rounded-md border p-3">
                        <div className="flex items-center justify-between gap-2">
                          <div className="min-w-0">
                            <p className="truncate font-mono text-sm">{name}</p>
                            <p className="text-muted-foreground text-xs">
                              {t.workflows.artifactSize}:{" "}
                              {formatSize(artifact.size)}
                            </p>
                          </div>
                          <div className="flex shrink-0 gap-2">
                            {previewable && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() =>
                                  setSelectedPath(
                                    selectedPath === artifact.path
                                      ? null
                                      : artifact.path,
                                  )
                                }
                              >
                                {t.common.preview}
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              onClick={() => void downloadArtifact(artifact)}
                            >
                              <DownloadIcon className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                        {selectedPath === artifact.path && (
                          <pre className="bg-muted mt-2 max-h-96 overflow-auto rounded p-2 text-xs whitespace-pre-wrap">
                            {previewLoading
                              ? t.common.loading
                              : prettyContent(
                                  artifact.path,
                                  previewContent ?? "",
                                )}
                          </pre>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
