"use client";

import {
  BotIcon,
  DownloadIcon,
  EditIcon,
  MessageSquareIcon,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  ResourceDetailCard,
  ResourceDetailLayout,
  ResourceDetailRow,
} from "@/components/workspace/resources/resource-detail-layout";
import { VisibilityImpactPanel } from "@/components/workspace/resources/visibility-impact-panel";
import { WorkspaceBreadcrumb } from "@/components/workspace/workspace-breadcrumb";
import { useAgent } from "@/core/agents";
import { exportAgent } from "@/core/agents/api";
import { useI18n } from "@/core/i18n/hooks";
import { useSkills } from "@/core/skills";
import {
  changeResourceVisibility,
  createVisibilityApplication,
} from "@/core/visibility-applications/api";
import { classifyVisibilityChange } from "@/core/visibility-applications/options";

export default function AgentDetailPage() {
  const { t } = useI18n();
  const router = useRouter();
  const { agent_name: agentName } = useParams<{ agent_name: string }>();
  const { agent, isLoading, error } = useAgent(agentName);
  const { skills } = useSkills();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [targetVisibility, setTargetVisibility] = useState("private");
  const [reason, setReason] = useState("");
  const [confirmingDowngrade, setConfirmingDowngrade] = useState(false);
  const [cascade, setCascade] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (agent?.resource_id && agentName !== agent.resource_id)
      router.replace(`/workspace/capabilities/experts/${agent.resource_id}`);
    if (agent) setTargetVisibility(agent.visibility ?? "private");
  }, [agent, agentName, router]);

  if (isLoading)
    return <div className="text-muted-foreground p-6">{t.common.loading}</div>;
  if (error || !agent)
    return (
      <div className="flex size-full items-center justify-center">
        <p className="text-destructive">
          {error?.message ?? t.agents.notFound}
        </p>
      </div>
    );

  const resourceId = agent.resource_id ?? agentName;
  const chatIdentity = agent.slug ?? agent.name;
  const visibility =
    agent.visibility === "public"
      ? t.agents.visibilityPublic
      : agent.visibility === "department"
        ? t.agents.visibilityDepartment
        : t.agents.visibilityPrivate;
  const submitVisibility = async () => {
    const change = classifyVisibilityChange(agent.visibility, targetVisibility);
    if (change === "unchanged") return;
    if (change === "downgrade") {
      setConfirmingDowngrade(true);
      return;
    }
    if (!reason.trim()) {
      toast.error(t.agents.visibilityReasonRequired);
      return;
    }
    setSubmitting(true);
    try {
      await createVisibilityApplication({
        resource_type: "agent",
        resource_id: resourceId,
        target_visibility: targetVisibility,
        reason: reason.trim(),
      });
      toast.success(t.agents.applicationSubmitted);
      setDialogOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };
  const confirmVisibility = async () => {
    setSubmitting(true);
    try {
      await changeResourceVisibility({
        resource_id: resourceId,
        visibility: targetVisibility,
        cascade,
      });
      toast.success(t.agents.visibilityUpdated);
      setDialogOpen(false);
      setConfirmingDowngrade(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };
  const download = async () => {
    try {
      const url = URL.createObjectURL(await exportAgent(resourceId));
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${agent.slug ?? agent.name}.zip`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error(t.agents.exportFailed);
    }
  };
  return (
    <>
      <ResourceDetailLayout
        breadcrumb={<WorkspaceBreadcrumb agent={agent} />}
        backHref="/workspace/capabilities/experts"
        icon={<BotIcon className="h-5 w-5" />}
        title={agent.name}
        description={agent.summary ?? agent.description}
        actions={
          <>
            <Button asChild>
              <Link
                href={`/workspace/chats/new?agent=${encodeURIComponent(chatIdentity)}`}
              >
                <MessageSquareIcon className="mr-1.5 h-4 w-4" />
                {t.agents.detailChat}
              </Link>
            </Button>
            {!agent.read_only && (
              <Button variant="outline" onClick={() => setDialogOpen(true)}>
                {t.agents.changeVisibility}
              </Button>
            )}
            {!agent.read_only && (
              <Button variant="outline" asChild>
                <Link
                  href={`/workspace/capabilities/experts/${agentName}/edit`}
                >
                  <EditIcon className="mr-1.5 h-4 w-4" />
                  {t.common.edit}
                </Link>
              </Button>
            )}
            {!agent.read_only && (
              <Button variant="outline" onClick={() => void download()}>
                <DownloadIcon className="mr-1.5 h-4 w-4" />
                {t.agents.export}
              </Button>
            )}
          </>
        }
      >
        <ResourceDetailCard title={t.agents.configuration}>
          <dl>
            <ResourceDetailRow
              label={t.agents.model}
              value={agent.model ?? t.agents.defaultModel}
            />
            <ResourceDetailRow
              label={t.agents.toolGroups}
              value={agent.tool_groups?.join(", ") ?? t.agents.notSpecified}
            />
            <ResourceDetailRow
              label={t.agents.skills}
              value={
                agent.skills?.length
                  ? agent.skills
                      .map(
                        (skillRef) =>
                          skills.find(
                            (skill) =>
                              skill.slug === skillRef ||
                              skill.resource_id === skillRef,
                          )?.name,
                      )
                      .filter((name): name is string => Boolean(name))
                      .join(", ") || t.agents.notSpecified
                  : t.agents.notSpecified
              }
            />
            <ResourceDetailRow label={t.agents.visibility} value={visibility} />
          </dl>
        </ResourceDetailCard>
        <ResourceDetailCard title={t.agents.source}>
          <pre className="bg-muted type-body max-h-[30rem] overflow-auto rounded-xl p-4 whitespace-pre-wrap">
            {agent.soul ?? t.agents.notSpecified}
          </pre>
        </ResourceDetailCard>
      </ResourceDetailLayout>
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          {confirmingDowngrade ? (
            <>
              <DialogHeader>
                <DialogTitle>{t.agents.downgradeConfirmTitle}</DialogTitle>
                <DialogDescription>
                  {t.agents.downgradeConfirmDescription}
                </DialogDescription>
              </DialogHeader>
              <VisibilityImpactPanel
                resourceId={resourceId}
                currentVisibility={agent.visibility}
                targetVisibility={targetVisibility}
                onCascadeChange={setCascade}
              />
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setConfirmingDowngrade(false)}
                >
                  {t.common.cancel}
                </Button>
                <Button
                  onClick={() => void confirmVisibility()}
                  disabled={submitting}
                >
                  {t.agents.confirm}
                </Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle>{t.agents.applyVisibility}</DialogTitle>
                <DialogDescription>
                  {t.agents.applyVisibilityDescription}
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <Label>{t.agents.targetVisibility}</Label>
                <Select
                  value={targetVisibility}
                  onValueChange={setTargetVisibility}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="private">
                      {t.agents.visibilityPrivate}
                    </SelectItem>
                    <SelectItem value="department">
                      {t.agents.visibilityDepartment}
                    </SelectItem>
                    <SelectItem value="public">
                      {t.agents.visibilityPublic}
                    </SelectItem>
                  </SelectContent>
                </Select>
                <Label htmlFor="reason">{t.agents.reason}</Label>
                <Textarea
                  id="reason"
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder={t.agents.reasonPlaceholder}
                  rows={3}
                />
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setDialogOpen(false)}>
                  {t.common.cancel}
                </Button>
                <Button
                  onClick={() => void submitVisibility()}
                  disabled={submitting}
                >
                  {t.agents.submit}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
