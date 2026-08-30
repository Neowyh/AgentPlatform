"use client";

import { ArrowLeftIcon, SaveIcon } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { WorkspaceBreadcrumb } from "@/components/workspace/workspace-breadcrumb";
import { useAgent, useUpdateAgent } from "@/core/agents";
import type { UpdateAgentRequest } from "@/core/agents";
import { useI18n } from "@/core/i18n/hooks";
import { useModels } from "@/core/models/hooks";
import { useSkills } from "@/core/skills/hooks";

const TOOL_GROUPS = [
  { id: "file:read", label: "File Read" },
  { id: "file:write", label: "File Write" },
  { id: "bash", label: "Bash" },
  { id: "web", label: "Web" },
  { id: "enterprise", label: "Enterprise" },
];

export default function AgentEditPage() {
  const { t } = useI18n();
  const router = useRouter();
  const { agent_name } = useParams<{ agent_name: string }>();
  const { agent, isLoading: isLoadingAgent } = useAgent(agent_name);
  const { models } = useModels();
  const { skills } = useSkills();
  const updateAgent = useUpdateAgent();

  const [formData, setFormData] = useState<UpdateAgentRequest>({
    description: "",
    model: null,
    tool_groups: [],
    skills: [],
    soul: "",
  });
  const [originalVisibility, setOriginalVisibility] = useState("private");
  const [visibilityChangeDialogOpen, setVisibilityChangeDialogOpen] =
    useState(false);

  useEffect(() => {
    if (agent) {
      setFormData({
        description: agent.description ?? "",
        model: agent.model,
        tool_groups: agent.tool_groups ?? [],
        skills: agent.skills ?? [],
        soul: agent.soul ?? "",
        draft_revision: agent.draft_revision,
      });
      setOriginalVisibility(agent.visibility ?? "private");
    }
  }, [agent]);

  const handleSave = useCallback(async () => {
    if (
      formData.visibility !== undefined &&
      formData.visibility !== originalVisibility
    ) {
      setVisibilityChangeDialogOpen(true);
      return;
    }
    try {
      await updateAgent.mutateAsync({ name: agent_name, request: formData });
      toast.success("Agent updated successfully");
      router.push(`/workspace/agents/${agent_name}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }, [agent_name, formData, originalVisibility, router, updateAgent]);

  const handleNavigateToDetail = () => {
    setVisibilityChangeDialogOpen(false);
    router.push(`/workspace/agents/${agent_name}`);
  };

  const toggleToolGroup = (groupId: string) => {
    setFormData((prev) => ({
      ...prev,
      tool_groups: prev.tool_groups?.includes(groupId)
        ? prev.tool_groups.filter((g) => g !== groupId)
        : [...(prev.tool_groups ?? []), groupId],
    }));
  };

  const toggleSkill = (skillName: string) => {
    setFormData((prev) => ({
      ...prev,
      skills: prev.skills?.includes(skillName)
        ? prev.skills.filter((s) => s !== skillName)
        : [...(prev.skills ?? []), skillName],
    }));
  };

  if (isLoadingAgent) {
    return (
      <div className="flex size-full items-center justify-center">
        <div className="text-muted-foreground text-base">
          {t.common.loading}
        </div>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="flex size-full flex-col items-center justify-center gap-4">
        <div className="text-destructive text-base">Agent not found</div>
        <Button
          variant="outline"
          onClick={() => router.push("/workspace/agents")}
        >
          {t.agents.backToGallery}
        </Button>
      </div>
    );
  }

  if (agent.read_only) {
    return (
      <div className="flex size-full flex-col items-center justify-center gap-4">
        <div className="text-destructive text-base">
          You do not have permission to edit this Agent
        </div>
        <Button
          variant="outline"
          onClick={() => router.push(`/workspace/agents/${agent_name}`)}
        >
          Back to Agent
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
            onClick={() => router.push(`/workspace/agents/${agent_name}`)}
          >
            <ArrowLeftIcon className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-base font-semibold">Edit Agent</h1>
            <p className="text-muted-foreground mt-0.5 text-base">
              {agent_name}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => router.push(`/workspace/agents/${agent_name}`)}
          >
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={updateAgent.isPending}>
            <SaveIcon className="mr-1.5 h-4 w-4" />
            {updateAgent.isPending ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </div>

      {/* Form */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-2xl space-y-6">
          {/* Name (readonly) */}
          <div className="space-y-2">
            <Label>Name</Label>
            <Input value={agent_name} disabled />
            <p className="text-muted-foreground text-base">
              Agent name cannot be changed after creation
            </p>
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              placeholder="Describe what this agent does..."
              value={formData.description ?? ""}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  description: e.target.value,
                }))
              }
              rows={3}
            />
          </div>

          {/* Model */}
          <div className="space-y-2">
            <Label htmlFor="model">Model</Label>
            <select
              id="model"
              className="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-base file:border-0 file:bg-transparent file:text-base file:font-medium focus:ring-2 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
              value={formData.model ?? ""}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  model: e.target.value || null,
                }))
              }
            >
              <option value="">Default model</option>
              {models.map((model) => (
                <option key={model.id} value={model.model}>
                  {model.display_name ?? model.name}
                </option>
              ))}
            </select>
          </div>

          {/* Visibility */}
          <div className="space-y-2">
            <Label>Visibility</Label>
            <Select
              value={formData.visibility ?? originalVisibility}
              onValueChange={(value) =>
                setFormData((prev) => ({ ...prev, visibility: value }))
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select visibility" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="private">Private</SelectItem>
                <SelectItem value="department">Department</SelectItem>
                <SelectItem value="public">Public</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-muted-foreground text-base">
              Visibility changes require an application submission
            </p>
          </div>

          {/* Tool Groups */}
          <div className="space-y-2">
            <Label>Tool Groups</Label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {TOOL_GROUPS.map((group) => (
                <label
                  key={group.id}
                  className="hover:bg-accent flex cursor-pointer items-center gap-2 rounded-md border p-3 transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={formData.tool_groups?.includes(group.id) ?? false}
                    onChange={() => toggleToolGroup(group.id)}
                    className="h-4 w-4 rounded border-gray-300"
                  />
                  <span className="text-base">{group.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Skills */}
          <div className="space-y-2">
            <Label>Skills</Label>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {skills.map((skill) => (
                <label
                  key={skill.resource_id ?? skill.name}
                  className="hover:bg-accent flex cursor-pointer items-center gap-2 rounded-md border p-3 transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={
                      formData.skills?.includes(
                        skill.resource_id ?? skill.name,
                      ) ?? false
                    }
                    onChange={() =>
                      toggleSkill(skill.resource_id ?? skill.name)
                    }
                    className="h-4 w-4 rounded border-gray-300"
                  />
                  <div className="min-w-0">
                    <div className="truncate text-base font-medium">
                      {skill.name}
                    </div>
                    {skill.description && (
                      <div className="text-muted-foreground truncate text-base">
                        {skill.description}
                      </div>
                    )}
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* SOUL.md */}
          <div className="space-y-2">
            <Label htmlFor="soul">SOUL.md</Label>
            <Textarea
              id="soul"
              placeholder="# Agent Soul&#10;&#10;Define the agent's personality, capabilities, and behavior..."
              value={formData.soul ?? ""}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, soul: e.target.value }))
              }
              rows={12}
              className="font-mono text-base"
            />
            <p className="text-muted-foreground text-base">
              The soul defines the agent&apos;s personality and behavior. Uses
              Markdown format.
            </p>
          </div>
        </div>
      </div>

      {/* Visibility Change Dialog */}
      <Dialog
        open={visibilityChangeDialogOpen}
        onOpenChange={setVisibilityChangeDialogOpen}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Visibility Change Requires Application</DialogTitle>
            <DialogDescription>
              Visibility changes cannot be saved directly. You need to submit a
              visibility change application on the agent detail page.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setVisibilityChangeDialogOpen(false)}
            >
              Stay on Edit Page
            </Button>
            <Button onClick={handleNavigateToDetail}>Go to Detail Page</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
