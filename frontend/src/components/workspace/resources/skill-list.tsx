"use client";

import {
  DownloadIcon,
  Code2Icon,
  MessageSquareIcon,
  StarIcon,
  Trash2Icon,
  UploadIcon,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
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
  const { t } = useI18n();
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
            `${skill.name} ${skill.description}`
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
        <Input
          className="w-48"
          placeholder={t.settings.skills.searchPlaceholder}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <Button
          variant={favoritesOnly ? "default" : "outline"}
          onClick={() => setFavoritesOnly((value) => !value)}
        >
          {t.common.favoritesOnly}
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
      </div>
      <div className="workbench-resource-grid grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {visibleSkills.map((skill) => {
          const identity = skill.resource_id ?? skill.slug ?? skill.name;
          const invocation = skill.slug ?? skill.name;
          return (
            <Card
              key={identity}
              className="workbench-resource-card flex min-h-[15rem] flex-col"
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <div className="bg-primary/10 text-primary flex h-9 w-9 shrink-0 items-center justify-center rounded-lg">
                      <Code2Icon className="h-5 w-5" />
                    </div>
                    <CardTitle className="type-body truncate">
                      {skill.name}
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
                <div className="flex flex-wrap gap-1">
                  <Badge variant="secondary">
                    {skill.slug ? `/${skill.slug}` : "Skill"}
                  </Badge>
                  <Badge variant="outline">{skill.category}</Badge>
                  {skill.visibility && (
                    <Badge variant="outline">{skill.visibility}</Badge>
                  )}
                  <Badge variant="outline">
                    {skill.read_only ? "只读" : "可管理"}
                  </Badge>
                </div>
                <p className="text-muted-foreground type-body line-clamp-2 min-h-[3rem]">
                  {skill.description}
                </p>
              </CardHeader>
              <CardContent className="pt-0" />
              <CardFooter className="mt-auto flex gap-2 pt-3">
                <Button asChild variant="outline" size="sm" className="flex-1">
                  <Link href={`/workspace/capabilities/skills/${identity}`}>
                    {t.settings.skills.details}
                  </Link>
                </Button>
                <Button asChild size="sm" className="flex-1">
                  <Link
                    href={`/workspace/chats/new?prompt=${encodeURIComponent(`/${invocation} `)}`}
                  >
                    <MessageSquareIcon className="mr-1.5 h-3.5 w-3.5" />
                    {t.settings.skills.use}
                  </Link>
                </Button>
                {skill.resource_id && (
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => void handleExport(skill)}
                  >
                    <DownloadIcon className="h-4 w-4" />
                  </Button>
                )}
                {skill.resource_id && !skill.read_only && (
                  <Button
                    size="icon"
                    variant="ghost"
                    className="text-destructive"
                    onClick={() => void handleArchive(skill.resource_id!)}
                  >
                    <Trash2Icon className="h-4 w-4" />
                  </Button>
                )}
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
