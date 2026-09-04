/**
 * ThreadHistory deep module — single seam for history loading.
 *
 * One small **interface** `useThreadHistory(threadId)` hides:
 * - per-run paginated fetch with `before_seq`,
 * - `AbortController` per request + cleanup on thread switch/unmount,
 * - bounded concurrency via `do/while pendingLoadRef`,
 * - pure `mergeMessages`/`dedupe` suffix logic.
 *
 * Callers learn one hook; all ref-orchestration and abort **locality**
 * live here. Deleting the module would scatter 7 refs and bare `fetch`
 * back to each caller.
 */
import type { Message, Run } from "@langchain/langgraph-sdk";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { getAPIClient } from "../api";
import { fetch } from "../api/fetcher";
import { getBackendBaseURL } from "../config";

import type { RunMessage } from "./types";

type RecoverableRun = Run & {
  message_count?: number;
  first_user_message?: string | null;
  last_assistant_message?: string | null;
};

// Local runs hook to avoid circular import with hooks.ts (history is the owner)
function useThreadRuns(threadId?: string) {
  const apiClient = getAPIClient();
  return useQuery<RecoverableRun[]>({
    queryKey: ["thread", threadId],
    queryFn: async () => {
      if (!threadId) return [];
      return apiClient.runs.list(threadId);
    },
    refetchOnWindowFocus: false,
  });
}

function isNonEmptyString(value: string | undefined): value is string {
  return typeof value === "string" && value.length > 0;
}

export function messageIdentity(message: Message): string | undefined {
  if (
    "tool_call_id" in message &&
    typeof message.tool_call_id === "string" &&
    message.tool_call_id.length > 0
  ) {
    return `tool:${message.tool_call_id}`;
  }
  if (typeof message.id === "string" && message.id.length > 0) {
    return `message:${message.id}`;
  }
  return undefined;
}

export function dedupeMessagesByIdentity(messages: Message[]): Message[] {
  const lastIndexByIdentity = new Map<string, number>();
  messages.forEach((message, index) => {
    const identity = messageIdentity(message);
    if (identity) lastIndexByIdentity.set(identity, index);
  });
  return messages.filter((message, index) => {
    const identity = messageIdentity(message);
    return !identity || lastIndexByIdentity.get(identity) === index;
  });
}

function findLatestUnloadedRunIndex(
  runs: Run[],
  loadedRunIds: ReadonlySet<string>,
): number {
  for (let i = runs.length - 1; i >= 0; i--) {
    const run = runs[i];
    if (run && !loadedRunIds.has(run.run_id)) return i;
  }
  return -1;
}

export function mergeMessages(
  historyMessages: Message[],
  threadMessages: Message[],
  optimisticMessages: Message[],
): Message[] {
  const threadMessageIds = new Set(
    threadMessages.map(messageIdentity).filter(isNonEmptyString),
  );
  let cutoff = historyMessages.length;
  for (let i = historyMessages.length - 1; i >= 0; i--) {
    const msg = historyMessages[i];
    if (!msg) continue;
    const identity = messageIdentity(msg);
    if (identity && threadMessageIds.has(identity)) cutoff = i;
    else break;
  }
  return dedupeMessagesByIdentity([
    ...historyMessages.slice(0, cutoff),
    ...threadMessages,
    ...optimisticMessages,
  ]);
}

export function getVisibleOptimisticMessages(
  optimisticMessages: Message[],
  previousHumanMessageCount: number,
  currentHumanMessageCount: number,
): Message[] {
  if (
    optimisticMessages.some((m) => m.type === "human") &&
    currentHumanMessageCount > previousHumanMessageCount
  )
    return [];
  return optimisticMessages;
}

