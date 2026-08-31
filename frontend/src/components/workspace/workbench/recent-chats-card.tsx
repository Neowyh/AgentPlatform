"use client";

import Link from "next/link";

import { useI18n } from "@/core/i18n/hooks";
import { useThreads } from "@/core/threads/hooks";
import { pathOfThread, titleOfThread } from "@/core/threads/utils";

export function RecentChatsCard({ max = 5 }: { max?: number }) {
  const { t } = useI18n();
  const { data: threads = [] } = useThreads();

  if (threads.length === 0) {
    return null;
  }

  return (
    <section className="space-y-2">
      <h2 className="text-muted-foreground type-section-title font-medium">
        {t.workbench.recentChatsTitle}
      </h2>
      <div className="flex flex-col gap-1" data-testid="workbench-recent-chats">
        {threads.slice(0, max).map((thread) => (
          <Link
            key={thread.thread_id}
            href={pathOfThread(thread)}
            className="hover:bg-background/10 text-foreground/90 type-body truncate rounded-lg border px-3 py-2 transition-colors"
          >
            {titleOfThread(thread)}
          </Link>
        ))}
      </div>
    </section>
  );
}
