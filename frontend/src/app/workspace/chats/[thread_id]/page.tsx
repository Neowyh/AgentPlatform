"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { type PromptInputMessage } from "@/components/ai-elements/prompt-input";
import { ArtifactTrigger } from "@/components/workspace/artifacts";
import {
  ChatBox,
  useSpecificChatMode,
  useThreadChat,
} from "@/components/workspace/chats";
import { ExportTrigger } from "@/components/workspace/export-trigger";
import { InputBox } from "@/components/workspace/input-box";
import {
  MessageList,
  MESSAGE_LIST_DEFAULT_PADDING_BOTTOM,
} from "@/components/workspace/messages";
import { ThreadContext } from "@/components/workspace/messages/context";
import { ScenarioCascadeBar } from "@/components/workspace/scenario";
import { ScenarioTabs } from "@/components/workspace/scenario/scenario-tabs";
import type { SelectedTag } from "@/components/workspace/scenario/selected-tags";
import { ThreadTitle } from "@/components/workspace/thread-title";
import { TodoList } from "@/components/workspace/todo-list";
import { TokenUsageIndicator } from "@/components/workspace/token-usage-indicator";
import { Welcome } from "@/components/workspace/welcome";
import { useAgent, useAgents } from "@/core/agents/hooks";
import { getAPIClient } from "@/core/api";
import { useI18n } from "@/core/i18n/hooks";
import { useModels } from "@/core/models/hooks";
import { useNotification } from "@/core/notification/hooks";
import { useScenarioBinding } from "@/core/scenarios/binding";
import { getChipsByPill } from "@/core/scenarios/config";
import type { ScenarioId } from "@/core/scenarios/types";
import { useLocalSettings, useThreadSettings } from "@/core/settings";
import { useSkills } from "@/core/skills/hooks";
import {
  useThreadStream,
  useThreadTokenUsage,
  useThreads,
} from "@/core/threads/hooks";
import { threadTokenUsageToTokenUsage } from "@/core/threads/token-usage";
import {
  pathOfThread,
  textOfMessage,
  titleOfThread,
} from "@/core/threads/utils";
import { env } from "@/env";
import { cn } from "@/lib/utils";

function RecentTaskCards({
  threads,
}: {
  threads: Array<Parameters<typeof titleOfThread>[0]>;
}) {
  if (threads.length === 0) return null;
  return (
    <section className="workbench-recent-tasks" aria-label="最近任务">
      <p className="workbench-module-guide">
        <span className="workbench-guide-question">工作复盘？</span>
        <span className="workbench-guide-answer">iDeer带你回到过去</span>
      </p>
      <div className="workbench-recent-grid">
        {threads.slice(0, 3).map((thread) => {
          const values = thread.values as Record<string, unknown> | undefined;
          const metadata = thread.metadata as
            | Record<string, unknown>
            | undefined;
          const context = thread.context;
          const messages = Array.isArray(values?.messages)
            ? values.messages
            : [];
          const latestSummary = [...messages]
            .reverse()
            .map((message) =>
              textOfMessage(message as Parameters<typeof textOfMessage>[0]),
            )
            .find((text): text is string => Boolean(text?.trim()));
          const taskType =
            context?.task_label ??
            (typeof metadata?.task_type === "string"
              ? metadata.task_type
              : undefined) ??
            "对话任务";
          const status =
            (typeof metadata?.status === "string"
              ? metadata.status
              : undefined) ??
            (typeof values?.status === "string" ? values.status : undefined) ??
            "进行中";

          return (
            <Link
              key={thread.thread_id}
              href={pathOfThread(thread)}
              className="workbench-recent-card"
            >
              <span className="workbench-recent-summary">
                {titleOfThread(thread)}
              </span>
              <span className="workbench-recent-meta">
                {taskType} · {status}
                {thread.updated_at ? ` · ${thread.updated_at}` : ""}
              </span>
              {latestSummary && (
                <span className="workbench-recent-detail">{latestSummary}</span>
              )}
            </Link>
          );
        })}
      </div>
    </section>
  );
}

