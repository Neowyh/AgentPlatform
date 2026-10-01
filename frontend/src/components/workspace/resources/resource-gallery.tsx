"use client";

import { SearchIcon } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/core/i18n/hooks";

import { PluginGallery } from "../capabilities/plugin-gallery";
import { SkillGallery } from "../capabilities/skill-gallery";

import { ConnectorList } from "./connector-list";
import { ExpertList } from "./expert-list";
import { SkillList } from "./skill-list";

type ResourceTab = "experts" | "skills" | "connectors";

export function ResourceGallery({
  defaultTab = "experts",
}: {
  defaultTab?: ResourceTab;
}) {
  const { t } = useI18n();
  const pathname = usePathname();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const pathTab = pathname.split("/").at(-1) as ResourceTab;
  const activeTab = ["experts", "skills", "connectors"].includes(pathTab)
    ? pathTab
    : defaultTab;

  return (
    <div className="workbench-resource-surface flex h-full flex-col gap-6 p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="type-page-title font-bold">{t.resources.title}</h1>
          <p className="text-muted-foreground">{t.resources.description}</p>
        </div>
        <div className="relative w-full md:w-64">
          <SearchIcon className="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2" />
          <Input
            className="pl-8"
            aria-label={
              activeTab === "connectors"
                ? t.capabilities.searchPlugins
                : t.capabilities.searchSkills
            }
            placeholder={
              activeTab === "connectors"
                ? t.capabilities.searchPlugins
                : t.capabilities.searchSkills
            }
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={(value) =>
          router.push(`/workspace/capabilities/${value}`)
        }
        className="flex-1"
      >
        <TabsList>
          <TabsTrigger value="experts">{t.resources.experts}</TabsTrigger>
          <TabsTrigger value="skills">{t.resources.skills}</TabsTrigger>
          <TabsTrigger value="connectors">{t.resources.connectors}</TabsTrigger>
        </TabsList>

        <TabsContent value="experts" className="flex-1">
          <ExpertList />
        </TabsContent>

        <TabsContent value="skills" className="flex-1">
          <div className="flex flex-col gap-10">
            <SkillList />
            <SkillGallery query={query} />
          </div>
        </TabsContent>

        <TabsContent value="connectors" className="flex-1">
          <div className="flex flex-col gap-10">
            <ConnectorList />
            <PluginGallery query={query} />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
