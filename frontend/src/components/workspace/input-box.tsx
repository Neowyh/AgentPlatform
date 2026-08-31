"use client";

import type { ChatStatus } from "ai";
import {
  CheckIcon,
  GraduationCapIcon,
  LightbulbIcon,
  PaperclipIcon,
  RocketIcon,
  SparklesIcon,
  XIcon,
  ZapIcon,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ComponentProps,
} from "react";

import {
  PromptInput,
  PromptInputActionMenu,
  PromptInputActionMenuContent,
  PromptInputActionMenuItem,
  PromptInputActionMenuTrigger,
  PromptInputAttachment,
  PromptInputAttachments,
  PromptInputBody,
  PromptInputButton,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
  usePromptInputAttachments,
  usePromptInputController,
  type PromptInputMessage,
} from "@/components/ai-elements/prompt-input";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenuGroup,
  DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import { useI18n } from "@/core/i18n/hooks";
import { useModels } from "@/core/models/hooks";
import { useSkills } from "@/core/skills/hooks";
import type { AgentThreadContext } from "@/core/threads";
import { textOfMessage } from "@/core/threads/utils";
import { cn } from "@/lib/utils";

import {
  ModelSelector,
  ModelSelectorContent,
  ModelSelectorInput,
  ModelSelectorItem,
  ModelSelectorList,
  ModelSelectorName,
  ModelSelectorTrigger,
} from "../ai-elements/model-selector";
import { Suggestion, Suggestions } from "../ai-elements/suggestion";

import { useThread } from "./messages/context";
import { ModeHoverGuide } from "./mode-hover-guide";
import { InlineSelectedTag, type SelectedTag } from "./scenario/selected-tags";
import { SkillPicker } from "./slash-overlay";
import {
  getSlashAtCursor,
  getMatchingSkillSuggestions,
  parseSlashPrefix,
} from "./slash-suggestions";
import { Tooltip } from "./tooltip";

type InputMode = "flash" | "thinking" | "pro" | "ultra";

function highlightPlaceholder(text: string, root: HTMLElement | null) {
  if (!root) return;
  const textarea = root.querySelector<HTMLTextAreaElement>("textarea");
  if (!textarea) return;
  const selEnd = text.lastIndexOf("]");
  if (selEnd === -1) return;
  const selStart = text.lastIndexOf("[", selEnd);
  if (selStart === -1 || selStart > selEnd) return;
  textarea.setSelectionRange(selStart, selEnd + 1);
  textarea.focus();
}

function getResolvedMode(
  mode: InputMode | undefined,
  supportsThinking: boolean,
): InputMode {
  if (!supportsThinking && mode !== "flash") {
    return "flash";
  }
  if (mode) {
    return mode;
  }
  return supportsThinking ? "pro" : "flash";
}

