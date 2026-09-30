import { act, render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const mockStopFn = vi.fn();
const mockSendMessage = vi.fn();
const mockSetThreadId = vi.fn();
const mockSetIsNewThread = vi.fn();
const mockShowNotification = vi.fn();
const mockSetLocalSettings = vi.fn();
const mockSetSettings = vi.fn();
const mockTextOfMessage = vi.fn().mockReturnValue("");
const mockRouterPush = vi.fn();
const mockRouterReplace = vi.fn();
let agentNameParam = "test-agent";

const { mockUseAgent, mockUseThreadChat, mockUseThreadStream } = vi.hoisted(
  () => ({
    mockUseAgent: vi.fn(),
    mockUseThreadChat: vi.fn(),
    mockUseThreadStream: vi.fn(),
  }),
);

const mockStreamCallbacks: Record<string, any> = {};
let lastInputBoxProps: any = {};
let lastMessageListProps: any = {};
let tokenUsageEnabledFlag = false;

vi.mock("next/navigation", () => ({
  useParams: () => ({ agent_name: agentNameParam }),
  useRouter: () => ({ push: mockRouterPush, replace: mockRouterReplace }),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      common: {
        loading: "Loading...",
        notAvailableInDemoMode: "Not available in demo",
      },
      agents: { newChat: "New Chat" },
    },
  }),
}));

vi.mock("@/core/agents", () => ({
  useAgent: (...args: any[]) => mockUseAgent(...args),
}));

vi.mock("@/components/workspace/chats", () => ({
  ChatBox: ({ children }: any) => <div data-testid="chat-box">{children}</div>,
  useThreadChat: () => mockUseThreadChat(),
  useSpecificChatMode: () => {},
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
    lastInputBoxProps = props;
    return (
      <div
        data-testid="input-box"
        data-welcome-mode={String(props.isWelcomeMode)}
        data-disabled={String(!!props.disabled)}
        data-status={props.status}
      />
    );
  },
}));

vi.mock("@/components/workspace/messages", () => ({
  MessageList: (props: any) => {
    lastMessageListProps = props;
    return <div data-testid="message-list">Messages</div>;
  },
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

let lastTokenUsageProps: any = {};
vi.mock("@/components/workspace/token-usage-indicator", () => ({
  TokenUsageIndicator: (props: any) => {
    lastTokenUsageProps = props;
    return <div data-testid="token-usage" />;
  },
}));

vi.mock("@/components/workspace/tooltip", () => ({
  Tooltip: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: any) => (
    <button {...props}>{children}</button>
  ),
}));

vi.mock("@/core/models/hooks", () => ({
  useModels: () => ({ tokenUsageEnabled: tokenUsageEnabledFlag }),
}));

vi.mock("@/core/notification/hooks", () => ({
  useNotification: () => ({ showNotification: mockShowNotification }),
}));

vi.mock("@/core/settings", () => ({
  useLocalSettings: () => [
    { tokenUsage: { inlineMode: "off" } },
    mockSetLocalSettings,
  ],
  useThreadSettings: () => [{ context: { mode: "flash" } }, mockSetSettings],
}));

vi.mock("@/core/threads/hooks", () => ({
  useThreadStream: (...args: any[]) => mockUseThreadStream(...args),
  useThreadTokenUsage: () => ({ data: null }),
  useThreadMetadata: () => ({
    data: null,
    isLoading: false,
    isFetching: false,
  }),
}));

vi.mock("@/core/threads/token-usage", () => ({
  threadTokenUsageToTokenUsage: () => ({}),
  selectContextUsage: () => null,
}));

vi.mock("@/core/threads/utils", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/core/threads/utils")>()),
  textOfMessage: (...args: any[]) => mockTextOfMessage(...args),
}));

vi.mock("@/core/features", () => ({
  useBrowserControlEnabled: () => ({ enabled: false }),
}));

vi.mock("@/components/workspace/sidecar", () => ({
  SidecarProvider: ({ children }: any) => (
    <div data-testid="sidecar-provider">{children}</div>
  ),
  SidecarTrigger: () => <div data-testid="sidecar-trigger" />,
}));

vi.mock("@/components/workspace/thread-background-tasks", () => ({
  ThreadBackgroundTasks: () => <div data-testid="thread-background-tasks" />,
}));

vi.mock("@/components/workspace/thread-subagent-batches", () => ({
  ThreadSubagentBatches: () => <div data-testid="thread-subagent-batches" />,
}));

