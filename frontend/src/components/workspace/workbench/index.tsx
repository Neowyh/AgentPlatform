"use client";

import { RecentChatsCard } from "./recent-chats-card";

export { RecentChatsCard } from "./recent-chats-card";

export function WorkbenchHome() {
  return (
    <div className="space-y-5" data-testid="workbench-home">
      <RecentChatsCard />
    </div>
  );
}
