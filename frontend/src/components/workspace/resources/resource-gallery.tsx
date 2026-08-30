"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/core/i18n/hooks";

import { ConnectorList } from "./connector-list";
import { ExpertList } from "./expert-list";
import { SkillList } from "./skill-list";

export function ResourceGallery() {
  const { t } = useI18n();

  return (
    <div className="workbench-resource-surface flex h-full flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">{t.resources.title}</h1>
        <p className="text-muted-foreground">{t.resources.description}</p>
      </div>

      <Tabs defaultValue="experts" className="flex-1">
        <TabsList>
          <TabsTrigger value="experts">{t.resources.experts}</TabsTrigger>
          <TabsTrigger value="skills">{t.resources.skills}</TabsTrigger>
          <TabsTrigger value="connectors">{t.resources.connectors}</TabsTrigger>
        </TabsList>

        <TabsContent value="experts" className="flex-1">
          <ExpertList />
        </TabsContent>

        <TabsContent value="skills" className="flex-1">
          <SkillList />
        </TabsContent>

        <TabsContent value="connectors" className="flex-1">
          <ConnectorList />
        </TabsContent>
      </Tabs>
    </div>
  );
}
