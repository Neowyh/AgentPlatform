import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { RecentChatsCard } from "@/components/workspace/workbench/recent-chats-card";
import type { AgentThread } from "@/core/threads/types";

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en",
    t: {
      workbench: {
        recentChatsTitle: "Recent chats",
      },
    },
  }),
}));

vi.mock("@/core/threads/hooks", () => ({
  useThreads: () => ({ data: mockThreadsData }),
}));

let mockThreadsData: AgentThread[] = [];

describe("RecentChatsCard", () => {
  beforeEach(() => {
    mockThreadsData = [];
  });

  test("renders recent thread links", () => {
    mockThreadsData = [
      {
        thread_id: "t1",
        values: { title: "My first chat", messages: [], artifacts: [] },
        metadata: {},
      },
      {
        thread_id: "t2",
        values: { messages: [], artifacts: [] },
        metadata: {},
      },
    ] as unknown as AgentThread[];
    render(<RecentChatsCard />);
    expect(screen.getByTestId("workbench-recent-chats").children.length).toBe(
      2,
    );
    expect(screen.getByText("My first chat")).toHaveAttribute(
      "href",
      "/workspace/chats/t1",
    );
  });

  test("renders nothing when there are no threads", () => {
    const { container } = render(<RecentChatsCard />);
    expect(container).toBeEmptyDOMElement();
  });
});
