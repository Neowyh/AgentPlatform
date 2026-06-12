"use client";

import { PlusIcon, WorkflowIcon } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/core/i18n/hooks";
import { useWorkflows } from "@/core/workflows";

import { WorkflowCard } from "./workflow-card";

export function WorkflowGallery() {
  const { workflows, isLoading, error } = useWorkflows();
  const { t } = useI18n();
  const router = useRouter();

  return (
    <div className="flex size-full flex-col">
      {/* Page header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div>
          <h1 className="text-xl font-semibold">{t.workflows.title}</h1>
          <p className="text-muted-foreground mt-0.5 text-sm">
            {t.workflows.description}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={() => router.push("/workspace/workflows/new")}>
            <PlusIcon className="mr-1.5 h-4 w-4" />
            {t.workflows.newWorkflow}
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="text-muted-foreground flex h-40 items-center justify-center text-sm">
            {t.common.loading}
          </div>
        ) : error ? (
          <div className="text-destructive flex h-40 items-center justify-center text-sm">
            {error.message}
          </div>
        ) : workflows.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3 text-center">
            <div className="bg-muted flex h-14 w-14 items-center justify-center rounded-full">
              <WorkflowIcon className="text-muted-foreground h-7 w-7" />
            </div>
            <div>
              <p className="font-medium">{t.workflows.emptyTitle}</p>
              <p className="text-muted-foreground mt-1 text-sm">
                {t.workflows.emptyDescription}
              </p>
            </div>
            <Button
              variant="outline"
              className="mt-2"
              onClick={() => router.push("/workspace/workflows/new")}
            >
              <PlusIcon className="mr-1.5 h-4 w-4" />
              {t.workflows.newWorkflow}
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {workflows.map((workflow) => (
              <WorkflowCard key={workflow.name} workflow={workflow} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
