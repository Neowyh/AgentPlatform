"use client";

import { ArrowLeftIcon, SaveIcon } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
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
import {
  allowedSubagentsToSelection,
  DEFAULT_MODEL_VALUE,
  INHERIT_VALUE,
  MAX_AGENT_OUTPUT_TOKENS,
  parseAgentModelSettingsDraft,
  resolveEffectiveModel,
  selectionToAllowedSubagents,
  selectionToThinkingEnabled,
  thinkingEnabledToSelection,
  type SubagentAccessSelection,
  type ThinkingSelection,
} from "@/components/workspace/agents/agent-settings-dialog-helpers";
import {
  KnowledgeDependencySelector,
  type KnowledgeDependencyOption,
} from "@/components/workspace/capabilities/knowledge-dependency-selector";
import { WorkspaceBreadcrumb } from "@/components/workspace/workspace-breadcrumb";
import { useAgent, useUpdateAgent } from "@/core/agents";
import type { ReasoningEffort, UpdateAgentRequest } from "@/core/agents";
import { useI18n } from "@/core/i18n/hooks";
import { useModels } from "@/core/models/hooks";
import {
  getResourceDependencies,
  listKnowledgeBases,
} from "@/core/resources/api";
import { useSkills } from "@/core/skills/hooks";
import { useSubagents } from "@/core/subagents";

const TOOL_GROUPS = [
  { id: "file:read", label: "File Read" },
  { id: "file:write", label: "File Write" },
  { id: "bash", label: "Bash" },
  { id: "web", label: "Web" },
  { id: "enterprise", label: "Enterprise" },
];

const REASONING_EFFORTS: ReasoningEffort[] = ["low", "medium", "high"];

// Shared by the native selects on this form (model + behavior settings).
const SELECT_CLASS =
  "border-input bg-background ring-offset-background placeholder:text-muted-foreground focus:ring-ring type-body flex h-10 w-full rounded-md border px-3 py-2 file:border-0 file:bg-transparent file:font-medium focus:ring-2 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50";

