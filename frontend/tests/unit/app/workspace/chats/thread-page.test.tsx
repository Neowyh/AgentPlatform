import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/styles/globals.css", () => ({}));
vi.mock("katex/dist/katex.min.css", () => ({}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en",
    t: {
      common: {
        loading: "Loading...",
        notAvailableInDemoMode: "Not available in demo mode",
      },
      chats: { searchChats: "Search chats..." },
      scenarios: {
        daily: "Daily Office",
        creative: "Creative Design",
        professional: "Professional Tasks",
      },
    },
  }),
}));

vi.mock("@/core/threads/hooks", () => ({
  useThreadStream: () => ({
    thread: {
      values: {},
      messages: [],
      isLoading: false,
      error: null,
      stop: vi.fn(),
    },
    pendingUsageMessages: [],
    sendMessage: vi.fn(),
    isUploading: false,
    isHistoryLoading: false,
    hasMoreHistory: false,
    loadMoreHistory: vi.fn(),
  }),
  useThreadTokenUsage: () => ({
    data: null,
  }),
}));

vi.mock("@/components/workspace/chats", () => ({
  ChatBox: ({ children, threadId }: any) => (
    <div data-testid="chat-box" data-thread-id={threadId}>
      {children}
    </div>
  ),
  useSpecificChatMode: () => {},
  useThreadChat: () => ({
    threadId: "test-thread-id",
    setThreadId: vi.fn(),
    isNewThread: false,
    setIsNewThread: vi.fn(),
    isMock: false,
  }),
}));

vi.mock("@/components/workspace/messages", () => ({
  MessageList: () => <div data-testid="message-list" />,
  MESSAGE_LIST_DEFAULT_PADDING_BOTTOM: 96,
}));

vi.mock("@/components/workspace/messages/context", () => ({
  ThreadContext: {
    Provider: ({ children }: any) => (
      <div data-testid="thread-context">{children}</div>
    ),
  },
}));

vi.mock("@/components/workspace/thread-title", () => ({
  ThreadTitle: () => <div data-testid="thread-title" />,
}));

vi.mock("@/components/workspace/todo-list", () => ({
  TodoList: () => <div data-testid="todo-list" />,
}));

vi.mock("@/components/workspace/token-usage-indicator", () => ({
  TokenUsageIndicator: () => <div data-testid="token-usage-indicator" />,
}));

vi.mock("@/components/workspace/welcome", () => ({
  Welcome: () => <div data-testid="welcome" />,
}));

vi.mock("@/components/workspace/input-box", () => ({
  InputBox: () => <div data-testid="input-box" />,
}));

vi.mock("@/components/workspace/export-trigger", () => ({
  ExportTrigger: () => <div data-testid="export-trigger" />,
}));

vi.mock("@/components/workspace/artifacts", () => ({
  ArtifactTrigger: () => <div data-testid="artifact-trigger" />,
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en",
    t: {
      common: {
        loading: "Loading...",
        notAvailableInDemoMode: "Not available in demo mode",
      },
      scenarios: {
        daily: "Daily Office",
        creative: "Creative Design",
        professional: "Professional Tasks",
      },
    },
  }),
}));

vi.mock("@/core/models/hooks", () => ({
  useModels: () => ({
    models: [],
    tokenUsageEnabled: false,
  }),
}));

vi.mock("@/core/notification/hooks", () => ({
  useNotification: () => ({
    showNotification: vi.fn(),
  }),
}));

vi.mock("@/core/settings", () => ({
  useLocalSettings: () => [{ tokenUsage: { inlineMode: "off" } }, vi.fn()],
  useThreadSettings: () => [{ context: { mode: "chat" } }, vi.fn()],
}));

vi.mock("@/core/threads/token-usage", () => ({
  threadTokenUsageToTokenUsage: () => null,
}));

vi.mock("@/core/threads/utils", () => ({
  textOfMessage: () => "",
}));

vi.mock("@/env", () => ({
  env: {
    NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false",
  },
}));

vi.mock("@/lib/utils", () => ({
  cn: (...args: any[]) => args.filter(Boolean).join(" "),
}));

vi.mock("@/components/ai-elements/prompt-input", () => ({
  PromptInputMessage: {},
}));

import ChatPage from "@/app/workspace/chats/[thread_id]/page";

afterEach(() => {
  vi.clearAllMocks();
});

describe("ChatPage", () => {
  test("renders chat box", () => {
    render(<ChatPage />);
    expect(screen.getByTestId("chat-box")).toBeInTheDocument();
  });

  test("passes threadId to chat box", () => {
    render(<ChatPage />);
    const chatBox = screen.getByTestId("chat-box");
    expect(chatBox).toHaveAttribute("data-thread-id", "test-thread-id");
  });

  test("renders message list", () => {
    render(<ChatPage />);
    expect(screen.getByTestId("message-list")).toBeInTheDocument();
  });

  test("renders thread title", () => {
    render(<ChatPage />);
    expect(screen.getByTestId("thread-title")).toBeInTheDocument();
  });

  test("renders token usage indicator", () => {
    render(<ChatPage />);
    expect(screen.getByTestId("token-usage-indicator")).toBeInTheDocument();
  });

  test("renders export trigger", () => {
    render(<ChatPage />);
    expect(screen.getByTestId("export-trigger")).toBeInTheDocument();
  });

  test("renders artifact trigger", () => {
    render(<ChatPage />);
    expect(screen.getByTestId("artifact-trigger")).toBeInTheDocument();
  });

  test("renders input placeholder when not yet mounted", () => {
    render(<ChatPage />);
    // mountedRef is false on initial render, so a placeholder div is shown
    // instead of the InputBox component
    const { container } = render(<ChatPage />);
    const placeholder = container.querySelector('[aria-hidden="true"]');
    expect(placeholder).toBeInTheDocument();
  });

  test("wraps content in thread context provider", () => {
    render(<ChatPage />);
    expect(screen.getByTestId("thread-context")).toBeInTheDocument();
  });
});
