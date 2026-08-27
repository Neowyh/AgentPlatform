import { render, screen, cleanup, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const {
  mockUseThreadChat,
  mockUseThreadStream,
  mockUseSpecificChatMode,
  mockShowNotification,
  mockLastInputBoxProps,
  mockTextOfMessage,
  mockEnvValues,
} = vi.hoisted(() => ({
  mockUseThreadChat: vi.fn().mockReturnValue({
    threadId: "test-thread",
    setThreadId: vi.fn(),
    isNewThread: false,
    setIsNewThread: vi.fn(),
    isMock: false,
  }),
  mockUseThreadStream: vi.fn().mockReturnValue({
    thread: {
      messages: [],
      isLoading: false,
      isThreadLoading: false,
      error: null,
      values: {},
      stop: vi.fn(),
      getMessagesMetadata: vi.fn(),
    },
    pendingUsageMessages: [],
    sendMessage: vi.fn(),
    isUploading: false,
    isHistoryLoading: false,
    hasMoreHistory: false,
    loadMoreHistory: vi.fn(),
  }),
  mockUseSpecificChatMode: vi.fn(),
  mockShowNotification: vi.fn(),
  mockLastInputBoxProps: { current: null as any },
  mockTextOfMessage: vi.fn().mockReturnValue(""),
  mockEnvValues: { NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false" },
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      common: {
        loading: "Loading...",
        notAvailableInDemoMode: "Not available in demo",
      },
      scenarios: {
        daily: "日常办公",
        creative: "创意设计",
        professional: "专业任务",
      },
    },
  }),
}));

vi.mock("@/components/workspace/chats", () => ({
  ChatBox: ({ children }: any) => <div data-testid="chat-box">{children}</div>,
  useSpecificChatMode: () => mockUseSpecificChatMode(),
  useThreadChat: () => mockUseThreadChat(),
}));

