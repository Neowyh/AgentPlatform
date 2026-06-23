import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/styles/globals.css", () => ({}));
vi.mock("katex/dist/katex.min.css", () => ({}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en",
    t: {
      pages: { chats: "Chats", appName: "iDeer" },
      chats: { searchChats: "Search chats..." },
      common: { loading: "Loading..." },
    },
  }),
}));

vi.mock("@/core/threads/hooks", () => ({
  useThreads: () => ({
    data: [
      {
        thread_id: "thread-1",
        title: "First Thread",
        updated_at: new Date("2025-01-15").toISOString(),
      },
      {
        thread_id: "thread-2",
        title: "Second Thread",
        updated_at: null,
      },
    ],
  }),
}));

vi.mock("@/core/threads/utils", () => ({
  pathOfThread: (thread: any) =>
    `/workspace/chats/${thread.thread_id ?? thread}`,
  titleOfThread: (thread: any) => thread.title ?? "Untitled",
}));

vi.mock("@/core/utils/datetime", () => ({
  formatTimeAgo: () => "2 days ago",
}));

vi.mock("@/components/ui/input", () => ({
  Input: (props: any) => (
    <input
      data-testid="chat-search-input"
      placeholder={props.placeholder}
      value={props.value}
      onChange={props.onChange}
    />
  ),
}));

vi.mock("@/components/ui/scroll-area", () => ({
  ScrollArea: ({ children }: any) => (
    <div data-testid="scroll-area">{children}</div>
  ),
}));

vi.mock("@/components/workspace/workspace-container", () => ({
  WorkspaceContainer: ({ children }: any) => (
    <div data-testid="workspace-container">{children}</div>
  ),
  WorkspaceHeader: () => <div data-testid="workspace-header" />,
  WorkspaceBody: ({ children }: any) => (
    <div data-testid="workspace-body">{children}</div>
  ),
}));

vi.mock("next/link", () => ({
  default: ({ children, href }: any) => (
    <a href={href} data-testid="thread-link">
      {children}
    </a>
  ),
}));

import ChatsPage from "@/app/workspace/chats/page";

afterEach(() => {
  vi.clearAllMocks();
});

describe("ChatsPage", () => {
  test("renders workspace container", () => {
    render(<ChatsPage />);
    expect(screen.getByTestId("workspace-container")).toBeInTheDocument();
  });

  test("renders search input", () => {
    render(<ChatsPage />);
    expect(screen.getByTestId("chat-search-input")).toBeInTheDocument();
  });

  test("renders thread list", () => {
    render(<ChatsPage />);
    const links = screen.getAllByTestId("thread-link");
    expect(links).toHaveLength(2);
  });

  test("displays thread titles", () => {
    render(<ChatsPage />);
    expect(screen.getByText("First Thread")).toBeInTheDocument();
    expect(screen.getByText("Second Thread")).toBeInTheDocument();
  });

  test("displays formatted time for threads with updated_at", () => {
    render(<ChatsPage />);
    expect(screen.getByText("2 days ago")).toBeInTheDocument();
  });

  test("renders workspace header and body", () => {
    render(<ChatsPage />);
    expect(screen.getByTestId("workspace-header")).toBeInTheDocument();
    expect(screen.getByTestId("workspace-body")).toBeInTheDocument();
  });

  test("renders scroll area", () => {
    render(<ChatsPage />);
    expect(screen.getByTestId("scroll-area")).toBeInTheDocument();
  });
});
