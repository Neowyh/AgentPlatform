"use client";

import {
  DownloadIcon,
  Code2Icon,
  MessageSquareIcon,
  PlusIcon,
  SearchIcon,
  StarIcon,
  Trash2Icon,
  UploadIcon,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardFooter,
  CardHeader,
  CardDescription,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/core/i18n/hooks";
import {
  archiveSkill,
  exportSkill,
  importSkill,
  toggleSkillFavorite,
  useSkills,
} from "@/core/skills";

export function SkillList() {
  const { locale, t } = useI18n();
  const { skills, isLoading, refetch } = useSkills();
  const importRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const visibleSkills = useMemo(
    () =>
      skills.filter(
        (skill) =>
          (!favoritesOnly || skill.is_favorited) &&
          (!query ||
            `${skill.name} ${skill.description} ${skill.summary ?? ""}`
              .toLowerCase()
              .includes(query.toLowerCase())),
      ),
    [favoritesOnly, query, skills],
  );

  async function handleImport(file?: File) {
    if (!file) return;
    try {
      await importSkill(file);
      await refetch();
      toast.success(t.settings.skills.importSuccess);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleExport(skill: { resource_id?: string; name: string }) {
    if (!skill.resource_id) return;
    try {
      const url = URL.createObjectURL(await exportSkill(skill.resource_id));
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${skill.name}.skill`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleFavorite(resourceId: string, isFavorited: boolean) {
    try {
      await toggleSkillFavorite(resourceId, isFavorited);
      await refetch();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleArchive(resourceId: string) {
    try {
      await archiveSkill(resourceId);
      await refetch();
      toast.success(t.settings.skills.archiveSuccess);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  if (isLoading)
    return <div className="text-muted-foreground">{t.common.loading}</div>;
  if (!skills.length)
    return (
      <div className="text-muted-foreground flex h-64 items-center justify-center">
        No skills found
      </div>
    );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="relative min-w-48 flex-1">
          <SearchIcon className="text-muted-foreground absolute top-1/2 left-2.5 h-4 w-4 -translate-y-1/2" />
          <Input
            className="pl-8"
            placeholder={t.settings.skills.searchPlaceholder}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
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
          ref={importRef}
          className="hidden"
          type="file"
          accept=".skill"
          onChange={(event) => void handleImport(event.target.files?.[0])}
        />
        <Button variant="outline" onClick={() => importRef.current?.click()}>
          <UploadIcon className="mr-1.5 h-4 w-4" />
          {t.common.import}
        </Button>
        <Button asChild>
          <Link
            href={`/workspace/chats/new?prompt=${encodeURIComponent("请使用 skill-creator 帮我创建一个新技能。")}`}
          >
            <PlusIcon className="mr-1.5 h-4 w-4" />
            {t.settings.skills.createSkill}
          </Link>
        </Button>
      </div>
      <div className="workbench-resource-grid grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {visibleSkills.map((skill) => {
          const identity = skill.resource_id ?? skill.slug ?? skill.name;
          const invocation = skill.slug ?? skill.name;
          return (
            <Card
              key={identity}
              className="workbench-resource-card group flex flex-col transition-shadow hover:shadow-md"
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <div className="bg-primary/10 text-primary flex h-9 w-9 shrink-0 items-center justify-center rounded-lg">
                      <Code2Icon className="h-5 w-5" />
                    </div>
                    <CardTitle className="type-body truncate">
                      <Link
                        href={`/workspace/capabilities/skills/${identity}`}
                        className="hover:underline"
                      >
                        {skill.name}
                      </Link>
                    </CardTitle>
                  </div>
                  {skill.resource_id && (
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label={t.common.favoritesOnly}
                      onClick={() =>
                        void handleFavorite(
                          skill.resource_id!,
                          Boolean(skill.is_favorited),
                        )
                      }
                    >
                      <StarIcon
                        className={`h-4 w-4 ${skill.is_favorited ? "fill-yellow-400 text-yellow-400" : "text-muted-foreground"}`}
                      />
                    </Button>
                  )}
                </div>
                <CardDescription className="type-body mt-2 line-clamp-2 min-h-[3rem]">
                  {locale === "zh-CN"
                    ? (skill.summary ?? skill.description)
                    : skill.description}
                </CardDescription>
              </CardHeader>
              <CardFooter className="mt-auto flex items-center justify-between gap-2 pt-3">
                <Button asChild size="sm" className="flex-1">
                  <Link
                    href={`/workspace/chats/new?prompt=${encodeURIComponent(`/${invocation} `)}`}
                  >
                    <MessageSquareIcon className="mr-1.5 h-3.5 w-3.5" />
                    {t.settings.skills.use}
                  </Link>
                </Button>
                <div className="flex gap-1">
                  {skill.resource_id && (
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8 shrink-0"
                      onClick={() => void handleExport(skill)}
                      title={t.common.export}
                    >
                      <DownloadIcon className="h-3.5 w-3.5" />
                    </Button>
                  )}
                  {skill.resource_id && !skill.read_only && (
                    <Button
                      size="icon"
                      variant="ghost"
                      className="text-destructive hover:text-destructive h-8 w-8 shrink-0"
                      onClick={() => void handleArchive(skill.resource_id!)}
                      title={t.settings.skills.archiveSuccess}
                    >
                      <Trash2Icon className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
              </CardFooter>
            </Card>
          );
        })}
      </div>
      {!visibleSkills.length && (
        <div className="text-muted-foreground">
          {t.settings.skills.noResults}
        </div>
      )}
    </div>
  );
}
