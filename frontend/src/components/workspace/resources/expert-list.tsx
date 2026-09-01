"use client";

import {
  BotIcon,
  PlusIcon,
  SearchIcon,
  UploadIcon,
  StarIcon,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AgentCard } from "@/components/workspace/agents/agent-card";
import { useAgents } from "@/core/agents";
import { importAgent } from "@/core/agents/api";
import { useI18n } from "@/core/i18n/hooks";

export function ExpertList() {
  const { t } = useI18n();
  const { agents, isLoading, refetch } = useAgents();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState("");
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const filteredAgents = useMemo(
    () =>
      agents.filter(
        (agent) =>
          (!favoritesOnly || agent.is_favorited) &&
          (!search.trim() ||
            `${agent.name} ${agent.description ?? ""}`
              .toLowerCase()
              .includes(search.toLowerCase())),
      ),
    [agents, favoritesOnly, search],
  );

  async function handleImport(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      await importAgent(file);
      await refetch();
      toast.success(t.agents.importSuccess);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      event.target.value = "";
    }
  }

  if (isLoading) {
    return (
      <div className="text-muted-foreground type-body flex h-40 items-center justify-center">
        {t.common.loading}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="relative min-w-48 flex-1">
          <SearchIcon className="text-muted-foreground absolute top-1/2 left-2.5 h-4 w-4 -translate-y-1/2" />
          <Input
            className="pl-8"
            placeholder={`${t.agents.title}...`}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <Button
          variant={favoritesOnly ? "default" : "outline"}
          onClick={() => setFavoritesOnly((value) => !value)}
        >
          <StarIcon className="mr-1.5 h-4 w-4" />
          {favoritesOnly ? t.common.showAll : t.common.favoritesOnly}
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".zip"
          className="hidden"
          onChange={handleImport}
        />
        <Button variant="outline" onClick={() => fileInputRef.current?.click()}>
          <UploadIcon className="mr-1.5 h-4 w-4" />
          {t.common.import}
        </Button>
        <Button asChild>
          <Link href="/workspace/capabilities/experts/new">
            <PlusIcon className="mr-1.5 h-4 w-4" />
            {t.agents.newAgent}
          </Link>
        </Button>
      </div>
      {agents.length > 0 && filteredAgents.length > 0 ? (
        <div className="workbench-resource-grid grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filteredAgents.map((agent) => (
            <AgentCard key={agent.name} agent={agent} />
          ))}
        </div>
      ) : agents.length > 0 ? (
        <div className="text-muted-foreground flex h-48 flex-col items-center justify-center gap-2 text-center">
          <BotIcon className="h-7 w-7" />
          <p>{t.settings.skills.noResults}</p>
        </div>
      ) : (
        <div className="flex h-64 flex-col items-center justify-center gap-3 text-center">
          <BotIcon className="text-muted-foreground h-7 w-7" />
          <p className="font-medium">{t.agents.emptyTitle}</p>
          <p className="text-muted-foreground type-body">
            {t.agents.emptyDescription}
          </p>
          <Button asChild variant="outline">
            <Link href="/workspace/capabilities/experts/new">
              <PlusIcon className="mr-1.5 h-4 w-4" />
              {t.agents.newAgent}
            </Link>
          </Button>
        </div>
      )}
    </div>
  );
}
