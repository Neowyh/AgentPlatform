"use client";

import { env } from "@/env";

import { AgentShowcase } from "./agent-showcase";
import { RecentChatsCard } from "./recent-chats-card";
import { SceneSuggestionCards } from "./scene-suggestion-cards";

export {
  agentChatUrlWithPrompt,
  SceneSuggestionCards,
} from "./scene-suggestion-cards";
export { AgentShowcase } from "./agent-showcase";
export { RecentChatsCard } from "./recent-chats-card";

export function WorkbenchHome({
  hideSuggestions,
}: {
  hideSuggestions?: boolean;
}) {
  // The suggestion cards and agent showcase depend on the agents API, which
  // is unavailable in the static demo build; only recent chats work there.
  const showAgentSections =
    !hideSuggestions && env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY !== "true";
  return (
    <div className="space-y-5" data-testid="workbench-home">
      {showAgentSections && (
        <>
          <SceneSuggestionCards />
          <AgentShowcase />
        </>
      )}
      <RecentChatsCard />
    </div>
  );
}
