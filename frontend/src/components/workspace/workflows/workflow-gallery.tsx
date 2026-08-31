"use client";

import { PlusIcon, SearchIcon, StarIcon, WorkflowIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/core/i18n/hooks";
import { useWorkflows } from "@/core/workflows";

import { WorkflowCard } from "./workflow-card";

export function WorkflowGallery() {
  const { workflows, isLoading, error } = useWorkflows();
  const { t } = useI18n();
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);

  const filteredWorkflows = useMemo(() => {
    let result = workflows;

    if (showFavoritesOnly) {
      result = result.filter((w) => w.is_favorited);
    }

    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (w) =>
          w.name.toLowerCase().includes(q) ||
          w.description?.toLowerCase().includes(q),
      );
    }

    return result;
  }, [workflows, search, showFavoritesOnly]);

  return (
    <div className="workbench-collection-surface flex size-full flex-col">
      {/* Page header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div>
          <h1 className="type-page-title font-semibold">{t.workflows.title}</h1>
          <p className="text-muted-foreground type-body mt-0.5">
            {t.workflows.description}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <SearchIcon className="text-muted-foreground absolute top-1/2 left-2.5 h-4 w-4 -translate-y-1/2" />
            <Input
              placeholder={`${t.workflows.title}...`}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="type-body h-9 w-48 pl-8"
            />
          </div>
          <Button
            variant={showFavoritesOnly ? "default" : "outline"}
            size="sm"
            onClick={() => setShowFavoritesOnly(!showFavoritesOnly)}
          >
            <StarIcon className="mr-1.5 h-4 w-4" />
            {showFavoritesOnly ? t.common.showAll : t.common.favoritesOnly}
          </Button>
          <Button onClick={() => router.push("/workspace/workflows/new")}>
            <PlusIcon className="mr-1.5 h-4 w-4" />
            {t.workflows.newWorkflow}
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="text-muted-foreground type-body flex h-40 items-center justify-center">
            {t.common.loading}
          </div>
        ) : error ? (
          <div className="text-destructive type-body flex h-40 items-center justify-center">
            {error.message}
          </div>
        ) : workflows.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3 text-center">
            <div className="bg-muted flex h-14 w-14 items-center justify-center rounded-full">
              <WorkflowIcon className="text-muted-foreground h-7 w-7" />
            </div>
            <div>
              <p className="font-medium">{t.workflows.emptyTitle}</p>
              <p className="text-muted-foreground type-body mt-1">
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
          <div className="workbench-collection-grid grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filteredWorkflows.map((workflow) => (
              <WorkflowCard key={workflow.name} workflow={workflow} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
