"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/core/i18n/hooks";
import { useKnowledgeBases } from "@/core/library";

import { DocumentList } from "./document-list";
import { KnowledgeBaseList } from "./knowledge-base-list";

export function LibraryGallery() {
  const { t } = useI18n();
  const { knowledgeBases } = useKnowledgeBases();
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] =
    useState<string>();
  const [activeTab, setActiveTab] = useState("documents");
  const selectedId = selectedKnowledgeBaseId ?? knowledgeBases[0]?.id;

  function handleSelectKnowledgeBase(id: string) {
    setSelectedKnowledgeBaseId(id);
    setActiveTab("documents");
  }

  return (
    <div className="workbench-collection-surface flex h-full flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="type-page-title font-bold">{t.library.title}</h1>
          <p className="text-muted-foreground">{t.library.description}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" asChild>
            <Link
              href={
                selectedId
                  ? `/workspace/library/quality?kb=${encodeURIComponent(selectedId)}`
                  : "/workspace/library/quality"
              }
            >
              {t.library.qualityEntry}
            </Link>
          </Button>
          <button
            type="button"
            className="bg-primary text-primary-foreground hover:bg-primary/90 rounded-md px-4 py-2"
            onClick={() =>
              document
                .querySelector<HTMLInputElement>(
                  'input[data-knowledge-upload="true"]',
                )
                ?.click()
            }
          >
            {t.library.upload}
          </button>
        </div>
      </div>

      <div className="relative">
        <input
          type="text"
          placeholder={t.library.search}
          className="bg-background w-full rounded-md border px-4 py-2 pl-10"
        />
        <svg
          className="text-muted-foreground absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1">
        <TabsList>
          <TabsTrigger value="documents">{t.library.documents}</TabsTrigger>
          <TabsTrigger value="knowledge-bases">
            {t.library.knowledgeBases}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="documents" className="flex-1">
          <DocumentList knowledgeBaseId={selectedId} />
        </TabsContent>

        <TabsContent value="knowledge-bases" className="flex-1">
          <KnowledgeBaseList
            selectedId={selectedId}
            onSelect={handleSelectKnowledgeBase}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
