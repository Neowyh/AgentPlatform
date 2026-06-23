"use client";

import { PlayIcon, Trash2Icon, WorkflowIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
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
import { useI18n } from "@/core/i18n/hooks";
import { useDeleteWorkflow } from "@/core/workflows";
import type { WorkflowSummary } from "@/core/workflows";

interface WorkflowCardProps {
  workflow: WorkflowSummary;
}

export function WorkflowCard({ workflow }: WorkflowCardProps) {
  const router = useRouter();
  const deleteWorkflow = useDeleteWorkflow();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const { t } = useI18n();

  function handleClick() {
    router.push(`/workspace/workflows/${workflow.name}`);
  }

  async function handleDelete() {
    try {
      await deleteWorkflow.mutateAsync(workflow.name);
      toast.success(t.workflows.deleteSuccess);
      setDeleteOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <>
      <Card
        className="group flex cursor-pointer flex-col transition-shadow hover:shadow-md"
        onClick={handleClick}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            handleClick();
          }
        }}
        data-testid="workflow-card"
      >
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <div className="bg-primary/10 text-primary flex h-9 w-9 shrink-0 items-center justify-center rounded-lg">
                <WorkflowIcon className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <CardTitle className="truncate text-base">
                  {workflow.name}
                </CardTitle>
                <Badge variant="secondary" className="mt-0.5 text-xs">
                  v{workflow.version ?? t.workflows.unknown}
                </Badge>
              </div>
            </div>
          </div>
          {workflow.description && (
            <CardDescription className="mt-2 line-clamp-2 text-sm">
              {workflow.description}
            </CardDescription>
          )}
        </CardHeader>

        <CardContent className="pt-0 pb-3">
          <div className="flex flex-wrap gap-1">
            <Badge variant="outline" className="text-xs">
              {t.workflows.steps(workflow.steps_count ?? 0)}
            </Badge>
            {workflow.inputs && Object.keys(workflow.inputs).length > 0 && (
              <Badge variant="outline" className="text-xs">
                {t.workflows.inputs(Object.keys(workflow.inputs).length)}
              </Badge>
            )}
          </div>
        </CardContent>

        <CardFooter className="mt-auto flex items-center justify-between gap-2 pt-3">
          <Button
            size="sm"
            className="flex-1"
            onClick={(e) => {
              e.stopPropagation();
              handleClick();
            }}
            data-testid="workflow-run-button"
          >
            <PlayIcon className="mr-1.5 h-3.5 w-3.5" />
            {t.workflows.view}
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="text-destructive hover:text-destructive h-8 w-8 shrink-0"
            onClick={(e) => {
              e.stopPropagation();
              setDeleteOpen(true);
            }}
            data-testid="workflow-delete-button"
          >
            <Trash2Icon className="h-3.5 w-3.5" />
          </Button>
        </CardFooter>
      </Card>

      {/* Delete Confirm */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t.workflows.deleteTitle}</DialogTitle>
            <DialogDescription>
              {t.workflows.deleteConfirm(workflow.name)}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteOpen(false)}
              disabled={deleteWorkflow.isPending}
            >
              {t.common.cancel}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteWorkflow.isPending}
            >
              {deleteWorkflow.isPending
                ? t.workflows.deleting
                : t.common.delete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
