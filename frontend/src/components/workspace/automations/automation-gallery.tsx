"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/core/i18n/hooks";

import { AutomationList } from "./automation-list";
import { AutomationTemplateGallery } from "./automation-template-gallery";

export function AutomationGallery() {
  const { t } = useI18n();

  return (
    <div className="flex h-full flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t.automations.title}</h1>
          <p className="text-muted-foreground">{t.automations.description}</p>
        </div>
        <button className="bg-primary text-primary-foreground hover:bg-primary/90 rounded-md px-4 py-2">
          {t.automations.create}
        </button>
      </div>

      <Tabs defaultValue="templates" className="flex-1">
        <TabsList>
          <TabsTrigger value="templates">{t.automations.templates}</TabsTrigger>
          <TabsTrigger value="my-automations">
            {t.automations.myAutomations}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="templates" className="flex-1">
          <AutomationTemplateGallery />
        </TabsContent>

        <TabsContent value="my-automations" className="flex-1">
          <AutomationList />
        </TabsContent>
      </Tabs>
    </div>
  );
}