export default function ChatPage() {
  const { t } = useI18n();
  const {
    threadId,
    setThreadId,
    isNewThread,
    setIsNewThread,
    isMock,
    selectedConnector,
  } = useThreadChat();
  // `isNewThread` tracks whether the backend has the thread yet — gates the
  // SDK's history fetch (see issue #2746).  `isWelcomeMode` is the visual
  // welcome layout (centered input, hero, quick actions); we flip it to false
  // the moment the user submits so the UI animates immediately, even though
  // `isNewThread` stays true until the backend actually creates the thread.
  const [isWelcomeMode, setIsWelcomeMode] = useState(isNewThread);
  const [settings, setSettings] = useThreadSettings(threadId);
  const [localSettings, setLocalSettings] = useLocalSettings();
  const { tokenUsageEnabled } = useModels();
  const {
    selectedScenario,
    selectedPill,
    selectedChip,
    selectScenario,
    togglePill,
    toggleChip,
    activeBinding,
    resetSelection,
  } = useScenarioBinding();
  const { agents } = useAgents();
  const { data: recentThreads = [] } = useThreads();
  const selectedAgent = agents.find(
    (item) => (item.slug ?? item.name) === selectedPill?.agentSlug,
  );
  const { skills } = useSkills();
  const selectedTask = selectedChip
    ? getChipsByPill(selectedChip.scenarioId, selectedChip.agentSlug).find(
        (item) => item.taskId === selectedChip.taskId,
      )
    : undefined;
  const selectedSkill = selectedChip
    ? skills.find(
        (skill) => (skill.slug ?? skill.name) === selectedTask?.skillName,
      )
    : undefined;
  const { agent: selectedAgentDetails } = useAgent(selectedAgent?.resource_id);
  const [pendingTemplate, setPendingTemplate] = useState<string | null>(null);
  const [templateResetKey, setTemplateResetKey] = useState(0);

  const activeScenario = selectedScenario;
  const handleSelectScenario = useCallback(
    (scenario: ScenarioId) => {
      selectScenario(scenario);
      setTemplateResetKey((key) => key + 1);
    },
    [selectScenario],
  );

  const selectedTags: SelectedTag[] = activeBinding.tags.map((tag) => ({
    id: tag.id,
    label:
      tag.kind === "task"
        ? (selectedSkill?.name ?? selectedTask?.label ?? tag.text)
        : tag.text,
  }));

  useEffect(() => {
    setPendingTemplate(activeBinding?.promptTemplate ?? null);
  }, [activeBinding?.promptTemplate]);

  const allowedSkillNames = useMemo(() => {
    if (!selectedPill) return undefined;
    const agent = selectedAgentDetails;
    return (
      agent?.skills ??
      getChipsByPill(selectedPill.scenarioId, selectedPill.agentSlug).map(
        (chip) => chip.skillName,
      )
    );
  }, [selectedAgentDetails, selectedPill]);

  const selectionContext = useMemo(() => {
    const context = { ...settings.context };
    if (!selectedPill) {
      delete context.agent_name;
      delete context.agent_resource_id;
      delete context.skill_name;
      delete context.skill_resource_id;
      delete context.scenario_id;
      delete context.agent_label;
      delete context.task_id;
      delete context.task_label;
      delete context.prompt_template;
      context.connector_name = selectedConnector ?? undefined;
      return context;
    }
    const chip = selectedChip
      ? getChipsByPill(selectedChip.scenarioId, selectedChip.agentSlug).find(
          (item) => item.taskId === selectedChip.taskId,
        )
      : undefined;
    const nextContext = {
      ...context,
      scenario_id: selectedPill.scenarioId,
      agent_name: selectedPill.agentSlug,
      agent_resource_id: selectedAgent?.resource_id,
      agent_label: activeBinding?.agentName,
      skill_name: chip?.skillName,
      skill_resource_id: selectedSkill?.resource_id,
      task_id: chip?.taskId,
      task_label: chip?.label,
      prompt_template: chip?.promptTemplate,
      connector_name: selectedConnector ?? undefined,
      ...(selectedPill.agentSlug === "fault-zeroing"
        ? {
            evidence_mode: "hybrid",
          }
        : {}),
    };
    return nextContext;
  }, [
    activeBinding,
    selectedAgent,
    selectedSkill,
    settings.context,
    selectedPill,
    selectedChip,
    selectedConnector,
  ]);

  const handleRemoveTag = useCallback(
    (id: string) => {
      if (id === `agent:${selectedPill?.agentSlug}` && selectedPill) {
        togglePill(selectedPill.agentSlug);
        setPendingTemplate(null);
      } else if (id === `task:${selectedChip?.taskId}` && selectedChip) {
        toggleChip(selectedChip.taskId);
        setPendingTemplate(null);
      }
    },
    [selectedChip, selectedPill, toggleChip, togglePill],
  );

  useEffect(() => {
    resetSelection();
    setPendingTemplate(null);
  }, [threadId, resetSelection]);
  const threadTokenUsage = useThreadTokenUsage(
    isNewThread || isMock ? undefined : threadId,
    { enabled: tokenUsageEnabled && !isMock },
  );
  const backendTokenUsage = threadTokenUsageToTokenUsage(threadTokenUsage.data);
  const mountedRef = useRef(false);
  useSpecificChatMode();

  useEffect(() => {
    mountedRef.current = true;
  }, []);

  // Keep welcome layout in sync when navigating between threads (sidebar
  // clicks, "new chat" button).  Submitting in /chats/new flips the layout
  // via onSend below — `isNewThread` stays true until onStart, so this effect
  // is harmless during the submit transition.
  useEffect(() => {
    setIsWelcomeMode(isNewThread);
  }, [isNewThread]);

  const { showNotification } = useNotification();

  const {
    thread,
    pendingUsageMessages,
    sendMessage,
    isUploading,
    isHistoryLoading,
    hasMoreHistory,
    loadMoreHistory,
  } = useThreadStream({
    threadId: isNewThread ? undefined : threadId,
    context: selectionContext,
    isMock,
    prepareSubmit: async () => {
      const created = await getAPIClient().threads.create({
        metadata: {
          agent_name: selectedPill?.agentSlug,
        },
      });
      return { threadId: created.thread_id };
    },
    onThreadCreated: (createdThreadId) => {
      setThreadId(createdThreadId);
      setIsNewThread(false);
      history.replaceState(null, "", `/workspace/chats/${createdThreadId}`);
    },
    // onSend only animates the UI; do NOT flip `isNewThread` here — the
    // LangGraph SDK eagerly fetches /history the moment it receives a
    // thread id and assumes the thread exists on the backend (issue #2746).
    onSend: () => {
      setIsWelcomeMode(false);
    },
    onStart: (createdThreadId) => {
      setThreadId(createdThreadId);
      setIsNewThread(false);
      // ! Important: Never use next.js router for navigation in this case, otherwise it will cause the thread to re-mount and lose all states. Use native history API instead.
      history.replaceState(null, "", `/workspace/chats/${createdThreadId}`);
    },
    onFinish: (state) => {
      if (document.hidden || !document.hasFocus()) {
        let body = "Conversation finished";
        const lastMessage = state.messages.at(-1);
        if (lastMessage) {
          const textContent = textOfMessage(lastMessage);
          if (textContent) {
            body =
              textContent.length > 200
                ? textContent.substring(0, 200) + "..."
                : textContent;
          }
        }
        showNotification(state.title, { body });
      }
    },
  });

  const handleSubmit = useCallback(
    (message: PromptInputMessage) => {
      const sendPromise = sendMessage(threadId, message);
      if (message.files.length > 0) {
        return sendPromise;
      }
      void sendPromise;
    },
    [sendMessage, threadId],
  );
  const handleStop = useCallback(async () => {
    await thread.stop();
  }, [thread]);

  const tokenUsageInlineMode = tokenUsageEnabled
    ? localSettings.tokenUsage.inlineMode
    : "off";
  const hasTodos = (thread.values.todos?.length ?? 0) > 0;

  return (
    <ThreadContext.Provider value={{ thread, isMock }}>
      <ChatBox threadId={threadId}>
        <div className="workbench-conversation relative flex size-full min-h-0 justify-between">
          <header
            className={cn(
              "workbench-conversation-header absolute top-0 right-0 left-0 z-30 flex h-12 shrink-0 items-center px-4",
              isWelcomeMode
                ? "bg-background/0 backdrop-blur-none"
                : "bg-background/80 shadow-xs backdrop-blur",
            )}
          >
            <div className="type-body flex w-full items-center font-medium">
              <ThreadTitle threadId={threadId} thread={thread} />
            </div>
            <div className="flex items-center gap-2">
              <TokenUsageIndicator
                threadId={isNewThread ? undefined : threadId}
                backendUsage={backendTokenUsage}
                enabled={tokenUsageEnabled}
                messages={thread.messages}
                pendingMessages={pendingUsageMessages}
                preferences={localSettings.tokenUsage}
                onPreferencesChange={(preferences) =>
                  setLocalSettings("tokenUsage", preferences)
                }
              />
              <ExportTrigger threadId={threadId} />
              <ArtifactTrigger />
            </div>
          </header>
          <main
            className={cn(
              "workbench-conversation-main flex min-h-0 max-w-full grow flex-col",
              isWelcomeMode && "justify-center",
            )}
          >
            {!isWelcomeMode && (
              <div className="flex min-h-0 flex-1 justify-center">
                <MessageList
                  className="size-full pt-10"
                  threadId={threadId}
                  thread={thread}
                  paddingBottom={MESSAGE_LIST_DEFAULT_PADDING_BOTTOM}
                  hasMoreHistory={hasMoreHistory}
                  loadMoreHistory={loadMoreHistory}
                  isHistoryLoading={isHistoryLoading}
                  tokenUsageInlineMode={tokenUsageInlineMode}
                />
              </div>
            )}
            <div
              className={cn(
                "relative z-30 flex shrink-0 justify-center px-4",
                isWelcomeMode ? "pb-0" : "pb-4",
              )}
            >
              <div className="relative w-full max-w-(--container-width-md)">
                {isWelcomeMode && (
                  <div
                    className="workbench-home flex flex-col items-center"
                    data-testid="workbench-home"
                  >
                    <Welcome mode={settings.context.mode} />
                    <div
                      className="workbench-quick-entry-module"
                      data-testid="workbench-quick-entry-module"
                    >
                      <p className="workbench-module-guide workbench-scenario-guide">
                        <span className="workbench-guide-question">
                          方向不明？
                        </span>
                        <span className="workbench-guide-answer">
                          iDeer帮你找对帮手
                        </span>
                      </p>
                      <ScenarioTabs
                        selected={activeScenario}
                        onSelect={handleSelectScenario}
                      />
                      <div className="workbench-scenario-cascade">
                        <ScenarioCascadeBar
                          selectedScenario={activeScenario}
                          selectedPill={selectedPill}
                          selectedChip={selectedChip}
                          onTogglePill={togglePill}
                          onToggleChip={toggleChip}
                        />
                      </div>
                    </div>
                  </div>
                )}
                {hasTodos && (
                  <div className="relative z-0">
                    <TodoList
                      className="bg-background/5"
                      todos={thread.values.todos ?? []}
                      hidden={false}
                    />
                  </div>
                )}
                {mountedRef.current ? (
                  <>
                    {isWelcomeMode && (
                      <p className="workbench-module-guide workbench-input-guide">
                        <span className="workbench-guide-question">
                          目标明确？
                        </span>
                        <span className="workbench-guide-answer">
                          iDeer帮你落地实现
                        </span>
                      </p>
                    )}
                    <InputBox
                      className="workbench-input-surface bg-background/5 w-full"
                      isWelcomeMode={isWelcomeMode}
                      threadId={threadId}
                      autoFocus={isWelcomeMode}
                      status={
                        thread.error
                          ? "error"
                          : thread.isLoading
                            ? "streaming"
                            : "ready"
                      }
                      context={selectionContext}
                      allowedSkillNames={allowedSkillNames}
                      skillInvocationEnabled={!selectedPill}
                      pendingTemplate={pendingTemplate}
                      clearInjectedTemplateKey={templateResetKey}
                      onPendingTemplateConsumed={() => setPendingTemplate(null)}
                      selectedTags={selectedTags}
                      onRemoveTag={handleRemoveTag}
                      disabled={
                        isMock ||
                        env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true" ||
                        isUploading
                      }
                      onContextChange={(context) =>
                        setSettings("context", context)
                      }
                      onSubmit={handleSubmit}
                      onStop={handleStop}
                    />
                    {isWelcomeMode && (
                      <RecentTaskCards threads={recentThreads} />
                    )}
                  </>
                ) : (
                  <div
                    aria-hidden="true"
                    className="bg-background/5 h-32 w-full rounded-2xl"
                  />
                )}
                {env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true" && (
                  <div className="text-muted-foreground/67 type-body w-full translate-y-12 text-center">
                    {t.common.notAvailableInDemoMode}
                  </div>
                )}
              </div>
            </div>
          </main>
        </div>
      </ChatBox>
    </ThreadContext.Provider>
  );
}
