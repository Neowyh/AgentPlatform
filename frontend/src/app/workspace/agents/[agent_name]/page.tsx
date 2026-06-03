"use client";

import {
  ArrowLeftIcon,
  BotIcon,
  CalendarIcon,
  CoinsIcon,
  EditIcon,
  MessageSquareIcon,
  SettingsIcon,
  SparklesIcon,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { WorkspaceBreadcrumb } from "@/components/workspace/workspace-breadcrumb";
import { useAgent } from "@/core/agents";
import { useI18n } from "@/core/i18n/hooks";

export default function AgentDetailPage() {
  const { t } = useI18n();
  const router = useRouter();
  const { agent_name } = useParams<{ agent_name: string }>();
  const { agent, isLoading, error } = useAgent(agent_name);

  if (isLoading) {
    return (
      <div className="flex size-full items-center justify-center">
        <div className="text-muted-foreground text-sm">{t.common.loading}</div>
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div className="flex size-full flex-col items-center justify-center gap-4">
        <div className="text-destructive text-sm">
          {error?.message ?? "Agent not found"}
        </div>
        <Button
          variant="outline"
          onClick={() => router.push("/workspace/agents")}
        >
          {t.agents.backToGallery}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex size-full flex-col">
      <WorkspaceBreadcrumb />
      {/* Page header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => router.push("/workspace/agents")}
          >
            <ArrowLeftIcon className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-2">
            <div className="bg-primary/10 text-primary flex h-9 w-9 items-center justify-center rounded-lg">
              <BotIcon className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-xl font-semibold">{agent.name}</h1>
              {agent.description && (
                <p className="text-muted-foreground mt-0.5 text-sm">
                  {agent.description}
                </p>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {agent.model && <Badge variant="secondary">{agent.model}</Badge>}
          {agent.read_only && <Badge variant="outline">Template</Badge>}
          <Button asChild>
            <Link href={`/workspace/agents/${agent_name}/edit`}>
              <EditIcon className="mr-1.5 h-4 w-4" />
              Edit Agent
            </Link>
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          {/* Stats cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Conversations
                </CardTitle>
                <MessageSquareIcon className="text-muted-foreground h-4 w-4" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">--</div>
                <p className="text-muted-foreground text-xs">
                  Total conversations
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Token Usage
                </CardTitle>
                <CoinsIcon className="text-muted-foreground h-4 w-4" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">--</div>
                <p className="text-muted-foreground text-xs">Tokens consumed</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Active Days
                </CardTitle>
                <CalendarIcon className="text-muted-foreground h-4 w-4" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">--</div>
                <p className="text-muted-foreground text-xs">
                  Days with activity
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Configuration overview */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <SettingsIcon className="h-5 w-5" />
                Configuration
              </CardTitle>
              <CardDescription>Agent capabilities and settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Model */}
              <div>
                <h4 className="text-sm font-medium">Model</h4>
                <p className="text-muted-foreground text-sm">
                  {agent.model ?? "Default model"}
                </p>
              </div>

              {/* Tool groups */}
              {agent.tool_groups && agent.tool_groups.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium">Tool Groups</h4>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {agent.tool_groups.map((group) => (
                      <Badge key={group} variant="outline">
                        {group}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Skills */}
              {agent.skills && agent.skills.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium">Skills</h4>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {agent.skills.map((skill) => (
                      <Badge key={skill} variant="secondary">
                        <SparklesIcon className="mr-1 h-3 w-3" />
                        {skill}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* SOUL.md preview */}
              {agent.soul && (
                <div>
                  <h4 className="text-sm font-medium">SOUL.md</h4>
                  <pre className="bg-muted mt-2 max-h-48 overflow-auto rounded-md p-4 text-sm">
                    {agent.soul}
                  </pre>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Quick actions */}
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-4">
                <Button asChild>
                  <Link href={`/workspace/agents/${agent_name}/chats/new`}>
                    <MessageSquareIcon className="mr-1.5 h-4 w-4" />
                    Start Chat
                  </Link>
                </Button>
                <Button variant="outline" asChild>
                  <Link href={`/workspace/agents/${agent_name}/edit`}>
                    <EditIcon className="mr-1.5 h-4 w-4" />
                    Edit Configuration
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