vi.mock("@/components/workspace/goal-status", () => ({
  GoalStatus: () => <div data-testid="goal-status" />,
}));

vi.mock("@/components/workspace/use-active-goal", () => ({
  useActiveGoal: () => ({
    activeGoal: null,
    hasGoal: false,
    setLocalGoal: vi.fn(),
  }),
}));

vi.mock("@/components/workspace/context-usage-badge", () => ({
  ContextUsageBadge: () => <div data-testid="context-usage-badge" />,
}));

vi.mock("@/components/ui/sidebar", () => ({
  SidebarTrigger: () => <div data-testid="sidebar-trigger" />,
}));

vi.mock("@/env", () => ({
  env: { NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false" },
}));

vi.mock("@/lib/utils", () => ({
  cn: (...args: any[]) => args.filter(Boolean).join(" "),
}));

import AgentChatPage from "@/app/workspace/capabilities/experts/[agent_name]/chats/[thread_id]/page";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  // Restore document properties
  Object.defineProperty(document, "hidden", {
    value: false,
    configurable: true,
  });
  Object.defineProperty(document, "hasFocus", {
    value: () => true,
    configurable: true,
  });
});

describe("AgentChatPage", () => {
  beforeEach(() => {
    Object.keys(mockStreamCallbacks).forEach(
      (k) => delete mockStreamCallbacks[k],
    );
    lastInputBoxProps = {};
    lastTokenUsageProps = {};
    lastMessageListProps = {};
    tokenUsageEnabledFlag = false;
    agentNameParam = "test-agent";
    mockStopFn.mockReset();
    mockSendMessage.mockReset().mockReturnValue(Promise.resolve());
    mockSetThreadId.mockReset();
    mockSetIsNewThread.mockReset();
    mockShowNotification.mockReset();
    mockTextOfMessage.mockReset().mockReturnValue("");
    mockRouterPush.mockReset();
    mockRouterReplace.mockReset();

    mockUseAgent.mockReturnValue({
      agent: { name: "test-agent", description: "A test agent" },
    });
    mockUseThreadChat.mockReturnValue({
      threadId: "test-thread",
      setThreadId: mockSetThreadId,
      isNewThread: false,
      setIsNewThread: mockSetIsNewThread,
      isMock: false,
    });
    mockUseThreadStream.mockImplementation((args: any) => {
      Object.assign(mockStreamCallbacks, args);
      return {
        thread: {
          messages: [],
          isLoading: false,
          isThreadLoading: false,
          error: null,
          values: {},
          stop: mockStopFn,
          getMessagesMetadata: vi.fn(),
        },
        pendingUsageMessages: [],
        sendMessage: mockSendMessage,
        isUploading: false,
        isHistoryLoading: false,
        hasMoreHistory: false,
        loadMoreHistory: vi.fn(),
      };
    });
  });

  test("renders chat box", () => {
    render(<AgentChatPage />);
    expect(screen.getByTestId("chat-box")).toBeInTheDocument();
  });

  test("renders message list", () => {
    render(<AgentChatPage />);
    expect(screen.getByTestId("message-list")).toBeInTheDocument();
  });

  test("renders agent name badge", () => {
    render(<AgentChatPage />);
    expect(screen.getByText("test-agent")).toBeInTheDocument();
  });

  test("renders new chat button", () => {
    render(<AgentChatPage />);
    expect(screen.getByText("New Chat")).toBeInTheDocument();
  });

  test("renders input box", () => {
    render(<AgentChatPage />);
    expect(screen.getByTestId("input-box")).toBeInTheDocument();
  });

  test("filters the slash skill panel to the agent's closure skills", () => {
    mockUseAgent.mockReturnValue({
      agent: {
        name: "test-agent",
        skills: ["docx-helper", "skill-resource-id"],
      },
    });
    render(<AgentChatPage />);
    expect(lastInputBoxProps.allowedSkillNames).toEqual([
      "docx-helper",
      "skill-resource-id",
    ]);
  });

  test("treats an agent without skills as an empty skill closure", () => {
    mockUseAgent.mockReturnValue({
      agent: { name: "test-agent", skills: null },
    });
    render(<AgentChatPage />);
    expect(lastInputBoxProps.allowedSkillNames).toEqual([]);
  });

  test("leaves skills unfiltered while agent details are loading", () => {
    mockUseAgent.mockReturnValue({ agent: null });
    render(<AgentChatPage />);
    expect(lastInputBoxProps.allowedSkillNames).toBeUndefined();
  });

  test("renders thread title", () => {
    render(<AgentChatPage />);
    expect(screen.getByTestId("thread-title")).toBeInTheDocument();
  });

  test("renders token usage indicator when token usage is enabled", () => {
    tokenUsageEnabledFlag = true;
    render(<AgentChatPage />);
    expect(screen.getByTestId("token-usage")).toBeInTheDocument();
  });

  test("renders the context usage badge when token usage is disabled", () => {
    render(<AgentChatPage />);
    expect(screen.getByTestId("context-usage-badge")).toBeInTheDocument();
    expect(screen.queryByTestId("token-usage")).not.toBeInTheDocument();
  });

  test("renders export trigger", () => {
    render(<AgentChatPage />);
    expect(screen.getByTestId("export-trigger")).toBeInTheDocument();
  });

  test("renders artifact trigger", () => {
    render(<AgentChatPage />);
    expect(screen.getByTestId("artifact-trigger")).toBeInTheDocument();
  });

  test("shows agent name when agent data is available", () => {
    mockUseAgent.mockReturnValue({
      agent: { name: "My Custom Agent", description: "Custom" },
    });
    render(<AgentChatPage />);
    expect(screen.getByText("My Custom Agent")).toBeInTheDocument();
  });

  test("shows agent_name param when agent data is null", () => {
    mockUseAgent.mockReturnValue({ agent: null });
    render(<AgentChatPage />);
    expect(screen.getByText("test-agent")).toBeInTheDocument();
  });

  test("sets welcome mode for new thread", () => {
    mockUseThreadChat.mockReturnValue({
      threadId: "new",
      setThreadId: mockSetThreadId,
      isNewThread: true,
      setIsNewThread: mockSetIsNewThread,
      isMock: false,
    });

    render(<AgentChatPage />);
    const inputBox = screen.getByTestId("input-box");
    expect(inputBox.getAttribute("data-welcome-mode")).toBe("true");
  });

  test("sets non-welcome mode for existing thread", () => {
    render(<AgentChatPage />);
    const inputBox = screen.getByTestId("input-box");
    expect(inputBox.getAttribute("data-welcome-mode")).toBe("false");
  });

  test("renders todo list when todos exist", () => {
    mockUseThreadStream.mockImplementation((args: any) => {
      Object.assign(mockStreamCallbacks, args);
      return {
        thread: {
          messages: [],
          isLoading: false,
          isThreadLoading: false,
          error: null,
          values: { todos: [{ id: "1", text: "Task 1", done: false }] },
          stop: mockStopFn,
          getMessagesMetadata: vi.fn(),
        },
        pendingUsageMessages: [],
        sendMessage: mockSendMessage,
        isUploading: false,
        isHistoryLoading: false,
        hasMoreHistory: false,
        loadMoreHistory: vi.fn(),
      };
    });

    render(<AgentChatPage />);
    expect(screen.getByTestId("todo-list")).toBeInTheDocument();
  });

  test("does not render todo list when no todos", () => {
    render(<AgentChatPage />);
    expect(screen.queryByTestId("todo-list")).not.toBeInTheDocument();
  });

  // --- onSend callback (line 77-79) ---
  test("onSend callback sets welcome mode to false", () => {
    mockUseThreadChat.mockReturnValue({
      threadId: "new",
      setThreadId: mockSetThreadId,
      isNewThread: true,
      setIsNewThread: mockSetIsNewThread,
      isMock: false,
    });

    render(<AgentChatPage />);
    expect(
      screen.getByTestId("input-box").getAttribute("data-welcome-mode"),
    ).toBe("true");

    act(() => {
      mockStreamCallbacks.onSend();
    });

    expect(
      screen.getByTestId("input-box").getAttribute("data-welcome-mode"),
    ).toBe("false");
  });

  // --- onStart callback (line 80-88) ---
  test("onStart callback updates threadId and replaces URL", () => {
    mockUseThreadChat.mockReturnValue({
      threadId: "new",
      setThreadId: mockSetThreadId,
      isNewThread: true,
      setIsNewThread: mockSetIsNewThread,
      isMock: false,
    });

    const replaceStateSpy = vi.spyOn(history, "replaceState");

    render(<AgentChatPage />);
    act(() => {
      mockStreamCallbacks.onStart("created-thread-123");
    });

    expect(mockSetThreadId).toHaveBeenCalledWith("created-thread-123");
    expect(mockSetIsNewThread).toHaveBeenCalledWith(false);
    expect(replaceStateSpy).toHaveBeenCalledWith(
      null,
      "",
      "/workspace/capabilities/experts/test-agent/chats/created-thread-123",
    );

    replaceStateSpy.mockRestore();
  });

  test("encodes expert and thread route segments after a chat starts", () => {
    agentNameParam = "ops/team";
    mockUseThreadChat.mockReturnValue({
      threadId: "new",
      setThreadId: mockSetThreadId,
      isNewThread: true,
      setIsNewThread: mockSetIsNewThread,
      isMock: false,
    });
    const replaceStateSpy = vi.spyOn(history, "replaceState");

    render(<AgentChatPage />);
    act(() => mockStreamCallbacks.onStart("thread/#1"));

    expect(replaceStateSpy).toHaveBeenCalledWith(
      null,
      "",
      "/workspace/capabilities/experts/ops%2Fteam/chats/thread%2F%231",
    );
    replaceStateSpy.mockRestore();
  });

  // --- onFinish callback - document visible (line 91) ---
  test("onFinish does not show notification when document is visible", () => {
    Object.defineProperty(document, "hidden", {
      value: false,
      configurable: true,
    });
    Object.defineProperty(document, "hasFocus", {
      value: () => true,
      configurable: true,
    });

    render(<AgentChatPage />);
    mockStreamCallbacks.onFinish({
      messages: [{ content: "hello" }],
      title: "Test Title",
    });

    expect(mockShowNotification).not.toHaveBeenCalled();
  });

  // --- onFinish callback - document has focus but not hidden (line 91) ---
  test("onFinish does not show notification when document has focus and is visible", () => {
    Object.defineProperty(document, "hidden", {
      value: false,
      configurable: true,
    });
    Object.defineProperty(document, "hasFocus", {
      value: () => true,
      configurable: true,
    });

    render(<AgentChatPage />);
    mockStreamCallbacks.onFinish({
      messages: [{ content: "test" }],
      title: "Done",
    });

    expect(mockShowNotification).not.toHaveBeenCalled();
  });

  // --- onFinish callback - document hidden, shows notification (line 91-103) ---
  test("onFinish shows notification when document is hidden", () => {
    mockTextOfMessage.mockReturnValue("hello world");
    Object.defineProperty(document, "hidden", {
      value: true,
      configurable: true,
    });
    Object.defineProperty(document, "hasFocus", {
      value: () => false,
      configurable: true,
    });

    render(<AgentChatPage />);
    mockStreamCallbacks.onFinish({
      messages: [{ content: "hello world" }],
      title: "Chat Done",
    });

    expect(mockShowNotification).toHaveBeenCalledWith("Chat Done", {
      body: "hello world",
    });
  });

  // --- onFinish - document hidden but has focus (line 91: document.hidden || !document.hasFocus()) ---
  test("onFinish shows notification when document is hidden even if focused", () => {
    mockTextOfMessage.mockReturnValue("result text");
    Object.defineProperty(document, "hidden", {
      value: true,
      configurable: true,
    });
    Object.defineProperty(document, "hasFocus", {
      value: () => true,
      configurable: true,
    });

    render(<AgentChatPage />);
    mockStreamCallbacks.onFinish({
      messages: [{ content: "result text" }],
      title: "Finished",
    });

    expect(mockShowNotification).toHaveBeenCalledWith("Finished", {
      body: "result text",
    });
  });

  // --- onFinish - long message truncated (line 98-99) ---
  test("onFinish truncates long messages in notification body", () => {
    mockTextOfMessage.mockReturnValue("a".repeat(250));
    Object.defineProperty(document, "hidden", {
      value: true,
      configurable: true,
    });
    Object.defineProperty(document, "hasFocus", {
      value: () => false,
      configurable: true,
    });

    render(<AgentChatPage />);
    mockStreamCallbacks.onFinish({
      messages: [{ content: "a".repeat(250) }],
      title: "Done",
    });

    expect(mockShowNotification).toHaveBeenCalledWith("Done", {
      body: "a".repeat(200) + "...",
    });
  });

  // --- onFinish - no messages (line 93: default body) ---
  test("onFinish uses default body when no messages", () => {
    Object.defineProperty(document, "hidden", {
      value: true,
      configurable: true,
    });
    Object.defineProperty(document, "hasFocus", {
      value: () => false,
      configurable: true,
    });

    render(<AgentChatPage />);
    mockStreamCallbacks.onFinish({
      messages: [],
      title: "Empty Chat",
    });

    expect(mockShowNotification).toHaveBeenCalledWith("Empty Chat", {
      body: "Conversation finished",
    });
  });

  // --- onFinish - message with no textContent (line 96: textContent falsy) ---
  test("onFinish uses default body when last message has no text content", () => {
    mockTextOfMessage.mockReturnValue("");
    Object.defineProperty(document, "hidden", {
      value: true,
      configurable: true,
    });
    Object.defineProperty(document, "hasFocus", {
      value: () => false,
      configurable: true,
    });

    render(<AgentChatPage />);
    mockStreamCallbacks.onFinish({
      messages: [{ content: null }],
      title: "Empty",
    });

    expect(mockShowNotification).toHaveBeenCalledWith("Empty", {
      body: "Conversation finished",
    });
  });

  // --- handleSubmit with files (line 111-112) ---
  test("handleSubmit returns promise when message has files", () => {
    render(<AgentChatPage />);
    const result = lastInputBoxProps.onSubmit({
      text: "hello",
      files: [new File([""], "test.png")],
    });
    expect(mockSendMessage).toHaveBeenCalledWith(
      "test-thread",
      { text: "hello", files: [expect.any(File)] },
      { agent_name: "test-agent" },
      undefined,
    );
    expect(result).toBeInstanceOf(Promise);
  });

  // --- handleSubmit without files (line 114) ---
  test("handleSubmit returns undefined when message has no files", () => {
    render(<AgentChatPage />);
    const result = lastInputBoxProps.onSubmit({ text: "hello", files: [] });
    expect(mockSendMessage).toHaveBeenCalledWith(
      "test-thread",
      { text: "hello", files: [] },
      { agent_name: "test-agent" },
      undefined,
    );
    expect(result).toBeUndefined();
  });

  // --- handleStop (line 119-121) ---
  test("handleStop calls thread.stop", async () => {
    render(<AgentChatPage />);
    await lastInputBoxProps.onStop();
    expect(mockStopFn).toHaveBeenCalled();
  });

  // --- isUploading disables input (line 252) ---
  test("input box is disabled when isUploading is true", () => {
    mockUseThreadStream.mockImplementation((args: any) => {
      Object.assign(mockStreamCallbacks, args);
      return {
        thread: {
          messages: [],
          isLoading: false,
          isThreadLoading: false,
          error: null,
          values: {},
          stop: mockStopFn,
          getMessagesMetadata: vi.fn(),
        },
        pendingUsageMessages: [],
        sendMessage: mockSendMessage,
        isUploading: true,
        isHistoryLoading: false,
        hasMoreHistory: false,
        loadMoreHistory: vi.fn(),
      };
    });

    render(<AgentChatPage />);
    expect(screen.getByTestId("input-box").getAttribute("data-disabled")).toBe(
      "true",
    );
  });

  // --- Input not disabled when not uploading ---
  test("input box is not disabled when isUploading is false", () => {
    render(<AgentChatPage />);
    expect(screen.getByTestId("input-box").getAttribute("data-disabled")).toBe(
      "false",
    );
  });

  // --- Static website only mode (line 259-262) ---
  // Note: env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY is statically mocked as "false" at import time.
  // The conditional rendering at line 259 and disabled at line 252 cannot be tested with
  // the static import approach. The isUploading path in the OR condition (line 253) is
  // tested separately above.

  // --- tokenUsageInlineMode when tokenUsageEnabled is false (line 123-125) ---
  test("token usage indicator receives inline mode preference", () => {
    tokenUsageEnabledFlag = true;
    render(<AgentChatPage />);
    expect(screen.getByTestId("token-usage")).toBeInTheDocument();
    expect(lastTokenUsageProps.preferences).toEqual({
      inlineMode: "off",
    });
  });

  // --- isMock conditional in useThreadTokenUsage (line 54-55) ---
  test("passes isMock=true to useThreadChat (isMock conditional)", () => {
    mockUseThreadChat.mockReturnValue({
      threadId: "test-thread",
      setThreadId: mockSetThreadId,
      isNewThread: false,
      setIsNewThread: mockSetIsNewThread,
      isMock: true,
    });

    render(<AgentChatPage />);
    expect(screen.getByTestId("chat-box")).toBeInTheDocument();
  });

  // --- isNewThread affects useThreadTokenUsage (line 54) ---
  test("passes isNewThread=true threadId to useThreadChat", () => {
    mockUseThreadChat.mockReturnValue({
      threadId: "new",
      setThreadId: mockSetThreadId,
      isNewThread: true,
      setIsNewThread: mockSetIsNewThread,
      isMock: false,
    });

    render(<AgentChatPage />);
    expect(screen.getByTestId("chat-box")).toBeInTheDocument();
  });

  // --- thread.isLoading status (line 241-242) ---
  test("passes 'streaming' status when thread is loading", () => {
    mockUseThreadStream.mockImplementation((args: any) => {
      Object.assign(mockStreamCallbacks, args);
      return {
        thread: {
          messages: [],
          isLoading: true,
          isThreadLoading: false,
          error: null,
          values: {},
          stop: mockStopFn,
          getMessagesMetadata: vi.fn(),
        },
        pendingUsageMessages: [],
        sendMessage: mockSendMessage,
        isUploading: false,
        isHistoryLoading: false,
        hasMoreHistory: false,
        loadMoreHistory: vi.fn(),
      };
    });

    render(<AgentChatPage />);
    expect(screen.getByTestId("input-box").getAttribute("data-status")).toBe(
      "streaming",
    );
  });

  // --- thread.error status (line 239-240) ---
  test("passes 'error' status when thread has error", () => {
    mockUseThreadStream.mockImplementation((args: any) => {
      Object.assign(mockStreamCallbacks, args);
      return {
        thread: {
          messages: [],
          isLoading: false,
          isThreadLoading: false,
          error: new Error("test error"),
          values: {},
          stop: mockStopFn,
          getMessagesMetadata: vi.fn(),
        },
        pendingUsageMessages: [],
        sendMessage: mockSendMessage,
        isUploading: false,
        isHistoryLoading: false,
        hasMoreHistory: false,
        loadMoreHistory: vi.fn(),
      };
    });

    render(<AgentChatPage />);
    expect(screen.getByTestId("input-box").getAttribute("data-status")).toBe(
      "error",
    );
  });

  // --- normal status (line 243) ---
  test("passes 'ready' status when not loading and no error", () => {
    render(<AgentChatPage />);
    expect(screen.getByTestId("input-box").getAttribute("data-status")).toBe(
      "ready",
    );
  });

  // --- new chat button onClick (line 156-158) ---
  test("new chat button navigates to new chat page", () => {
    render(<AgentChatPage />);
    const newChatButton = screen.getByText("New Chat").closest("button");
    newChatButton?.click();

    expect(mockRouterPush).toHaveBeenCalledWith(
      "/workspace/capabilities/experts/test-agent/chats/new",
    );
  });

  // --- onContextChange handler (line 255) ---
  test("onContextChange updates settings context", () => {
    render(<AgentChatPage />);
    lastInputBoxProps.onContextChange({ mode: "deep" });
    expect(mockSetSettings).toHaveBeenCalledWith("context", { mode: "deep" });
  });

  // --- clarification cards stay answerable in expert chats ---
  test("passes a clarification submit handler that sends a hidden reply", async () => {
    mockSendMessage.mockImplementation(async (...args: unknown[]) => {
      (args[3] as { onSent?: () => void } | undefined)?.onSent?.();
    });
    render(<AgentChatPage />);

    expect(typeof lastMessageListProps.onSubmitHumanInput).toBe("function");
    const sent = await lastMessageListProps.onSubmitHumanInput(
      { question: "Which files?" },
      { value: "All reports" },
    );

    expect(sent).toBe(true);
    const [, message, context, options] = mockSendMessage.mock.calls.at(-1)!;
    expect(message).toEqual({
      text: 'For your clarification "Which files?", my answer is: All reports',
      files: [],
    });
    expect(context).toEqual({ agent_name: "test-agent" });
    expect(options.additionalKwargs).toMatchObject({
      hide_from_ui: true,
      human_input_response: { value: "All reports" },
    });
  });

  // --- onPreferencesChange handler (line 170-172) ---
  test("onPreferencesChange updates local settings for token usage", () => {
    tokenUsageEnabledFlag = true;
    render(<AgentChatPage />);
    lastTokenUsageProps.onPreferencesChange({ inlineMode: "compact" });
    expect(mockSetLocalSettings).toHaveBeenCalledWith("tokenUsage", {
      inlineMode: "compact",
    });
  });
});
