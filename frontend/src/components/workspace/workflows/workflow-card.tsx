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
import { useDeleteWorkflow } from "@/core/workflows";
import type { WorkflowSummary } from "@/core/workflows";

interface WorkflowCardProps {
  workflow: WorkflowSummary;
}

export function WorkflowCard({ workflow }: WorkflowCardProps) {
  const router = useRouter();
  const deleteWorkflow = useDeleteWorkflow();
  const [deleteOpen, setDeleteOpen] = useState(false);

  function handleClick() {
    router.push(`/workspace/workflows/${workflow.name}`);
  }

  async function handleDelete() {
    try {
      await deleteWorkflow.mutateAsync(workflow.name);
      toast.success("Workflow deleted");
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
                  v{workflow.version}
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
              {workflow.steps_count}{" "}
              {workflow.steps_count === 1 ? "step" : "steps"}
            </Badge>
            {Object.keys(workflow.inputs).length > 0 && (
              <Badge variant="outline" className="text-xs">
                {Object.keys(workflow.inputs).length}{" "}
                {Object.keys(workflow.inputs).length === 1 ? "input" : "inputs"}
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
          >
            <PlayIcon className="mr-1.5 h-3.5 w-3.5" />
            View
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="text-destructive hover:text-destructive h-8 w-8 shrink-0"
            onClick={(e) => {
              e.stopPropagation();
              setDeleteOpen(true);
            }}
          >
            <Trash2Icon className="h-3.5 w-3.5" />
          </Button>
        </CardFooter>
      </Card>

      {/* Delete Confirm */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Workflow</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &quot;{workflow.name}&quot;? This
              action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteOpen(false)}
              disabled={deleteWorkflow.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteWorkflow.isPending}
            >
              {deleteWorkflow.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
