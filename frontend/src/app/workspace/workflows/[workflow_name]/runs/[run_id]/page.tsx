"use client";

import { ArrowLeftIcon } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { WorkspaceBreadcrumb } from "@/components/workspace/workspace-breadcrumb";
import { useI18n } from "@/core/i18n/hooks";
import {
  useRunStatus,
  useSubmitWorkflowCommand,
  useWorkflow,
} from "@/core/workflows";

function statusClass(status: string) {
  if (status === "completed") return "text-green-600";
  if (status === "failed" || status === "cancelled") return "text-destructive";
  if (status === "running") return "text-blue-600";
  return "text-muted-foreground";
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
    runStatus.status === "queued" || runStatus.status === "running";

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
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          {fallbackPolling && (
            <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              {t.workflows.streamFallback}
            </p>
          )}
          {runStatus.error && (
            <p className="text-destructive rounded-md border border-red-200 bg-red-50 p-3 text-sm">
              {runStatus.error}
            </p>
          )}
          <Card>
            <CardHeader>
              <CardTitle>{t.workflows.runStatus}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {Object.entries(runStatus.steps ?? {}).map(([nodeId, step]) => (
                  <div key={nodeId} className="rounded-md border p-3">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{nodeId}</span>
                      <Badge
                        variant="outline"
                        className={statusClass(step.status)}
                      >
                        {step.status}
                      </Badge>
                    </div>
                    {step.error && (
                      <p className="text-destructive mt-1 text-xs">
                        {step.error}
                      </p>
                    )}
                    {runStatus.action_progress?.[nodeId] && (
                      <p className="text-muted-foreground mt-1 text-sm">
                        {runStatus.action_progress[nodeId]}
                      </p>
                    )}
                    {runStatus.action_tokens?.[nodeId] && (
                      <pre className="bg-muted mt-2 overflow-auto rounded p-2 text-xs whitespace-pre-wrap">
                        {runStatus.action_tokens[nodeId]}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t.workflows.eventTimeline}</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="space-y-2">
                {(runStatus.events ?? []).map((event) => (
                  <li key={event.seq} className="rounded-md border p-2 text-sm">
                    <span className="text-muted-foreground mr-2 font-mono">
                      #{event.seq}
                    </span>
                    {event.type}
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
