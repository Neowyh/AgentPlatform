import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
  usePathname: () => "/workspace/chats/new",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

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
      inputBox: {
        createSkillPrompt: "Create a skill",
      },
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
  useThreads: () => ({ data: [] }),
  useThreadMetadata: () => ({ data: null }),
  useBranchThread: () => ({ mutate: vi.fn() }),
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
  useThread: () => ({ thread: null }),
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
      inputBox: {
        createSkillPrompt: "Create a skill",
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

vi.mock("@/core/agents/hooks", () => ({
  useAgents: () => ({ agents: [] }),
  useAgent: () => ({ agent: null }),
}));

vi.mock("@/core/skills/hooks", () => ({
  useSkills: () => ({ skills: [], isLoading: false, error: null }),
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
  selectContextUsage: () => null,
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
  usePromptInputController: () => ({
    textInput: { setInput: vi.fn() },
  }),
}));

import ChatPage from "@/app/workspace/chats/[thread_id]/page";

// jsdom has no matchMedia; the workspace sidebar's useIsMobile hook needs it.
vi.stubGlobal("matchMedia", (query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  addListener: vi.fn(),
  removeListener: vi.fn(),
  dispatchEvent: vi.fn(),
}));

// ChatPage reads feature flags through react-query; provide a client.
function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("ChatPage", () => {
  test("renders chat box", () => {
    renderWithProviders(<ChatPage />);
    expect(screen.getByTestId("chat-box")).toBeInTheDocument();
  });

  test("passes threadId to chat box", () => {
    renderWithProviders(<ChatPage />);
    const chatBox = screen.getByTestId("chat-box");
    expect(chatBox).toHaveAttribute("data-thread-id", "test-thread-id");
  });

  test("renders message list", () => {
    renderWithProviders(<ChatPage />);
    expect(screen.getByTestId("message-list")).toBeInTheDocument();
  });

  test("renders thread title", () => {
    renderWithProviders(<ChatPage />);
    expect(screen.getByTestId("thread-title")).toBeInTheDocument();
  });

  test("renders token usage indicator", () => {
    renderWithProviders(<ChatPage />);
    expect(screen.getByTestId("token-usage-indicator")).toBeInTheDocument();
  });

  test("renders export trigger", () => {
    renderWithProviders(<ChatPage />);
    expect(screen.getByTestId("export-trigger")).toBeInTheDocument();
  });

  test("renders artifact trigger", () => {
    renderWithProviders(<ChatPage />);
    expect(screen.getByTestId("artifact-trigger")).toBeInTheDocument();
  });

  test("renders input placeholder when not yet mounted", () => {
    renderWithProviders(<ChatPage />);
    // mountedRef is false on initial render, so a placeholder div is shown
    // instead of the InputBox component
    const { container } = renderWithProviders(<ChatPage />);
    const placeholder = container.querySelector('[aria-hidden="true"]');
    expect(placeholder).toBeInTheDocument();
  });

  test("wraps content in thread context provider", () => {
    renderWithProviders(<ChatPage />);
    expect(screen.getByTestId("thread-context")).toBeInTheDocument();
  });
});