export function useThreadHistory(threadId: string) {
  const runs = useThreadRuns(threadId);
  const threadIdRef = useRef(threadId);
  const runsRef = useRef(runs.data ?? []);
  const indexRef = useRef(-1);
  const loadingRef = useRef(false);
  const pendingLoadRef = useRef(false);
  const loadingRunIdRef = useRef<string | null>(null);
  const loadedRunIdsRef = useRef<Set<string>>(new Set());
  const abortRef = useRef<AbortController | null>(null);
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);

  const loadMessages = useCallback(async () => {
    if (loadingRef.current) {
      const pendingRunIndex = findLatestUnloadedRunIndex(
        runsRef.current,
        loadedRunIdsRef.current,
      );
      const pendingRun = runsRef.current[pendingRunIndex];
      if (pendingRun && pendingRun.run_id !== loadingRunIdRef.current)
        pendingLoadRef.current = true;
      return;
    }
    if (runsRef.current.length === 0) return;

    loadingRef.current = true;
    setLoading(true);
    // New abort scope for this batch
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      do {
        pendingLoadRef.current = false;
        const nextRunIndex = findLatestUnloadedRunIndex(
          runsRef.current,
          loadedRunIdsRef.current,
        );
        indexRef.current = nextRunIndex;
        const run = runsRef.current[nextRunIndex];
        if (!run) {
          indexRef.current = -1;
          return;
        }
        const requestThreadId = threadIdRef.current;
        loadingRunIdRef.current = run.run_id;
        const runMessages: RunMessage[] = [];
        let beforeSeq: number | undefined;
        while (true) {
          if (
            controller.signal.aborted ||
            threadIdRef.current !== requestThreadId
          )
            return;
          const query =
            beforeSeq === undefined ? "" : `?before_seq=${beforeSeq}`;
          let result: {
            data: RunMessage[];
            has_more?: boolean;
            hasMore?: boolean;
          };
          try {
            const res = await fetch(
              `${getBackendBaseURL()}/api/threads/${encodeURIComponent(requestThreadId)}/runs/${encodeURIComponent(run.run_id)}/messages${query}`,
              {
                method: "GET",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                signal: controller.signal,
              } as RequestInit & { signal: AbortSignal },
            );
            // HTTP-level error — treat as empty page to avoid tight loop
            if (res.ok === false) {
              console.error(
                `history fetch failed ${res.status} for run ${run.run_id}`,
              );
              break;
            }
            result = (await res.json()) as typeof result;
          } catch (err) {
            if ((err as Error)?.name === "AbortError") return;
            console.error(err);
            break;
          }
          if (
            threadIdRef.current !== requestThreadId ||
            controller.signal.aborted
          )
            return;
          runMessages.unshift(...result.data);
          if (
            !(result.has_more ?? result.hasMore) ||
            result.data.length === 0 ||
            typeof result.data[0]?.seq !== "number"
          )
            break;
          beforeSeq = result.data[0].seq;
        }
        const _messages = runMessages
          .filter((m) => !m.metadata.caller?.startsWith("middleware:"))
          .map((m) => m.content);
        if (
          _messages.length === 0 &&
          run.message_count &&
          run.message_count > 0
        ) {
          const summary = [run.first_user_message, run.last_assistant_message]
            .filter((value): value is string => Boolean(value))
            .join(" → ");
          toast.warning(
            summary
              ? `This older conversation cannot be fully restored. Available summary: ${summary}`
              : "This older conversation cannot be fully restored because its messages were not persisted.",
          );
        }
        if (
          threadIdRef.current !== requestThreadId ||
          controller.signal.aborted
        )
          return;
        setMessages((prev) =>
          dedupeMessagesByIdentity([..._messages, ...prev]),
        );
        loadedRunIdsRef.current.add(run.run_id);
        indexRef.current = findLatestUnloadedRunIndex(
          runsRef.current,
          loadedRunIdsRef.current,
        );
      } while (pendingLoadRef.current);
    } catch (err) {
      if ((err as Error)?.name !== "AbortError") console.error(err);
    } finally {
      loadingRef.current = false;
      loadingRunIdRef.current = null;
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const threadChanged = threadIdRef.current !== threadId;
    threadIdRef.current = threadId;
    if (threadChanged) {
      abortRef.current?.abort();
      runsRef.current = [];
      indexRef.current = -1;
      pendingLoadRef.current = false;
      loadingRunIdRef.current = null;
      loadedRunIdsRef.current = new Set();
      loadingRef.current = false;
      setLoading(false);
      setMessages([]);
    }
    if (runs.data && runs.data.length > 0) {
      runsRef.current = runs.data ?? [];
      indexRef.current = findLatestUnloadedRunIndex(
        runs.data,
        loadedRunIdsRef.current,
      );
    }
    loadMessages().catch(() => toast.error("Failed to load thread history."));
    return () => {
      // Do not abort here aggressively — let in-flight finish or be cancelled by next thread change
    };
  }, [threadId, runs.data, loadMessages]);

  // Abort on unmount
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const appendMessages = useCallback((_messages: Message[]) => {
    setMessages((prev) => dedupeMessagesByIdentity([...prev, ..._messages]));
  }, []);

  const hasMore = indexRef.current >= 0 || !runs.data;
  return {
    runs: runs.data,
    messages,
    loading,
    appendMessages,
    hasMore,
    loadMore: loadMessages,
  } as const;
}