export function InputBox({
  className,
  disabled,
  autoFocus,
  status = "ready",
  context,
  isWelcomeMode,
  threadId,
  initialValue,
  pendingTemplate,
  clearInjectedTemplateKey,
  allowedSkillNames,
  selectedTags = [],
  onPendingTemplateConsumed,
  onContextChange,
  onFollowupsVisibilityChange,
  onRemoveTag,
  onSubmit,
  onStop,
  ...props
}: Omit<ComponentProps<typeof PromptInput>, "onSubmit"> & {
  assistantId?: string | null;
  status?: ChatStatus;
  disabled?: boolean;
  context: Omit<
    AgentThreadContext,
    "thread_id" | "is_plan_mode" | "thinking_enabled" | "subagent_enabled"
  > & {
    mode: "flash" | "thinking" | "pro" | "ultra" | undefined;
    reasoning_effort?: "minimal" | "low" | "medium" | "high";
  };
  /**
   * Whether to render the input in welcome layout (vertically centered,
   * with hero + quick action suggestions).  This is purely a visual flag,
   * decoupled from "the backend has created the thread" — see issue #2746.
   */
  isWelcomeMode?: boolean;
  threadId: string;
  initialValue?: string;
  pendingTemplate?: string | null;
  clearInjectedTemplateKey?: number;
  allowedSkillNames?: readonly string[];
  selectedTags?: SelectedTag[];
  onPendingTemplateConsumed?: () => void;
  onContextChange?: (
    context: Omit<
      AgentThreadContext,
      "thread_id" | "is_plan_mode" | "thinking_enabled" | "subagent_enabled"
    > & {
      mode: "flash" | "thinking" | "pro" | "ultra" | undefined;
      reasoning_effort?: "minimal" | "low" | "medium" | "high";
    },
  ) => void;
  onFollowupsVisibilityChange?: (visible: boolean) => void;
  onRemoveTag?: (id: string) => void;
  onSubmit?: (message: PromptInputMessage) => void | Promise<void>;
  onStop?: () => void;
}) {
  const { t } = useI18n();
  const [modelDialogOpen, setModelDialogOpen] = useState(false);
  const { models } = useModels();
  const { thread, isMock } = useThread();
  const { textInput } = usePromptInputController();
  const promptRootRef = useRef<HTMLDivElement | null>(null);
  const selectedTagsRef = useRef<HTMLDivElement | null>(null);
  const [selectedTagsOffset, setSelectedTagsOffset] = useState(0);

  const [followups, setFollowups] = useState<string[]>([]);
  const [followupsHidden, setFollowupsHidden] = useState(false);
  const [followupsLoading, setFollowupsLoading] = useState(false);
  const lastGeneratedForAiIdRef = useRef<string | null>(null);
  const injectedTemplateRef = useRef<string | null>(null);
  const lastTemplateResetKeyRef = useRef(clearInjectedTemplateKey);
  const wasStreamingRef = useRef(false);
  const messagesRef = useRef(thread.messages);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingSuggestion, setPendingSuggestion] = useState<string | null>(
    null,
  );
  const pendingSourceRef = useRef<"followup" | "cascade">("followup");

  const { skills } = useSkills();
  const [slashState, setSlashState] = useState<{
    open: boolean;
    query: string;
    start: number;
    end: number;
    activeIndex: number;
  }>({ open: false, query: "", start: 0, end: 0, activeIndex: 0 });

  useEffect(() => {
    if (selectedTags.length > 0 && promptRootRef.current) {
      const textarea =
        promptRootRef.current.querySelector<HTMLTextAreaElement>("textarea");
      if (textarea) {
        textarea.focus();
        textarea.setSelectionRange(0, 0);
      }
    }
  }, [selectedTags]);

  useLayoutEffect(() => {
    const element = selectedTagsRef.current;
    if (!element || selectedTags.length === 0) {
      setSelectedTagsOffset(0);
      return;
    }

    setSelectedTagsOffset(element.offsetWidth + 12);
  }, [selectedTags]);

  useEffect(() => {
    if (models.length === 0) {
      return;
    }
    const currentModel = models.find((m) => m.name === context.model_name);
    const fallbackModel = currentModel ?? models[0]!;
    const supportsThinking = fallbackModel.supports_thinking ?? false;
    const nextModelName = fallbackModel.name;
    const nextMode = getResolvedMode(context.mode, supportsThinking);

    if (context.model_name === nextModelName && context.mode === nextMode) {
      return;
    }

    onContextChange?.({
      ...context,
      model_name: nextModelName,
      mode: nextMode,
    });
  }, [context, models, onContextChange]);

  const selectedModel = useMemo(() => {
    if (models.length === 0) {
      return undefined;
    }
    return models.find((m) => m.name === context.model_name) ?? models[0];
  }, [context.model_name, models]);

  const resolvedModelName = selectedModel?.name;

  const supportThinking = useMemo(
    () => selectedModel?.supports_thinking ?? false,
    [selectedModel],
  );

  const supportReasoningEffort = useMemo(
    () => selectedModel?.supports_reasoning_effort ?? false,
    [selectedModel],
  );

  const handleModelSelect = useCallback(
    (model_name: string) => {
      const model = models.find((m) => m.name === model_name);
      if (!model) {
        return;
      }
      onContextChange?.({
        ...context,
        model_name,
        mode: getResolvedMode(context.mode, model.supports_thinking ?? false),
        reasoning_effort: context.reasoning_effort,
      });
      setModelDialogOpen(false);
    },
    [onContextChange, context, models],
  );

  const handleModeSelect = useCallback(
    (mode: InputMode) => {
      onContextChange?.({
        ...context,
        mode: getResolvedMode(mode, supportThinking),
        reasoning_effort:
          mode === "ultra"
            ? "high"
            : mode === "pro"
              ? "medium"
              : mode === "thinking"
                ? "low"
                : "minimal",
      });
    },
    [onContextChange, context, supportThinking],
  );

  const handleReasoningEffortSelect = useCallback(
    (effort: "minimal" | "low" | "medium" | "high") => {
      onContextChange?.({
        ...context,
        reasoning_effort: effort,
      });
    },
    [onContextChange, context],
  );

  const handleSubmit = useCallback(
    (message: PromptInputMessage) => {
      if (status === "streaming") {
        onStop?.();
        return;
      }
      if (!message.text.trim() && message.files.length === 0) {
        return;
      }
      setFollowups([]);
      setFollowupsHidden(false);
      setFollowupsLoading(false);

      const parsed = parseSlashPrefix(message.text);
      const skillName = parsed?.skillName ?? null;
      const cleanText = parsed ? parsed.rest : message.text;
      const cleanMessage = { ...message, text: cleanText };

      const contextWithSkill = skillName
        ? { ...context, skill_name: skillName }
        : context;

      if (resolvedModelName && context.model_name !== resolvedModelName) {
        onContextChange?.({
          ...contextWithSkill,
          model_name: resolvedModelName,
          mode: getResolvedMode(
            context.mode,
            selectedModel?.supports_thinking ?? false,
          ),
        });
        return new Promise<void>((resolve, reject) => {
          setTimeout(() => {
            Promise.resolve(onSubmit?.(cleanMessage))
              .then(resolve)
              .catch(reject);
          }, 0);
        });
      }

      return onSubmit?.(cleanMessage);
    },
    [
      context,
      onContextChange,
      onSubmit,
      onStop,
      resolvedModelName,
      selectedModel?.supports_thinking,
      status,
    ],
  );

  const requestFormSubmit = useCallback(() => {
    const form = promptRootRef.current?.querySelector("form");
    form?.requestSubmit();
  }, []);

  const handleFollowupClick = useCallback(
    (suggestion: string) => {
      if (status === "streaming") {
        return;
      }
      const current = (textInput.value ?? "").trim();
      if (current) {
        pendingSourceRef.current = "followup";
        setPendingSuggestion(suggestion);
        setConfirmOpen(true);
        return;
      }
      textInput.setInput(suggestion);
      setFollowupsHidden(true);
      setTimeout(() => requestFormSubmit(), 0);
    },
    [requestFormSubmit, status, textInput],
  );

  const confirmReplaceAndSend = useCallback(() => {
    if (!pendingSuggestion) {
      setConfirmOpen(false);
      return;
    }
    const isCascade = pendingSourceRef.current === "cascade";
    textInput.setInput(pendingSuggestion);
    setFollowupsHidden(true);
    setConfirmOpen(false);
    setPendingSuggestion(null);
    pendingSourceRef.current = "followup";
    if (isCascade) {
      setTimeout(() => {
        highlightPlaceholder(pendingSuggestion, promptRootRef.current);
      }, 50);
    } else {
      setTimeout(() => requestFormSubmit(), 0);
    }
  }, [pendingSuggestion, requestFormSubmit, textInput]);

  const confirmAppendAndSend = useCallback(() => {
    if (!pendingSuggestion) {
      setConfirmOpen(false);
      return;
    }
    const isCascade = pendingSourceRef.current === "cascade";
    const current = (textInput.value ?? "").trim();
    const next = current
      ? `${current}\n${pendingSuggestion}`
      : pendingSuggestion;
    textInput.setInput(next);
    setFollowupsHidden(true);
    setConfirmOpen(false);
    setPendingSuggestion(null);
    pendingSourceRef.current = "followup";
    if (isCascade) {
      setTimeout(() => {
        highlightPlaceholder(next, promptRootRef.current);
      }, 50);
    } else {
      setTimeout(() => requestFormSubmit(), 0);
    }
  }, [pendingSuggestion, requestFormSubmit, textInput]);

  const handleCursorChange = useCallback(
    (pos: number) => {
      const match = getSlashAtCursor(textInput.value ?? "", pos);
      if (match) {
        setSlashState({ open: true, ...match, activeIndex: 0 });
      } else {
        setSlashState((prev) => ({ ...prev, open: false }));
      }
    },
    [textInput],
  );

  const handleSlashSelect = useCallback(
    (skillName: string) => {
      const value = textInput.value ?? "";
      const before = value.slice(0, slashState.start);
      const after = value.slice(slashState.end);
      const newText = `${before}/${skillName} ${after}`;
      textInput.setInput(newText);
      setSlashState({
        open: false,
        query: "",
        start: 0,
        end: 0,
        activeIndex: 0,
      });
      const textarea = promptRootRef.current?.querySelector("textarea");
      if (textarea) {
        const cursorPos = before.length + skillName.length + 2;
        setTimeout(() => {
          textarea.setSelectionRange(cursorPos, cursorPos);
          textarea.focus();
        }, 0);
      }
    },
    [textInput, slashState.start, slashState.end],
  );

  const handleSlashKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (!slashState.open) return;
      const suggestions = getMatchingSkillSuggestions(
        skills,
        slashState.query,
        allowedSkillNames,
      );
      if (suggestions.length === 0) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSlashState((prev) => ({
          ...prev,
          activeIndex: (prev.activeIndex + 1) % suggestions.length,
        }));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSlashState((prev) => ({
          ...prev,
          activeIndex:
            (prev.activeIndex - 1 + suggestions.length) % suggestions.length,
        }));
        return;
      }
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSlashSelect(suggestions[slashState.activeIndex]!.name);
        return;
      }
      if (e.key === "Tab") {
        e.preventDefault();
        handleSlashSelect(suggestions[slashState.activeIndex]!.name);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setSlashState((prev) => ({ ...prev, open: false }));
        return;
      }
    },
    [
      slashState.open,
      slashState.query,
      slashState.activeIndex,
      skills,
      allowedSkillNames,
      handleSlashSelect,
    ],
  );

  const handleSkillPickerOpen = useCallback(() => {
    const value = textInput.value ?? "";
    const textarea = promptRootRef.current?.querySelector("textarea");
    const cursor = textarea?.selectionStart ?? value.length;
    setSlashState({
      open: true,
      query: "",
      start: cursor,
      end: cursor,
      activeIndex: 0,
    });
    textarea?.focus();
  }, [textInput]);

  const showFollowups =
    !disabled &&
    !isWelcomeMode &&
    !followupsHidden &&
    (followupsLoading || followups.length > 0);

  const handlePromptSurfaceClick = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      const target = event.target as HTMLElement;
      if (
        target.closest(
          "button, textarea, input, [role='dialog'], [role='menu']",
        )
      ) {
        return;
      }
      promptRootRef.current
        ?.querySelector<HTMLTextAreaElement>("textarea")
        ?.focus();
    },
    [],
  );

  useEffect(() => {
    onFollowupsVisibilityChange?.(showFollowups);
  }, [onFollowupsVisibilityChange, showFollowups]);

  useEffect(() => {
    return () => onFollowupsVisibilityChange?.(false);
  }, [onFollowupsVisibilityChange]);

  useEffect(() => {
    if (!pendingTemplate) return;
    textInput.setInput(pendingTemplate);
    injectedTemplateRef.current = pendingTemplate;
    onPendingTemplateConsumed?.();
    setTimeout(() => {
      highlightPlaceholder(pendingTemplate, promptRootRef.current);
    }, 50);
  }, [pendingTemplate, onPendingTemplateConsumed, textInput]);

  useEffect(() => {
    if (clearInjectedTemplateKey === undefined) return;
    if (lastTemplateResetKeyRef.current === clearInjectedTemplateKey) return;
    lastTemplateResetKeyRef.current = clearInjectedTemplateKey;
    if (injectedTemplateRef.current === textInput.value) {
      textInput.clear();
    }
    injectedTemplateRef.current = null;
  }, [clearInjectedTemplateKey, textInput]);

  useEffect(() => {
    messagesRef.current = thread.messages;
  }, [thread.messages]);

  useEffect(() => {
    const streaming = status === "streaming";
    const wasStreaming = wasStreamingRef.current;
    wasStreamingRef.current = streaming;
    if (!wasStreaming || streaming) {
      return;
    }

    if (disabled || isMock) {
      return;
    }

    const lastAi = [...messagesRef.current]
      .reverse()
      .find((m) => m.type === "ai");
    const lastAiId = lastAi?.id ?? null;
    if (!lastAiId || lastAiId === lastGeneratedForAiIdRef.current) {
      return;
    }
    lastGeneratedForAiIdRef.current = lastAiId;

    const recent = messagesRef.current
      .filter((m) => m.type === "human" || m.type === "ai")
      .map((m) => {
        const role = m.type === "human" ? "user" : "assistant";
        const content = textOfMessage(m) ?? "";
        return { role, content };
      })
      .filter((m) => m.content.trim().length > 0)
      .slice(-6);

    if (recent.length === 0) {
      return;
    }

    const controller = new AbortController();
    setFollowupsHidden(false);
    setFollowupsLoading(true);
    setFollowups([]);

    fetch(`${getBackendBaseURL()}/api/threads/${threadId}/suggestions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: recent,
        n: 3,
        model_name: context.model_name ?? undefined,
      }),
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok) {
          return { suggestions: [] as string[] };
        }
        return (await res.json()) as { suggestions?: string[] };
      })
      .then((data) => {
        const suggestions = (data.suggestions ?? [])
          .map((s) => (typeof s === "string" ? s.trim() : ""))
          .filter((s) => s.length > 0)
          .slice(0, 5);
        setFollowups(suggestions);
      })
      .catch(() => {
        setFollowups([]);
      })
      .finally(() => {
        setFollowupsLoading(false);
      });

    return () => controller.abort();
  }, [context.model_name, disabled, isMock, status, threadId]);

  return (
    <div
      ref={promptRootRef}
      data-testid="input-box"
      onClick={handlePromptSurfaceClick}
      className={cn(
        "relative flex flex-col",
        isWelcomeMode ? "gap-5" : "gap-2",
      )}
    >
      {showFollowups && (
        <div className="flex items-center justify-center pb-1">
          <div className="flex items-center gap-2">
            {followupsLoading ? (
              <div className="text-muted-foreground bg-background/80 type-body rounded-full border px-4 py-1.5 backdrop-blur-sm">
                {t.inputBox.followupLoading}
              </div>
            ) : (
              <Suggestions className="w-fit items-center">
                {followups.map((s) => (
                  <Suggestion
                    key={s}
                    className="py-1.5"
                    suggestion={s}
                    onClick={() => handleFollowupClick(s)}
                  />
                ))}
                <Button
                  aria-label={t.common.close}
                  className="text-muted-foreground type-body h-auto cursor-pointer rounded-full px-2.5 py-1.5 font-normal"
                  variant="outline"
                  size="sm"
                  type="button"
                  onClick={() => setFollowupsHidden(true)}
                >
                  <XIcon className="size-4" />
                </Button>
              </Suggestions>
            )}
          </div>
        </div>
      )}
      <PromptInput
        className={cn(
          "bg-background/85 rounded-2xl backdrop-blur-sm transition-all duration-300 ease-out *:data-[slot='input-group']:items-start *:data-[slot='input-group']:rounded-2xl",
          className,
        )}
        disabled={disabled}
        globalDrop
        multiple
        onSubmit={handleSubmit}
        {...props}
      >
        <PromptInputAttachments>
          {(attachment) => <PromptInputAttachment data={attachment} />}
        </PromptInputAttachments>
        <PromptInputBody className="absolute top-0 right-0 left-0 z-3">
          <div className="relative">
            {selectedTags.length > 0 && onRemoveTag && (
              <div
                ref={selectedTagsRef}
                className="absolute top-3 left-4 z-4 flex max-w-[calc(100%-2rem)] flex-nowrap items-center gap-1 overflow-x-auto pr-1 [&::-webkit-scrollbar]:hidden"
                data-testid="inline-selected-tags"
              >
                {selectedTags.map((tag) => (
                  <InlineSelectedTag
                    key={tag.id}
                    tag={tag}
                    onRemove={onRemoveTag}
                  />
                ))}
              </div>
            )}
            <PromptInputTextarea
              className={cn(
                "size-full text-left placeholder:text-left",
                isWelcomeMode &&
                  "workbench-input-textarea type-body min-h-40 leading-7",
                "pt-3",
              )}
              style={{ textIndent: selectedTagsOffset }}
              disabled={disabled}
              placeholder={t.inputBox.placeholder}
              autoFocus={autoFocus}
              defaultValue={initialValue}
              data-testid="chat-input"
              onCursorChange={handleCursorChange}
              externalOnKeyDown={handleSlashKeyDown}
            />
            {slashState.open && (
              <SkillPicker
                skills={skills}
                allowedSkillNames={allowedSkillNames}
                query={slashState.query}
                activeIndex={slashState.activeIndex}
                title={t.inputBox.skill}
                onSelect={(skill) => handleSlashSelect(skill.name)}
                onClose={() =>
                  setSlashState((prev) => ({ ...prev, open: false }))
                }
              />
            )}
          </div>
        </PromptInputBody>
        <PromptInputFooter
          className={cn(
            "flex",
            isWelcomeMode &&
              "workbench-welcome-footer min-h-12 [&_button]:min-h-10",
          )}
        >
          <PromptInputTools>
            {/* TODO: Add more connectors here
          <PromptInputActionMenu>
            <PromptInputActionMenuTrigger className="px-2!" />
            <PromptInputActionMenuContent>
              <PromptInputActionAddAttachments
                label={t.inputBox.addAttachments}
              />
            </PromptInputActionMenuContent>
          </PromptInputActionMenu> */}
            <AddAttachmentsButton className="px-2!" />
            <PromptInputActionMenu>
              <ModeHoverGuide
                mode={
                  context.mode === "flash" ||
                  context.mode === "thinking" ||
                  context.mode === "pro" ||
                  context.mode === "ultra"
                    ? context.mode
                    : "flash"
                }
              >
                <PromptInputActionMenuTrigger
                  className="gap-1! px-2!"
                  data-testid="mode-selector-trigger"
                  aria-label={t.inputBox.mode}
                >
                  <div>
                    {context.mode === "flash" && <ZapIcon className="size-3" />}
                    {context.mode === "thinking" && (
                      <LightbulbIcon className="size-3" />
                    )}
                    {context.mode === "pro" && (
                      <GraduationCapIcon className="size-3" />
                    )}
                    {context.mode === "ultra" && (
                      <RocketIcon className="size-3 text-[#dabb5e]" />
                    )}
                  </div>
                  <div
                    className={cn(
                      "type-body font-normal",
                      context.mode === "ultra" ? "golden-text" : "",
                    )}
                  >
                    {(context.mode === "flash" && t.inputBox.flashMode) ||
                      (context.mode === "thinking" &&
                        t.inputBox.reasoningMode) ||
                      (context.mode === "pro" && t.inputBox.proMode) ||
                      (context.mode === "ultra" && t.inputBox.ultraMode)}
                  </div>
                </PromptInputActionMenuTrigger>
              </ModeHoverGuide>
              <PromptInputActionMenuContent className="w-80">
                <DropdownMenuGroup>
                  <DropdownMenuLabel className="text-muted-foreground type-body">
                    {t.inputBox.mode}
                  </DropdownMenuLabel>
                  <PromptInputActionMenu>
                    <PromptInputActionMenuItem
                      className={cn(
                        context.mode === "flash"
                          ? "text-accent-foreground"
                          : "text-muted-foreground/65",
                      )}
                      onSelect={() => handleModeSelect("flash")}
                    >
                      <div className="flex flex-col gap-2">
                        <div className="flex items-center gap-1 font-bold">
                          <ZapIcon
                            className={cn(
                              "mr-2 size-4",
                              context.mode === "flash" &&
                                "text-accent-foreground",
                            )}
                          />
                          {t.inputBox.flashMode}
                        </div>
                        <div className="type-body pl-7">
                          {t.inputBox.flashModeDescription}
                        </div>
                      </div>
                      {context.mode === "flash" ? (
                        <CheckIcon className="ml-auto size-4" />
                      ) : (
                        <div className="ml-auto size-4" />
                      )}
                    </PromptInputActionMenuItem>
                    {supportThinking && (
                      <PromptInputActionMenuItem
                        className={cn(
                          context.mode === "thinking"
                            ? "text-accent-foreground"
                            : "text-muted-foreground/65",
                        )}
                        onSelect={() => handleModeSelect("thinking")}
                      >
                        <div className="flex flex-col gap-2">
                          <div className="flex items-center gap-1 font-bold">
                            <LightbulbIcon
                              className={cn(
                                "mr-2 size-4",
                                context.mode === "thinking" &&
                                  "text-accent-foreground",
                              )}
                            />
                            {t.inputBox.reasoningMode}
                          </div>
                          <div className="type-body pl-7">
                            {t.inputBox.reasoningModeDescription}
                          </div>
                        </div>
                        {context.mode === "thinking" ? (
                          <CheckIcon className="ml-auto size-4" />
                        ) : (
                          <div className="ml-auto size-4" />
                        )}
                      </PromptInputActionMenuItem>
                    )}
                    <PromptInputActionMenuItem
                      className={cn(
                        context.mode === "pro"
                          ? "text-accent-foreground"
                          : "text-muted-foreground/65",
                      )}
                      onSelect={() => handleModeSelect("pro")}
                    >
                      <div className="flex flex-col gap-2">
                        <div className="flex items-center gap-1 font-bold">
                          <GraduationCapIcon
                            className={cn(
                              "mr-2 size-4",
                              context.mode === "pro" &&
                                "text-accent-foreground",
                            )}
                          />
                          {t.inputBox.proMode}
                        </div>
                        <div className="type-body pl-7">
                          {t.inputBox.proModeDescription}
                        </div>
                      </div>
                      {context.mode === "pro" ? (
                        <CheckIcon className="ml-auto size-4" />
                      ) : (
                        <div className="ml-auto size-4" />
                      )}
                    </PromptInputActionMenuItem>
                    <PromptInputActionMenuItem
                      className={cn(
                        context.mode === "ultra"
                          ? "text-accent-foreground"
                          : "text-muted-foreground/65",
                      )}
                      onSelect={() => handleModeSelect("ultra")}
                    >
                      <div className="flex flex-col gap-2">
                        <div className="flex items-center gap-1 font-bold">
                          <RocketIcon
                            className={cn(
                              "mr-2 size-4",
                              context.mode === "ultra" && "text-[#dabb5e]",
                            )}
                          />
                          <div
                            className={cn(
                              context.mode === "ultra" && "golden-text",
                            )}
                          >
                            {t.inputBox.ultraMode}
                          </div>
                        </div>
                        <div className="type-body pl-7">
                          {t.inputBox.ultraModeDescription}
                        </div>
                      </div>
                      {context.mode === "ultra" ? (
                        <CheckIcon className="ml-auto size-4" />
                      ) : (
                        <div className="ml-auto size-4" />
                      )}
                    </PromptInputActionMenuItem>
                  </PromptInputActionMenu>
                </DropdownMenuGroup>
              </PromptInputActionMenuContent>
            </PromptInputActionMenu>
            {supportReasoningEffort && context.mode !== "flash" && (
              <PromptInputActionMenu>
                <PromptInputActionMenuTrigger className="gap-1! px-2!">
                  <div className="type-body font-normal">
                    {t.inputBox.reasoningEffort}:
                    {context.reasoning_effort === "minimal" &&
                      " " + t.inputBox.reasoningEffortMinimal}
                    {context.reasoning_effort === "low" &&
                      " " + t.inputBox.reasoningEffortLow}
                    {context.reasoning_effort === "medium" &&
                      " " + t.inputBox.reasoningEffortMedium}
                    {context.reasoning_effort === "high" &&
                      " " + t.inputBox.reasoningEffortHigh}
                  </div>
                </PromptInputActionMenuTrigger>
                <PromptInputActionMenuContent className="w-70">
                  <DropdownMenuGroup>
                    <DropdownMenuLabel className="text-muted-foreground type-body">
                      {t.inputBox.reasoningEffort}
                    </DropdownMenuLabel>
                    <PromptInputActionMenu>
                      <PromptInputActionMenuItem
                        className={cn(
                          context.reasoning_effort === "minimal"
                            ? "text-accent-foreground"
                            : "text-muted-foreground/65",
                        )}
                        onSelect={() => handleReasoningEffortSelect("minimal")}
                      >
                        <div className="flex flex-col gap-2">
                          <div className="flex items-center gap-1 font-bold">
                            {t.inputBox.reasoningEffortMinimal}
                          </div>
                          <div className="type-body pl-2">
                            {t.inputBox.reasoningEffortMinimalDescription}
                          </div>
                        </div>
                        {context.reasoning_effort === "minimal" ? (
                          <CheckIcon className="ml-auto size-4" />
                        ) : (
                          <div className="ml-auto size-4" />
                        )}
                      </PromptInputActionMenuItem>
                      <PromptInputActionMenuItem
                        className={cn(
                          context.reasoning_effort === "low"
                            ? "text-accent-foreground"
                            : "text-muted-foreground/65",
                        )}
                        onSelect={() => handleReasoningEffortSelect("low")}
                      >
                        <div className="flex flex-col gap-2">
                          <div className="flex items-center gap-1 font-bold">
                            {t.inputBox.reasoningEffortLow}
                          </div>
                          <div className="type-body pl-2">
                            {t.inputBox.reasoningEffortLowDescription}
                          </div>
                        </div>
                        {context.reasoning_effort === "low" ? (
                          <CheckIcon className="ml-auto size-4" />
                        ) : (
                          <div className="ml-auto size-4" />
                        )}
                      </PromptInputActionMenuItem>
                      <PromptInputActionMenuItem
                        className={cn(
                          context.reasoning_effort === "medium" ||
                            !context.reasoning_effort
                            ? "text-accent-foreground"
                            : "text-muted-foreground/65",
                        )}
                        onSelect={() => handleReasoningEffortSelect("medium")}
                      >
                        <div className="flex flex-col gap-2">
                          <div className="flex items-center gap-1 font-bold">
                            {t.inputBox.reasoningEffortMedium}
                          </div>
                          <div className="type-body pl-2">
                            {t.inputBox.reasoningEffortMediumDescription}
                          </div>
                        </div>
                        {context.reasoning_effort === "medium" ||
                        !context.reasoning_effort ? (
                          <CheckIcon className="ml-auto size-4" />
                        ) : (
                          <div className="ml-auto size-4" />
                        )}
                      </PromptInputActionMenuItem>
                      <PromptInputActionMenuItem
                        className={cn(
                          context.reasoning_effort === "high"
                            ? "text-accent-foreground"
                            : "text-muted-foreground/65",
                        )}
                        onSelect={() => handleReasoningEffortSelect("high")}
                      >
                        <div className="flex flex-col gap-2">
                          <div className="flex items-center gap-1 font-bold">
                            {t.inputBox.reasoningEffortHigh}
                          </div>
                          <div className="type-body pl-2">
                            {t.inputBox.reasoningEffortHighDescription}
                          </div>
                        </div>
                        {context.reasoning_effort === "high" ? (
                          <CheckIcon className="ml-auto size-4" />
                        ) : (
                          <div className="ml-auto size-4" />
                        )}
                      </PromptInputActionMenuItem>
                    </PromptInputActionMenu>
                  </DropdownMenuGroup>
                </PromptInputActionMenuContent>
              </PromptInputActionMenu>
            )}
          </PromptInputTools>
          <PromptInputTools>
            <ModelSelector
              open={modelDialogOpen}
              onOpenChange={setModelDialogOpen}
            >
              <Tooltip content={t.inputBox.selectModel}>
                <ModelSelectorTrigger asChild>
                  <PromptInputButton
                    data-testid="model-selector-trigger"
                    aria-label={t.inputBox.selectModel}
                  >
                    <div className="flex min-w-0 flex-col items-start text-left">
                      <ModelSelectorName className="type-body font-normal">
                        {selectedModel?.display_name}
                      </ModelSelectorName>
                    </div>
                  </PromptInputButton>
                </ModelSelectorTrigger>
              </Tooltip>
              <ModelSelectorContent>
                <ModelSelectorInput placeholder={t.inputBox.searchModels} />
                <ModelSelectorList>
                  {models.map((m) => (
                    <ModelSelectorItem
                      key={m.name}
                      value={m.name}
                      onSelect={() => handleModelSelect(m.name)}
                    >
                      <div className="flex min-w-0 flex-1 flex-col">
                        <ModelSelectorName>{m.display_name}</ModelSelectorName>
                        <span className="text-muted-foreground type-compact truncate">
                          {m.model}
                        </span>
                      </div>
                      {m.name === context.model_name ? (
                        <CheckIcon className="ml-auto size-4" />
                      ) : (
                        <div className="ml-auto size-4" />
                      )}
                    </ModelSelectorItem>
                  ))}
                </ModelSelectorList>
              </ModelSelectorContent>
            </ModelSelector>
            <Tooltip content={t.inputBox.invokeSkill}>
              <PromptInputButton
                data-testid="skill-selector-trigger"
                aria-label={t.inputBox.invokeSkill}
                onClick={handleSkillPickerOpen}
              >
                <SparklesIcon className="size-4" />
                <span className="type-body font-normal">
                  {t.inputBox.skill}
                </span>
              </PromptInputButton>
            </Tooltip>
            <PromptInputSubmit
              className="rounded-full"
              disabled={disabled}
              variant="outline"
              status={status}
              data-testid="submit-button"
            />
          </PromptInputTools>
        </PromptInputFooter>
        {!isWelcomeMode && (
          <div className="bg-background absolute right-0 -bottom-[17px] left-0 z-0 h-4"></div>
        )}
      </PromptInput>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t.inputBox.followupConfirmTitle}</DialogTitle>
            <DialogDescription>
              {t.inputBox.followupConfirmDescription}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button variant="secondary" onClick={confirmAppendAndSend}>
              {t.inputBox.followupConfirmAppend}
            </Button>
            <Button onClick={confirmReplaceAndSend}>
              {t.inputBox.followupConfirmReplace}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function AddAttachmentsButton({ className }: { className?: string }) {
  const { t } = useI18n();
  const attachments = usePromptInputAttachments();
  return (
    <Tooltip content={t.inputBox.addAttachments}>
      <PromptInputButton
        className={cn("px-2!", className)}
        aria-label={t.inputBox.addAttachments}
        onClick={() => attachments.openFileDialog()}
      >
        <PaperclipIcon className="size-3" />
      </PromptInputButton>
    </Tooltip>
  );
}