vi.mock("@/components/ai-elements/prompt-input", () => ({
  PromptInputProvider: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("@/components/workspace/artifacts", () => ({
  ArtifactTrigger: () => <div data-testid="artifact-trigger" />,
}));

vi.mock("@/components/workspace/export-trigger", () => ({
  ExportTrigger: () => <div data-testid="export-trigger" />,
}));

vi.mock("@/components/workspace/input-box", () => ({
  InputBox: (props: any) => {
    mockLastInputBoxProps.current = props;
    return (
      <div
        data-testid="input-box"
        data-welcome-mode={String(props.isWelcomeMode)}
        data-disabled={String(props.disabled)}
      ></div>
    );
  },
}));

vi.mock("@/components/workspace/messages", () => ({
  MessageList: () => <div data-testid="message-list">Messages</div>,
  MESSAGE_LIST_DEFAULT_PADDING_BOTTOM: 24,
}));

vi.mock("@/components/workspace/messages/context", () => ({
  ThreadContext: { Provider: ({ children }: any) => <div>{children}</div> },
}));

vi.mock("@/components/workspace/thread-title", () => ({
  ThreadTitle: () => <div data-testid="thread-title">Thread Title</div>,
}));

vi.mock("@/components/workspace/todo-list", () => ({
  TodoList: (props: any) => <div data-testid="todo-list" />,
}));

vi.mock("@/components/workspace/token-usage-indicator", () => ({
  TokenUsageIndicator: () => <div data-testid="token-usage" />,
}));

vi.mock("@/components/workspace/welcome", () => ({
  Welcome: (props: any) => <div data-testid="welcome" />,
}));

vi.mock("@/components/workspace/workbench", () => ({
  WorkbenchHome: () => <div data-testid="workbench-home" />,
}));

vi.mock("@/core/models/hooks", () => ({
  useModels: () => ({ tokenUsageEnabled: false }),
}));

vi.mock("@/core/notification/hooks", () => ({
  useNotification: () => ({ showNotification: mockShowNotification }),
}));

vi.mock("@/core/settings", () => ({
  useLocalSettings: () => [{ tokenUsage: { inlineMode: "off" } }, vi.fn()],
  useThreadSettings: () => [{ context: { mode: "flash" } }, vi.fn()],
}));

vi.mock("@/core/threads/hooks", () => ({
  useThreadStream: (...args: any[]) => mockUseThreadStream(...args),
  useThreadTokenUsage: () => ({ data: null }),
}));

vi.mock("@/core/threads/token-usage", () => ({
  threadTokenUsageToTokenUsage: () => ({}),
}));

vi.mock("@/core/threads/utils", () => ({
  textOfMessage: (...args: any[]) => mockTextOfMessage(...args),
}));

vi.mock("@/env", () => ({
  env: mockEnvValues,
}));

vi.mock("@/lib/utils", () => ({
  cn: (...args: any[]) => args.filter(Boolean).join(" "),
}));

import ChatPage from "@/app/workspace/chats/[thread_id]/page";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ChatPage", () => {
  beforeEach(() => {
    mockUseThreadChat.mockReturnValue({
      threadId: "test-thread",
      setThreadId: vi.fn(),
      isNewThread: false,
      setIsNewThread: vi.fn(),
      isMock: false,
    });
    mockUseThreadStream.mockReturnValue({
      thread: {
        messages: [],
        isLoading: false,
        isThreadLoading: false,
        error: null,
        values: {},
        stop: vi.fn(),
        getMessagesMetadata: vi.fn(),
      },
      pendingUsageMessages: [],
      sendMessage: vi.fn(),
      isUploading: false,
      isHistoryLoading: false,
      hasMoreHistory: false,
      loadMoreHistory: vi.fn(),
    });
    mockLastInputBoxProps.current = null;
    mockTextOfMessage.mockReturnValue("");
  });

  test("renders chat box", () => {
    render(<ChatPage />);
    expect(screen.getByTestId("chat-box")).toBeInTheDocument();
  });

  test("renders message list", () => {
    render(<ChatPage />);
    expect(screen.getByTestId("message-list")).toBeInTheDocument();
  });

  test("renders thread title", () => {
    render(<ChatPage />);
    expect(screen.getByTestId("thread-title")).toBeInTheDocument();
  });

  test("renders input box placeholder", () => {
    render(<ChatPage />);
    const placeholder = document.querySelector('[aria-hidden="true"]');
    expect(placeholder).toBeInTheDocument();
  });

  test("renders token usage indicator", () => {
    render(<ChatPage />);
    expect(screen.getByTestId("token-usage")).toBeInTheDocument();
  });

  test("renders export trigger", () => {
    render(<ChatPage />);
    expect(screen.getByTestId("export-trigger")).toBeInTheDocument();
  });

  test("renders artifact trigger", () => {
    render(<ChatPage />);
    expect(screen.getByTestId("artifact-trigger")).toBeInTheDocument();
  });

  test("does not render todo list when no todos", () => {
    render(<ChatPage />);
    expect(screen.queryByTestId("todo-list")).not.toBeInTheDocument();
  });

  test("renders todo list when todos exist", () => {
    mockUseThreadStream.mockReturnValue({
      thread: {
        messages: [],
        isLoading: false,
        error: null,
        values: { todos: [{ id: "1", text: "Task 1", done: false }] },
        stop: vi.fn(),
      },
      sendMessage: vi.fn(),
      isUploading: false,
      isHistoryLoading: false,
      hasMoreHistory: false,
      loadMoreHistory: vi.fn(),
    });

    render(<ChatPage />);
    expect(screen.getByTestId("todo-list")).toBeInTheDocument();
  });

  test("renders with mock thread", () => {
    mockUseThreadChat.mockReturnValue({
      threadId: "mock-thread",
      setThreadId: vi.fn(),
      isNewThread: false,
      setIsNewThread: vi.fn(),
      isMock: true,
    });

    render(<ChatPage />);
    expect(screen.getByTestId("chat-box")).toBeInTheDocument();
    expect(screen.getByTestId("message-list")).toBeInTheDocument();
  });

  test("renders with thread error state", () => {
    mockUseThreadStream.mockReturnValue({
      thread: {
        messages: [],
        isLoading: false,
        error: "Connection failed",
        values: {},
        stop: vi.fn(),
      },
      sendMessage: vi.fn(),
      isUploading: false,
      isHistoryLoading: false,
      hasMoreHistory: false,
      loadMoreHistory: vi.fn(),
    });

    render(<ChatPage />);
    expect(screen.getByTestId("chat-box")).toBeInTheDocument();
  });

  test("renders with loading thread state", () => {
    mockUseThreadStream.mockReturnValue({
      thread: {
        messages: [],
        isLoading: true,
        error: null,
        values: {},
        stop: vi.fn(),
      },
      sendMessage: vi.fn(),
      isUploading: false,
      isHistoryLoading: false,
      hasMoreHistory: false,
      loadMoreHistory: vi.fn(),
    });

    render(<ChatPage />);
    expect(screen.getByTestId("chat-box")).toBeInTheDocument();
  });

  test("renders InputBox after re-render when mounted", () => {
    const { rerender } = render(<ChatPage />);
    expect(screen.queryByTestId("input-box")).not.toBeInTheDocument();
    expect(
      document.querySelector('div[aria-hidden="true"]'),
    ).toBeInTheDocument();
    rerender(<ChatPage />);
    expect(screen.getByTestId("input-box")).toBeInTheDocument();
    expect(
      document.querySelector('div[aria-hidden="true"]'),
    ).not.toBeInTheDocument();
  });

  test("calls useSpecificChatMode on render", () => {
    render(<ChatPage />);
    expect(mockUseSpecificChatMode).toHaveBeenCalled();
  });

  test("onSend callback exits welcome mode", () => {
    mockUseThreadChat.mockReturnValue({
      threadId: "test-thread",
      setThreadId: vi.fn(),
      isNewThread: true,
      setIsNewThread: vi.fn(),
      isMock: false,
    });

    let capturedOnSend: (() => void) | undefined;
    mockUseThreadStream.mockImplementation((args: any) => {
      capturedOnSend = args.onSend;
      return {
        thread: {
          messages: [],
          isLoading: false,
          isThreadLoading: false,
          error: null,
          values: {},
          stop: vi.fn(),
          getMessagesMetadata: vi.fn(),
        },
        pendingUsageMessages: [],
        sendMessage: vi.fn(),
        isUploading: false,
        isHistoryLoading: false,
        hasMoreHistory: false,
        loadMoreHistory: vi.fn(),
      };
    });

    const { rerender } = render(<ChatPage />);
    rerender(<ChatPage />);
    expect(mockLastInputBoxProps.current.isWelcomeMode).toBe(true);

    act(() => {
      capturedOnSend!();
    });
    expect(mockLastInputBoxProps.current.isWelcomeMode).toBe(false);
  });

  test("onStart callback sets threadId and updates URL", () => {
    const setThreadIdMock = vi.fn();
    const setIsNewThreadMock = vi.fn();
    mockUseThreadChat.mockReturnValue({
      threadId: "test-thread",
      setThreadId: setThreadIdMock,
      isNewThread: true,
      setIsNewThread: setIsNewThreadMock,
      isMock: false,
    });

    let capturedOnStart: ((id: string) => void) | undefined;
    mockUseThreadStream.mockImplementation((args: any) => {
      capturedOnStart = args.onStart;
      return {
        thread: {
          messages: [],
          isLoading: false,
          isThreadLoading: false,
          error: null,
          values: {},
          stop: vi.fn(),
          getMessagesMetadata: vi.fn(),
        },
        pendingUsageMessages: [],
        sendMessage: vi.fn(),
        isUploading: false,
        isHistoryLoading: false,
        hasMoreHistory: false,
        loadMoreHistory: vi.fn(),
      };
    });

    const replaceStateSpy = vi.spyOn(history, "replaceState");

    render(<ChatPage />);
    act(() => {
      capturedOnStart!("new-thread-id-123");
    });

    expect(setThreadIdMock).toHaveBeenCalledWith("new-thread-id-123");
    expect(setIsNewThreadMock).toHaveBeenCalledWith(false);
    expect(replaceStateSpy).toHaveBeenCalledWith(
      null,
      "",
      "/workspace/chats/new-thread-id-123",
    );

    replaceStateSpy.mockRestore();
  });

  test("onFinish shows notification when document is hidden", () => {
    let capturedOnFinish: ((state: any) => void) | undefined;
    mockUseThreadStream.mockImplementation((args: any) => {
      capturedOnFinish = args.onFinish;
      return {
        thread: {
          messages: [],
          isLoading: false,
          isThreadLoading: false,
          error: null,
          values: {},
          stop: vi.fn(),
          getMessagesMetadata: vi.fn(),
        },
        pendingUsageMessages: [],
        sendMessage: vi.fn(),
        isUploading: false,
        isHistoryLoading: false,
        hasMoreHistory: false,
        loadMoreHistory: vi.fn(),
      };
    });

    const hiddenSpy = vi.spyOn(document, "hidden", "get").mockReturnValue(true);
    const focusSpy = vi.spyOn(document, "hasFocus").mockReturnValue(false);

    render(<ChatPage />);
    capturedOnFinish!({
      messages: [{ content: "Hello world" }],
      title: "Test Conversation",
    });

    expect(mockShowNotification).toHaveBeenCalledWith("Test Conversation", {
      body: "Conversation finished",
    });

    hiddenSpy.mockRestore();
    focusSpy.mockRestore();
  });

  test("onFinish does not show notification when document is visible and focused", () => {
    let capturedOnFinish: ((state: any) => void) | undefined;
    mockUseThreadStream.mockImplementation((args: any) => {
      capturedOnFinish = args.onFinish;
      return {
        thread: {
          messages: [],
          isLoading: false,
          isThreadLoading: false,
          error: null,
          values: {},
          stop: vi.fn(),
          getMessagesMetadata: vi.fn(),
        },
        pendingUsageMessages: [],
        sendMessage: vi.fn(),
        isUploading: false,
        isHistoryLoading: false,
        hasMoreHistory: false,
        loadMoreHistory: vi.fn(),
      };
    });

    vi.spyOn(document, "hidden", "get").mockReturnValue(false);
    vi.spyOn(document, "hasFocus").mockReturnValue(true);

    render(<ChatPage />);
    capturedOnFinish!({
      messages: [{ content: "Hello" }],
      title: "Test",
    });

    expect(mockShowNotification).not.toHaveBeenCalled();
  });

  test("onFinish truncates long message text in notification body", () => {
    mockTextOfMessage.mockReturnValue("A".repeat(250));

    let capturedOnFinish: ((state: any) => void) | undefined;
    mockUseThreadStream.mockImplementation((args: any) => {
      capturedOnFinish = args.onFinish;
      return {
        thread: {
          messages: [],
          isLoading: false,
          isThreadLoading: false,
          error: null,
          values: {},
          stop: vi.fn(),
          getMessagesMetadata: vi.fn(),
        },
        pendingUsageMessages: [],
        sendMessage: vi.fn(),
        isUploading: false,
        isHistoryLoading: false,
        hasMoreHistory: false,
        loadMoreHistory: vi.fn(),
      };
    });

    vi.spyOn(document, "hidden", "get").mockReturnValue(true);

    render(<ChatPage />);
    capturedOnFinish!({
      messages: [{ content: "Hello" }],
      title: "Test",
    });

    expect(mockShowNotification).toHaveBeenCalledWith("Test", {
      body: "A".repeat(200) + "...",
    });
  });

  test("onFinish uses short message text as body when under 200 chars", () => {
    mockTextOfMessage.mockReturnValue("Short message");

    let capturedOnFinish: ((state: any) => void) | undefined;
    mockUseThreadStream.mockImplementation((args: any) => {
      capturedOnFinish = args.onFinish;
      return {
        thread: {
          messages: [],
          isLoading: false,
          isThreadLoading: false,
          error: null,
          values: {},
          stop: vi.fn(),
          getMessagesMetadata: vi.fn(),
        },
        pendingUsageMessages: [],
        sendMessage: vi.fn(),
        isUploading: false,
        isHistoryLoading: false,
        hasMoreHistory: false,
        loadMoreHistory: vi.fn(),
      };
    });

    vi.spyOn(document, "hidden", "get").mockReturnValue(true);

    render(<ChatPage />);
    capturedOnFinish!({
      messages: [{ content: "Hello" }],
      title: "Test",
    });

    expect(mockShowNotification).toHaveBeenCalledWith("Test", {
      body: "Short message",
    });
  });

  test("onFinish handles empty messages gracefully", () => {
    let capturedOnFinish: ((state: any) => void) | undefined;
    mockUseThreadStream.mockImplementation((args: any) => {
      capturedOnFinish = args.onFinish;
      return {
        thread: {
          messages: [],
          isLoading: false,
          isThreadLoading: false,
          error: null,
          values: {},
          stop: vi.fn(),
          getMessagesMetadata: vi.fn(),
        },
        pendingUsageMessages: [],
        sendMessage: vi.fn(),
        isUploading: false,
        isHistoryLoading: false,
        hasMoreHistory: false,
        loadMoreHistory: vi.fn(),
      };
    });

    vi.spyOn(document, "hidden", "get").mockReturnValue(true);

    render(<ChatPage />);
    capturedOnFinish!({
      messages: [],
      title: "Empty Chat",
    });

    expect(mockShowNotification).toHaveBeenCalledWith("Empty Chat", {
      body: "Conversation finished",
    });
  });

  test("handleSubmit with files returns send promise", () => {
    const sendMessageMock = vi.fn().mockResolvedValue(undefined);
    mockUseThreadStream.mockReturnValue({
      thread: {
        messages: [],
        isLoading: false,
        isThreadLoading: false,
        error: null,
        values: {},
        stop: vi.fn(),
        getMessagesMetadata: vi.fn(),
      },
      pendingUsageMessages: [],
      sendMessage: sendMessageMock,
      isUploading: false,
      isHistoryLoading: false,
      hasMoreHistory: false,
      loadMoreHistory: vi.fn(),
    });

    const { rerender } = render(<ChatPage />);
    rerender(<ChatPage />);

    const file = new File(["content"], "test.txt", { type: "text/plain" });
    const result = mockLastInputBoxProps.current.onSubmit({
      text: "hello",
      files: [file],
    });
    expect(result).toBeInstanceOf(Promise);
    expect(sendMessageMock).toHaveBeenCalledWith("test-thread", {
      text: "hello",
      files: [file],
    });
  });

  test("handleSubmit without files returns void", () => {
    const sendMessageMock = vi.fn().mockResolvedValue(undefined);
    mockUseThreadStream.mockReturnValue({
      thread: {
        messages: [],
        isLoading: false,
        isThreadLoading: false,
        error: null,
        values: {},
        stop: vi.fn(),
        getMessagesMetadata: vi.fn(),
      },
      pendingUsageMessages: [],
      sendMessage: sendMessageMock,
      isUploading: false,
      isHistoryLoading: false,
      hasMoreHistory: false,
      loadMoreHistory: vi.fn(),
    });

    const { rerender } = render(<ChatPage />);
    rerender(<ChatPage />);

    const result = mockLastInputBoxProps.current.onSubmit({
      text: "hello",
      files: [],
    });
    expect(result).toBeUndefined();
    expect(sendMessageMock).toHaveBeenCalledWith("test-thread", {
      text: "hello",
      files: [],
    });
  });

  test("handleStop calls thread.stop", async () => {
    const stopMock = vi.fn().mockResolvedValue(undefined);
    mockUseThreadStream.mockReturnValue({
      thread: {
        messages: [],
        isLoading: false,
        isThreadLoading: false,
        error: null,
        values: {},
        stop: stopMock,
        getMessagesMetadata: vi.fn(),
      },
      pendingUsageMessages: [],
      sendMessage: vi.fn(),
      isUploading: false,
      isHistoryLoading: false,
      hasMoreHistory: false,
      loadMoreHistory: vi.fn(),
    });

    const { rerender } = render(<ChatPage />);
    rerender(<ChatPage />);

    await mockLastInputBoxProps.current.onStop();
    expect(stopMock).toHaveBeenCalled();
  });

  test("static website only mode shows demo message and disables input", () => {
    mockEnvValues.NEXT_PUBLIC_STATIC_WEBSITE_ONLY = "true";
    const { rerender } = render(<ChatPage />);
    rerender(<ChatPage />);
    expect(screen.getByText("Not available in demo")).toBeInTheDocument();
    expect(mockLastInputBoxProps.current.disabled).toBe(true);
    mockEnvValues.NEXT_PUBLIC_STATIC_WEBSITE_ONLY = "false";
  });

  test("input is disabled when isMock is true", () => {
    mockUseThreadChat.mockReturnValue({
      threadId: "test-thread",
      setThreadId: vi.fn(),
      isNewThread: false,
      setIsNewThread: vi.fn(),
      isMock: true,
    });

    const { rerender } = render(<ChatPage />);
    rerender(<ChatPage />);
    expect(mockLastInputBoxProps.current.disabled).toBe(true);
  });

  test("input is disabled when isUploading is true", () => {
    mockUseThreadStream.mockReturnValue({
      thread: {
        messages: [],
        isLoading: false,
        isThreadLoading: false,
        error: null,
        values: {},
        stop: vi.fn(),
        getMessagesMetadata: vi.fn(),
      },
      pendingUsageMessages: [],
      sendMessage: vi.fn(),
      isUploading: true,
      isHistoryLoading: false,
      hasMoreHistory: false,
      loadMoreHistory: vi.fn(),
    });

    const { rerender } = render(<ChatPage />);
    rerender(<ChatPage />);
    expect(mockLastInputBoxProps.current.disabled).toBe(true);
  });

  test("renders WorkbenchHome in welcome mode", () => {
    mockUseThreadChat.mockReturnValue({
      threadId: "test-thread",
      setThreadId: vi.fn(),
      isNewThread: true,
      setIsNewThread: vi.fn(),
      isMock: false,
    });

    const { rerender } = render(<ChatPage />);
    rerender(<ChatPage />);
    expect(screen.getByTestId("workbench-home")).toBeInTheDocument();
  });

  test("does not render WorkbenchHome after send", () => {
    mockUseThreadChat.mockReturnValue({
      threadId: "test-thread",
      setThreadId: vi.fn(),
      isNewThread: false,
      setIsNewThread: vi.fn(),
      isMock: false,
    });

    const { rerender } = render(<ChatPage />);
    rerender(<ChatPage />);
    expect(screen.queryByTestId("workbench-home")).not.toBeInTheDocument();
  });

  test.skip("renders Welcome component in welcome mode", () => {
    mockUseThreadChat.mockReturnValue({
      threadId: "test-thread",
      setThreadId: vi.fn(),
      isNewThread: true,
      setIsNewThread: vi.fn(),
      isMock: false,
    });

    const { rerender } = render(<ChatPage />);
    rerender(<ChatPage />);
    expect(screen.getByTestId("welcome")).toBeInTheDocument();
    expect(mockLastInputBoxProps.current.isWelcomeMode).toBe(true);
  });

  test("does not render Welcome component when not in welcome mode", () => {
    const { rerender } = render(<ChatPage />);
    rerender(<ChatPage />);
    expect(screen.queryByTestId("welcome")).not.toBeInTheDocument();
    expect(mockLastInputBoxProps.current.isWelcomeMode).toBe(false);
  });
});