export default function AgentEditPage() {
  const { t } = useI18n();
  const router = useRouter();
  const { agent_name } = useParams<{ agent_name: string }>();
  const { agent, isLoading: isLoadingAgent } = useAgent(agent_name);
  const { models } = useModels();
  const { skills } = useSkills();
  const { subagents } = useSubagents();
  const updateAgent = useUpdateAgent();

  const [formData, setFormData] = useState<UpdateAgentRequest>({
    description: "",
    model: null,
    tool_groups: [],
    skills: [],
    soul: "",
  });
  // Model-behavior overrides (merged from the DeerFlow expert settings
  // dialog): temperature / max tokens / thinking / reasoning effort /
  // subagent access.
  const [temperature, setTemperature] = useState("");
  const [maxTokens, setMaxTokens] = useState("");
  const [thinking, setThinking] = useState<ThinkingSelection>(INHERIT_VALUE);
  const [reasoningEffort, setReasoningEffort] = useState<
    ReasoningEffort | typeof INHERIT_VALUE
  >(INHERIT_VALUE);
  const [subagentAccess, setSubagentAccess] =
    useState<SubagentAccessSelection>("all");
  const [selectedSubagents, setSelectedSubagents] = useState<string[]>([]);
  const [originalVisibility, setOriginalVisibility] = useState("private");
  const [visibilityChangeDialogOpen, setVisibilityChangeDialogOpen] =
    useState(false);
  const [knowledgeBases, setKnowledgeBases] = useState<
    Array<{ id: string; slug: string; display_name: string }>
  >([]);
  const [knowledgeDependencies, setKnowledgeDependencies] = useState<
    KnowledgeDependencyOption[]
  >([]);
  const [knowledgeDependenciesLoaded, setKnowledgeDependenciesLoaded] =
    useState(false);
  const [knowledgeDependenciesLoadError, setKnowledgeDependenciesLoadError] =
    useState(false);
  const [revisionsLoadError, setRevisionsLoadError] = useState(false);

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
      setTemperature(
        agent.model_settings?.temperature != null
          ? String(agent.model_settings.temperature)
          : "",
      );
      setMaxTokens(
        agent.model_settings?.max_tokens != null
          ? String(agent.model_settings.max_tokens)
          : "",
      );
      setThinking(thinkingEnabledToSelection(agent.thinking_enabled));
      setReasoningEffort(agent.reasoning_effort ?? INHERIT_VALUE);
      setSubagentAccess(allowedSubagentsToSelection(agent.allowed_subagents));
      setSelectedSubagents(agent.allowed_subagents ?? []);
    }
  }, [agent]);

  useEffect(() => {
    if (!agent?.resource_id) return;
    setKnowledgeDependenciesLoaded(false);
    setKnowledgeDependenciesLoadError(false);
    void Promise.all([
      listKnowledgeBases(),
      getResourceDependencies(agent.resource_id),
    ])
      .then(([bases, dependencies]) => {
        setKnowledgeBases(bases);
        setKnowledgeDependencies(
          dependencies
            .filter((item) => item.type === "knowledge_base")
            .map((item) => ({
              resource_id: item.resource_id,
              dependency_mode: item.dependency_mode,
              revision_id: item.revision_id,
              required: item.required,
              purpose: item.purpose,
            })),
        );
        setKnowledgeDependenciesLoaded(true);
      })
      .catch(() => {
        // A failed dependency read must never be interpreted as an empty
        // selection: saving that value would silently remove existing edges.
        setKnowledgeDependenciesLoadError(true);
      });
  }, [agent?.resource_id]);

  // The resolved model gates which behavior controls are meaningful. When the
  // agent inherits the global default, fall back to models[0] so the controls
  // stay visible.
  const selectedModel = resolveEffectiveModel(
    models,
    formData.model ?? DEFAULT_MODEL_VALUE,
  );
  const supportsThinking = selectedModel?.supports_thinking ?? false;
  const supportsReasoningEffort =
    selectedModel?.supports_reasoning_effort ?? false;
  const selectableSubagents = useMemo(
    () =>
      Array.from(
        new Map(
          subagents
            .filter((item) => item.enabled && !item.conflict)
            .map((item) => [item.name, item]),
        ).values(),
      ),
    [subagents],
  );
  const missingSubagents = useMemo(() => {
    const selectableNames = new Set(
      selectableSubagents.map((item) => item.name),
    );
    return selectedSubagents.filter((name) => !selectableNames.has(name));
  }, [selectableSubagents, selectedSubagents]);

  const handleSave = useCallback(async () => {
    if (
      formData.visibility !== undefined &&
      formData.visibility !== originalVisibility
    ) {
      setVisibilityChangeDialogOpen(true);
      return;
    }
    try {
      if (knowledgeDependenciesLoadError || revisionsLoadError) {
        // A failed dependency or revision read must never be saved: the
        // selection on screen is not proven to match the stored edges.
        toast.error(
          "Knowledge dependencies could not be loaded. Reload before saving.",
        );
        return;
      }
      const parsedSettings = parseAgentModelSettingsDraft({
        temperature,
        maxTokens,
      });
      if (!parsedSettings.ok) {
        toast.error(
          parsedSettings.error === "temperature"
            ? t.agents.settingsInvalidTemperature
            : t.agents.settingsInvalidMaxTokens,
        );
        return;
      }
      const baseRequest = agent?.resource_id
        ? {
            ...formData,
            ...(knowledgeDependenciesLoaded
              ? { knowledge_dependencies: knowledgeDependencies }
              : {}),
          }
        : formData;
      const request = {
        ...baseRequest,
        model_settings: parsedSettings.modelSettings,
        thinking_enabled: supportsThinking
          ? selectionToThinkingEnabled(thinking)
          : null,
        reasoning_effort:
          supportsReasoningEffort && reasoningEffort !== INHERIT_VALUE
            ? reasoningEffort
            : null,
        allowed_subagents: selectionToAllowedSubagents(
          subagentAccess,
          selectedSubagents,
        ),
      };
      await updateAgent.mutateAsync({ name: agent_name, request });
      toast.success("Agent updated successfully");
      router.push(`/workspace/capabilities/experts/${agent_name}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }, [
    agent,
    agent_name,
    formData,
    knowledgeDependencies,
    knowledgeDependenciesLoaded,
    knowledgeDependenciesLoadError,
    maxTokens,
    reasoningEffort,
    revisionsLoadError,
    selectedSubagents,
    subagentAccess,
    supportsReasoningEffort,
    supportsThinking,
    t.agents.settingsInvalidMaxTokens,
    t.agents.settingsInvalidTemperature,
    temperature,
    thinking,
    originalVisibility,
    router,
    updateAgent,
  ]);

  const handleNavigateToDetail = () => {
    setVisibilityChangeDialogOpen(false);
    router.push(`/workspace/capabilities/experts/${agent_name}`);
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
        <div className="text-muted-foreground type-body">
          {t.common.loading}
        </div>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="flex size-full flex-col items-center justify-center gap-4">
        <div className="text-destructive type-body">Agent not found</div>
        <Button
          variant="outline"
          onClick={() => router.push("/workspace/capabilities/experts")}
        >
          {t.agents.backToGallery}
        </Button>
      </div>
    );
  }

  if (agent.read_only) {
    return (
      <div className="flex size-full flex-col items-center justify-center gap-4">
        <div className="text-destructive type-body">
          You do not have permission to edit this Agent
        </div>
        <Button
          variant="outline"
          onClick={() =>
            router.push(`/workspace/capabilities/experts/${agent_name}`)
          }
        >
          Back to Agent
        </Button>
      </div>
    );
  }

  return (
    <div className="flex size-full flex-col">
      <WorkspaceBreadcrumb agent={agent} />
      {/* Page header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() =>
              router.push(`/workspace/capabilities/experts/${agent_name}`)
            }
          >
            <ArrowLeftIcon className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="type-page-title font-semibold">Edit Agent</h1>
            <p className="text-muted-foreground type-body mt-0.5">
              {agent_name}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() =>
              router.push(`/workspace/capabilities/experts/${agent_name}`)
            }
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
            <p className="text-muted-foreground type-body">
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
              className={SELECT_CLASS}
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

          {/* Temperature */}
          <div className="space-y-2">
            <Label htmlFor="temperature">{t.agents.settingsTemperature}</Label>
            <Input
              id="temperature"
              type="number"
              min={0}
              max={2}
              step={0.1}
              value={temperature}
              placeholder={t.agents.settingsInherit}
              onChange={(e) => setTemperature(e.target.value)}
            />
            <p className="text-muted-foreground type-body">
              {t.agents.settingsTemperatureHint}
            </p>
          </div>

          {/* Max output tokens */}
          <div className="space-y-2">
            <Label htmlFor="max-tokens">{t.agents.settingsMaxTokens}</Label>
            <Input
              id="max-tokens"
              type="number"
              min={1}
              max={MAX_AGENT_OUTPUT_TOKENS}
              step={1}
              value={maxTokens}
              placeholder={t.agents.settingsInherit}
              onChange={(e) => setMaxTokens(e.target.value)}
            />
          </div>

          {/* Thinking mode (only when the selected model supports it) */}
          {supportsThinking && (
            <div className="space-y-2">
              <Label htmlFor="thinking-select">
                {t.agents.settingsThinking}
              </Label>
              <select
                id="thinking-select"
                className={SELECT_CLASS}
                value={thinking}
                onChange={(e) =>
                  setThinking(e.target.value as ThinkingSelection)
                }
              >
                <option value={INHERIT_VALUE}>
                  {t.agents.settingsInherit}
                </option>
                <option value="on">{t.agents.settingsThinkingOn}</option>
                <option value="off">{t.agents.settingsThinkingOff}</option>
              </select>
            </div>
          )}

          {/* Reasoning effort (only when supported) */}
          {supportsReasoningEffort && (
            <div className="space-y-2">
              <Label htmlFor="reasoning-effort-select">
                {t.agents.settingsReasoningEffort}
              </Label>
              <select
                id="reasoning-effort-select"
                className={SELECT_CLASS}
                value={reasoningEffort}
                onChange={(e) =>
                  setReasoningEffort(
                    e.target.value as ReasoningEffort | typeof INHERIT_VALUE,
                  )
                }
              >
                <option value={INHERIT_VALUE}>
                  {t.agents.settingsInherit}
                </option>
                {REASONING_EFFORTS.map((effort) => (
                  <option key={effort} value={effort}>
                    {effort}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Subagent access */}
          <div className="space-y-2">
            <Label htmlFor="subagent-access-select">
              {t.settings.subagents.bindingTitle}
            </Label>
            <select
              id="subagent-access-select"
              className={SELECT_CLASS}
              value={subagentAccess}
              onChange={(e) =>
                setSubagentAccess(e.target.value as SubagentAccessSelection)
              }
            >
              <option value="all">{t.settings.subagents.allAllowed}</option>
              <option value="none">{t.settings.subagents.noneAllowed}</option>
              <option value="selected">
                {t.settings.subagents.selectedAllowed}
              </option>
            </select>
            {subagentAccess === "selected" && (
              <div className="max-h-40 space-y-2 overflow-y-auto rounded-md border p-3">
                {selectableSubagents.map((item) => (
                  <label
                    key={item.name}
                    className="hover:bg-accent type-body flex cursor-pointer items-start gap-2 rounded-md p-2"
                  >
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4"
                      checked={selectedSubagents.includes(item.name)}
                      onChange={(event) =>
                        setSelectedSubagents((current) =>
                          event.target.checked
                            ? [...current, item.name]
                            : current.filter((name) => name !== item.name),
                        )
                      }
                    />
                    <span>
                      <span className="font-medium">
                        {item.display_name ?? item.name}
                      </span>{" "}
                      <span className="text-muted-foreground block">
                        {item.description}
                      </span>
                    </span>
                  </label>
                ))}
                {missingSubagents.map((name) => (
                  <label
                    key={name}
                    className="text-muted-foreground type-body flex items-start gap-2"
                  >
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4"
                      checked
                      disabled
                      onChange={() =>
                        setSelectedSubagents((current) =>
                          current.filter((item) => item !== name),
                        )
                      }
                    />
                    <span>
                      <span className="font-medium">{name}</span>
                      <span className="block">
                        {t.settings.subagents.missing}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            )}
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
            <p className="text-muted-foreground type-body">
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
                  <span className="type-body">{group.label}</span>
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
                    <div className="type-body truncate font-medium">
                      {skill.name}
                    </div>
                    {skill.description && (
                      <div className="text-muted-foreground type-body truncate">
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
            <Label>KnowledgeBases</Label>
            <KnowledgeDependencySelector
              knowledgeBases={knowledgeBases}
              dependencies={knowledgeDependencies}
              onChange={setKnowledgeDependencies}
              loadError={knowledgeDependenciesLoadError}
              onRevisionsLoadError={setRevisionsLoadError}
            />
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
              className="type-body font-mono"
            />
            <p className="text-muted-foreground type-body">
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
