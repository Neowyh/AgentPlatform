"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/core/i18n/hooks";
import { useKnowledgeBases } from "@/core/library";

import { EvalCaseList } from "./eval-case-list";
import { EvaluationPanel } from "./evaluation-panel";
import { RetrievalTestPanel } from "./retrieval-test-panel";
import { RevisionList } from "./revision-list";

export function KnowledgeQualityPanel() {
  const { t } = useI18n();
  const { knowledgeBases } = useKnowledgeBases();
  const requestedId = useSearchParams().get("kb") ?? undefined;
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] =
    useState<string>();
  const selectedId =
    selectedKnowledgeBaseId ??
    knowledgeBases.find((kb) => kb.id === requestedId)?.id ??
    knowledgeBases[0]?.id;
  const selectedKnowledgeBase = knowledgeBases.find(
    (kb) => kb.id === selectedId,
  );

  return (
    <div className="workbench-collection-surface flex h-full flex-col gap-6 p-6">
      <div>
        <h1 className="type-page-title font-bold">{t.library.quality.title}</h1>
        <p className="text-muted-foreground">{t.library.quality.description}</p>
      </div>

      <Select value={selectedId} onValueChange={setSelectedKnowledgeBaseId}>
        <SelectTrigger
          aria-label={t.library.quality.selectKnowledgeBase}
          className="w-64"
        >
          <SelectValue placeholder={t.library.quality.selectKnowledgeBase} />
        </SelectTrigger>
        <SelectContent>
          {knowledgeBases.map((kb) => (
            <SelectItem key={kb.id} value={kb.id}>
              {kb.display_name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Tabs defaultValue="revisions" className="flex-1">
        <TabsList>
          <TabsTrigger value="revisions">{t.library.revisions}</TabsTrigger>
          <TabsTrigger value="eval-cases">{t.library.evalCases}</TabsTrigger>
          <TabsTrigger value="retrieval-test">
            {t.library.retrievalTestTab}
          </TabsTrigger>
          <TabsTrigger value="evaluation">{t.library.evaluation}</TabsTrigger>
        </TabsList>

        <TabsContent value="revisions" className="flex-1">
          <RevisionList
            knowledgeBaseId={selectedId}
            canModify={selectedKnowledgeBase?.can_modify}
          />
        </TabsContent>

        <TabsContent value="eval-cases" className="flex-1">
          <EvalCaseList
            knowledgeBaseId={selectedId}
            canModify={selectedKnowledgeBase?.can_modify}
          />
        </TabsContent>

        <TabsContent value="retrieval-test" className="flex-1">
          <RetrievalTestPanel
            knowledgeBaseId={selectedId}
            canModify={selectedKnowledgeBase?.can_modify}
          />
        </TabsContent>

        <TabsContent value="evaluation" className="flex-1">
          <EvaluationPanel
            knowledgeBaseId={selectedId}
            canModify={selectedKnowledgeBase?.can_modify}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
