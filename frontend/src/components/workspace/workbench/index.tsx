"use client";

import { AgentShowcase } from "./agent-showcase";
import { RecentChatsCard } from "./recent-chats-card";
import { SceneSuggestionCards } from "./scene-suggestion-cards";

export {
  agentChatUrlWithPrompt,
  SceneSuggestionCards,
} from "./scene-suggestion-cards";
export { AgentShowcase } from "./agent-showcase";
export { RecentChatsCard } from "./recent-chats-card";

export function WorkbenchHome() {
  return (
    <div className="space-y-5" data-testid="workbench-home">
      <SceneSuggestionCards />
      <AgentShowcase />
      <RecentChatsCard />
    </div>
  );
}
