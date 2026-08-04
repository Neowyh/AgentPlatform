"use client";

import { ChevronDownIcon } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useI18n } from "@/core/i18n/hooks";
import type { StepStatus, WorkflowNode } from "@/core/workflows";
import { cn } from "@/lib/utils";

const MAX_OUTPUT_CHARS = 8000;

function statusClass(status: string) {
  if (status === "completed")
    return "border-emerald-500 text-emerald-700 dark:text-emerald-400";
  if (status === "failed")
    return "border-red-500 text-red-700 dark:text-red-400";
  if (status === "running")
    return "border-blue-500 text-blue-700 dark:text-blue-400";
  return "border-border text-muted-foreground";
}

function formatDuration(step: StepStatus | null | undefined): string | null {
  if (!step?.started_at || !step.finished_at) return null;
  const millis =
    new Date(step.finished_at).getTime() - new Date(step.started_at).getTime();
  if (!Number.isFinite(millis) || millis < 0) return null;
  if (millis < 1000) return `${millis}ms`;
  if (millis < 60000) return `${(millis / 1000).toFixed(1)}s`;
  return `${Math.floor(millis / 60000)}m ${Math.floor((millis % 60000) / 1000)}s`;
}

function formatOutput(output: unknown): string {
  let text: string;
  try {
    text = JSON.stringify(output, null, 2);
  } catch {
    text = String(output);
  }
  if (text.length <= MAX_OUTPUT_CHARS) return text;
  return `${text.slice(0, MAX_OUTPUT_CHARS)}\n… (truncated)`;
}

export interface NodeDetailPanelProps {
  node: WorkflowNode | null;
  step?: StepStatus | null;
  progress?: string;
  tokens?: string;
}

export function NodeDetailPanel({
  node,
  step,
  progress,
  tokens,
}: NodeDetailPanelProps) {
  const { t } = useI18n();
  const [showOutput, setShowOutput] = useState(false);
  const [showTokens, setShowTokens] = useState(false);

  if (!node) {
    return (
      <div className="text-muted-foreground flex h-full items-center justify-center p-6 text-center text-sm">
        {t.workflows.selectNodeHint}
      </div>
    );
  }

  const duration = formatDuration(step);

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4">
      <div>
        <div className="flex items-center justify-between gap-2">
          <h3 className="truncate text-sm font-semibold">
            {t.workflows.nodeDetailTitle}
          </h3>
          <Badge variant="outline" className="shrink-0 text-xs">
            {node.type}
          </Badge>
        </div>
        <p className="mt-1 font-mono text-sm font-medium">{node.id}</p>
        {node.action?.name && (
          <p className="text-muted-foreground text-xs">
            {node.action.kind}: {node.action.name}
          </p>
        )}
      </div>

      {step && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Badge variant="outline" className={statusClass(step.status)}>
            {step.status}
          </Badge>
          {duration && (
            <span className="text-muted-foreground text-xs">
              {t.workflows.duration}: {duration}
            </span>
          )}
        </div>
      )}

      {step?.error && (
        <div className="text-destructive rounded-md border border-red-200 bg-red-50 p-2 text-xs break-words dark:border-red-800 dark:bg-red-950/50">
          {step.error}
        </div>
      )}

      {progress && <p className="text-muted-foreground text-xs">{progress}</p>}

      {step?.output !== undefined && step.output !== null && (
        <Collapsible open={showOutput} onOpenChange={setShowOutput}>
          <CollapsibleTrigger className="flex w-full items-center justify-between rounded-md border px-3 py-2 text-sm">
            <span>{t.workflows.actionOutput}</span>
            <ChevronDownIcon
              className={cn(
                "h-4 w-4 transition-transform",
                showOutput && "rotate-180",
              )}
            />
          </CollapsibleTrigger>
          <CollapsibleContent>
            <pre className="bg-muted mt-2 max-h-64 overflow-auto rounded-md p-2 text-xs break-words whitespace-pre-wrap">
              {formatOutput(step.output)}
            </pre>
          </CollapsibleContent>
        </Collapsible>
      )}

      {tokens && (
        <Collapsible open={showTokens} onOpenChange={setShowTokens}>
          <CollapsibleTrigger className="flex w-full items-center justify-between rounded-md border px-3 py-2 text-sm">
            <span>{t.workflows.tokenStream}</span>
            <ChevronDownIcon
              className={cn(
                "h-4 w-4 transition-transform",
                showTokens && "rotate-180",
              )}
            />
          </CollapsibleTrigger>
          <CollapsibleContent>
            <pre className="bg-muted mt-2 max-h-64 overflow-auto rounded-md p-2 text-xs break-words whitespace-pre-wrap">
              {tokens}
            </pre>
          </CollapsibleContent>
        </Collapsible>
      )}

      {!step && !progress && !tokens && (
        <p className="text-muted-foreground text-xs">
          {t.workflows.nodeNotStarted}
        </p>
      )}
    </div>
  );
}
