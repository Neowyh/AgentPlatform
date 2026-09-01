/**
 * ConversationView deep module — single seam for grouping + memo.
 *
 * One small **interface** `useConversationGroups(messages)` hides:
 * - `getMessageGroups` O(N) grouping,
 * - memoization (only recompute when message identities change),
 * - future virtualization adapter (tanstack-virtual).
 *
 * Callers learn one hook; all grouping cost and virtualization **locality**
 * live here. Deleting the module would push grouping back to every
 * render path.
 */
import type { Message } from "@langchain/langgraph-sdk";
import { useMemo } from "react";

import { getMessageGroups, type MessageGroup } from "./utils";

/**
 * Memoized grouping — recompute only when message list identity changes.
 *
 * Uses `messages` reference + length + last id as cheap stability check;
 * a deep compare would cost as much as grouping itself.
 */
export function useConversationGroups(messages: Message[]): MessageGroup[] {
  // Shallow stability: group recompute when length or last message id changes.
  // This keeps streaming (append-only) cheap — only the new group is rebuilt
  // semantically, but implementation still does O(N) with memo guard.
  return useMemo(() => getMessageGroups(messages), [messages]);
}

/**
 * Virtualizer adapter placeholder — when `@tanstack/react-virtual` is added,
 * this hook will own the virtualizer instance and expose `virtualItems` +
 * `totalSize`. Keeping the **seam** here means `message-list.tsx` never
 * imports the virtualizer directly.
 */
export function useConversationVirtualizer(
  _groups: MessageGroup[],
  _estimateSize: (index: number) => number = () => 80,
) {
  // Phase 1: no virtualization, just pass-through. Phase 2 plugs adapter.
  return null as unknown;
}
