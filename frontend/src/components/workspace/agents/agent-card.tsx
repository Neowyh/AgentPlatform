"use client";

import {
  BotIcon,
  DownloadIcon,
  LockIcon,
  MessageSquareIcon,
  StarIcon,
  Trash2Icon,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useDeleteAgent, useToggleAgentFavorite } from "@/core/agents";
import type { Agent } from "@/core/agents";
import { exportAgent } from "@/core/agents/api";
import { useI18n } from "@/core/i18n/hooks";

interface AgentCardProps {
  agent: Agent;
}

export function AgentCard({ agent }: AgentCardProps) {
  const { t } = useI18n();
  const router = useRouter();
  const deleteAgent = useDeleteAgent();
  const toggleFavorite = useToggleAgentFavorite();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const routeIdentity = agent.resource_id ?? agent.name;

  function handleChat() {
    router.push(`/workspace/agents/${routeIdentity}/chats/new`);
  }

  async function handleToggleFavorite() {
    try {
      await toggleFavorite.mutateAsync(
        agent.resource_id
          ? {
              name: agent.resource_id,
              isFavorited: agent.is_favorited ?? false,
            }
          : agent.name,
      );
      toast.success(
        agent.is_favorited ? t.agents.favoriteRemoved : t.agents.favoriteAdded,
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleDelete() {
    try {
      await deleteAgent.mutateAsync(routeIdentity);
      toast.success(t.agents.deleteSuccess);
      setDeleteOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleExport() {
    try {
      const blob = await exportAgent(routeIdentity);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${agent.name}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success(t.agents.exportSuccess);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <>
      <Card
        className="workbench-resource-card group flex flex-col transition-shadow hover:shadow-md"
        data-testid="agent-card"
      >
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <div className="bg-primary/10 text-primary flex h-9 w-9 shrink-0 items-center justify-center rounded-lg">
                <BotIcon className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <CardTitle className="type-body truncate">
                  <Link
                    href={`/workspace/agents/${routeIdentity}`}
                    className="hover:underline"
                  >
                    {agent.name}
                  </Link>
                  {agent.read_only && (
                    <Badge variant="outline" className="type-body ml-1.5">
                      <LockIcon className="mr-0.5 h-2.5 w-2.5" />
                      {t.agents.template}
                    </Badge>
                  )}
                </CardTitle>
                <div className="mt-0.5 flex items-center gap-1.5">
                  {agent.model && (
                    <Badge variant="secondary" className="type-body">
                      {agent.model}
                    </Badge>
                  )}
                  <span
                    className={`type-compact inline-flex items-center rounded-full px-1.5 py-0.5 font-medium ${
                      agent.visibility === "public"
                        ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                        : agent.visibility === "department"
                          ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                          : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {agent.visibility === "public"
                      ? t.agents.visibilityPublic
                      : agent.visibility === "department"
                        ? t.agents.visibilityDepartment
                        : t.agents.visibilityPrivate}
                  </span>
                </div>
              </div>
            </div>
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 shrink-0"
              onClick={handleToggleFavorite}
              data-testid="agent-favorite-button"
            >
              <StarIcon
                className={`h-4 w-4 ${agent.is_favorited ? "fill-yellow-400 text-yellow-400" : "text-muted-foreground"}`}
              />
            </Button>
          </div>
          {agent.description && (
            <CardDescription className="type-body mt-2 line-clamp-2">
              {agent.description}
            </CardDescription>
          )}
        </CardHeader>

        {(agent.tool_groups?.length ?? agent.skills?.length ?? 0) > 0 && (
          <CardContent className="pt-0 pb-3">
            <div className="flex flex-wrap gap-1">
              {agent.tool_groups?.map((group) => (
                <Badge
                  key={`tg:${group}`}
                  variant="outline"
                  className="type-body"
                >
                  {group}
                </Badge>
              ))}
              {agent.skills?.map((skill) => (
                <Badge
                  key={`sk:${skill}`}
                  variant="secondary"
                  className="type-body"
                >
                  {skill}
                </Badge>
              ))}
            </div>
          </CardContent>
        )}

        <CardFooter className="mt-auto flex items-center justify-between gap-2 pt-3">
          <Button
            size="sm"
            className="flex-1"
            onClick={handleChat}
            data-testid="agent-chat-button"
          >
            <MessageSquareIcon className="mr-1.5 h-3.5 w-3.5" />
            {t.agents.chat}
          </Button>
          <div className="flex gap-1">
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 shrink-0"
              onClick={handleExport}
              title={t.common.export}
              data-testid="agent-export-button"
            >
              <DownloadIcon className="h-3.5 w-3.5" />
            </Button>
            {!agent.read_only && (
              <Button
                size="icon"
                variant="ghost"
                className="text-destructive hover:text-destructive h-8 w-8 shrink-0"
                onClick={() => setDeleteOpen(true)}
                title={t.agents.delete}
                data-testid="agent-delete-button"
              >
                <Trash2Icon className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        </CardFooter>
      </Card>

      {/* Delete Confirm */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t.agents.delete}</DialogTitle>
            <DialogDescription>{t.agents.deleteConfirm}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteOpen(false)}
              disabled={deleteAgent.isPending}
            >
              {t.common.cancel}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteAgent.isPending}
            >
              {deleteAgent.isPending ? t.common.loading : t.common.delete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
