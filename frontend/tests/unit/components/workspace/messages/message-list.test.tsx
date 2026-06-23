import {
  render,
  screen,
  fireEvent,
  cleanup,
  act,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ---------------------------------------------------------------------------
// Hoisted mock functions (mutable per test)
// ---------------------------------------------------------------------------
const {
  mockGetMessageGroups,
  mockGetAssistantTurnUsageMessages,
  mockGetAssistantTurnCopyData,
  mockGetStreamingMessageLookup,
  mockIsAssistantMessageGroupStreaming,
  mockExtractContentFromMessage,
  mockExtractPresentFilesFromMessage,
  mockExtractTextFromMessage,
  mockHasContent,
  mockHasPresentFiles,
  mockHasReasoning,
  mockBuildTokenDebugSteps,
  mockUseUpdateSubtask,
  mockParseSubtaskResult,
} = vi.hoisted(() => ({
  mockGetMessageGroups: vi.fn(),
  mockGetAssistantTurnUsageMessages: vi.fn(),
  mockGetAssistantTurnCopyData: vi.fn(),
  mockGetStreamingMessageLookup: vi.fn(),
  mockIsAssistantMessageGroupStreaming: vi.fn(),
  mockExtractContentFromMessage: vi.fn(),
  mockExtractPresentFilesFromMessage: vi.fn(),
  mockExtractTextFromMessage: vi.fn(),
  mockHasContent: vi.fn(),
  mockHasPresentFiles: vi.fn(),
  mockHasReasoning: vi.fn(),
  mockBuildTokenDebugSteps: vi.fn(),
  mockUseUpdateSubtask: vi.fn(),
  mockParseSubtaskResult: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Static component mocks
// ---------------------------------------------------------------------------
vi.mock("@/components/ai-elements/conversation", () => ({
  Conversation: ({ children, className, ...props }: any) => (
    <div data-testid="conversation" data-class={className} {...props}>
      {children}
    </div>
  ),
  ConversationContent: ({ children, className, ...props }: any) => (
    <div data-testid="conversation-content" data-class={className} {...props}>
      {children}
    </div>
  ),
}));

vi.mock("@/components/workspace/artifacts/artifact-file-list", () => ({
  ArtifactFileList: ({ files, threadId }: any) => (
    <div
      data-testid="artifact-file-list"
      data-files={JSON.stringify(files)}
      data-thread-id={threadId}
    />
  ),
}));

vi.mock("@/components/workspace/copy-button", () => ({
  CopyButton: ({ clipboardData }: any) => (
    <button data-testid="copy-button" data-clipboard={clipboardData} />
  ),
}));

vi.mock("@/components/workspace/streaming-indicator", () => ({
  StreamingIndicator: (props: any) => <div data-testid="streaming-indicator" />,
}));

vi.mock("@/components/workspace/messages/markdown-content", () => ({
  MarkdownContent: ({ content, isLoading, className }: any) => (
    <div
      data-testid="markdown-content"
      data-content={content}
      data-is-loading={isLoading}
      data-class={className}
    />
  ),
}));

vi.mock("@/components/workspace/messages/message-group", () => ({
  MessageGroup: ({
    messages,
    isLoading,
    tokenDebugSteps,
    showTokenDebugSummaries,
  }: any) => (
    <div
      data-testid="message-group"
      data-count={messages?.length}
      data-is-loading={isLoading}
      data-debug-step-count={tokenDebugSteps?.length}
      data-show-debug-summaries={showTokenDebugSummaries}
    />
  ),
}));

vi.mock("@/components/workspace/messages/message-list-item", () => ({
  MessageListItem: ({ message, isLoading, threadId, showCopyButton }: any) => (
    <div
      data-testid="message-list-item"
      data-type={message?.type}
      data-message-id={message?.id}
      data-is-loading={isLoading}
      data-thread-id={threadId}
      data-show-copy-button={showCopyButton}
    />
  ),
}));

vi.mock("@/components/workspace/messages/message-token-usage", () => ({
  MessageTokenUsageDebugList: ({ enabled, isLoading, steps }: any) => (
    <div
      data-testid="token-usage-debug"
      data-step-count={steps?.length}
      data-enabled={enabled}
    />
  ),
  MessageTokenUsageList: ({ enabled, isLoading, messages }: any) => (
    <div
      data-testid="token-usage-list"
      data-message-count={messages?.length}
      data-enabled={enabled}
    />
  ),
}));

vi.mock("@/components/workspace/messages/skeleton", () => ({
  MessageListSkeleton: () => (
    <div data-testid="skeleton">Loading messages...</div>
  ),
}));

vi.mock("@/components/workspace/messages/subtask-card", () => ({
  SubtaskCard: ({ taskId, isLoading }: any) => (
    <div
      data-testid="subtask-card"
      data-task-id={taskId}
      data-is-loading={isLoading}
    />
  ),
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, disabled, onClick, variant, size, ...props }: any) => (
    <button
      disabled={disabled}
      onClick={onClick}
      data-variant={variant}
      data-size={size}
      {...props}
    >
      {children}
    </button>
  ),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      common: { loading: "Loading...", loadMore: "Load More" },
      subtasks: { executing: (n: number) => `Executing ${n} tasks` },
    },
  }),
}));

vi.mock("lucide-react", () => ({
  Loader2Icon: (props: any) => <span data-testid="loader-icon" {...props} />,
  ChevronUpIcon: (props: any) => <span data-testid="chevron-icon" {...props} />,
}));

// ---------------------------------------------------------------------------
// Mutable function mocks
// ---------------------------------------------------------------------------
vi.mock("@/core/messages/usage-model", () => ({
  buildTokenDebugSteps: (...args: any[]) => mockBuildTokenDebugSteps(...args),
}));

vi.mock("@/core/messages/utils", () => ({
  extractContentFromMessage: (...args: any[]) =>
    mockExtractContentFromMessage(...args),
  extractPresentFilesFromMessage: (...args: any[]) =>
    mockExtractPresentFilesFromMessage(...args),
  extractTextFromMessage: (...args: any[]) =>
    mockExtractTextFromMessage(...args),
  getAssistantTurnCopyData: (...args: any[]) =>
    mockGetAssistantTurnCopyData(...args),
  getAssistantTurnUsageMessages: (...args: any[]) =>
    mockGetAssistantTurnUsageMessages(...args),
  getMessageGroups: (...args: any[]) => mockGetMessageGroups(...args),
  getStreamingMessageLookup: (...args: any[]) =>
    mockGetStreamingMessageLookup(...args),
  hasContent: (...args: any[]) => mockHasContent(...args),
  hasPresentFiles: (...args: any[]) => mockHasPresentFiles(...args),
  hasReasoning: (...args: any[]) => mockHasReasoning(...args),
  isAssistantMessageGroupStreaming: (...args: any[]) =>
    mockIsAssistantMessageGroupStreaming(...args),
}));

vi.mock("@/core/rehype", () => ({
  useRehypeSplitWordsIntoSpans: () => [],
}));

vi.mock("@/core/tasks/context", () => ({
  useUpdateSubtask: (...args: any[]) => mockUseUpdateSubtask(...args),
}));

vi.mock("@/core/tasks/subtask-result", () => ({
  parseSubtaskResult: (...args: any[]) => mockParseSubtaskResult(...args),
}));

vi.mock("@/lib/utils", () => ({
  cn: (...args: any[]) => args.filter(Boolean).join(" "),
}));

// ---------------------------------------------------------------------------
// Import component under test (after mocks)
// ---------------------------------------------------------------------------
import {
  MessageList,
  MESSAGE_LIST_DEFAULT_PADDING_BOTTOM,
} from "@/components/workspace/messages/message-list";

// ---------------------------------------------------------------------------
// IntersectionObserver mock
// ---------------------------------------------------------------------------
let intersectionCallback: ((entries: any[]) => void) | null = null;
const mockObserve = vi.fn();
const mockDisconnect = vi.fn();

beforeEach(() => {
  // Clear all mock call histories from previous tests
  vi.clearAllMocks();

  // Default mock implementations
  mockGetMessageGroups.mockReturnValue([]);
  mockGetAssistantTurnUsageMessages.mockReturnValue([]);
  mockGetAssistantTurnCopyData.mockReturnValue(null);
  mockGetStreamingMessageLookup.mockReturnValue({
    ids: new Set(),
    messages: new Set(),
  });
  mockIsAssistantMessageGroupStreaming.mockReturnValue(false);
  mockExtractContentFromMessage.mockReturnValue("");
  mockExtractPresentFilesFromMessage.mockReturnValue([]);
  mockExtractTextFromMessage.mockReturnValue("");
  mockHasContent.mockReturnValue(false);
  mockHasPresentFiles.mockReturnValue(false);
  mockHasReasoning.mockReturnValue(false);
  mockBuildTokenDebugSteps.mockReturnValue([]);
  mockUseUpdateSubtask.mockReturnValue(vi.fn());
  mockParseSubtaskResult.mockReturnValue({ status: "in_progress" });

  // Reset IntersectionObserver mock with a proper class constructor
  intersectionCallback = null;
  mockObserve.mockReset();
  mockDisconnect.mockReset();
  Object.defineProperty(globalThis, "IntersectionObserver", {
    value: class MockIntersectionObserver {
      constructor(cb: (entries: any[]) => void) {
        intersectionCallback = cb;
      }
      observe = mockObserve;
      disconnect = mockDisconnect;
      unobserve = vi.fn();
    },
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  cleanup();
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function createThread(overrides: Record<string, any> = {}) {
  return {
    messages: [],
    isLoading: false,
    isThreadLoading: false,
    values: {},
    stop: vi.fn(),
    getMessagesMetadata: vi.fn(),
    ...overrides,
  } as any;
}

function createHumanGroup(id = "g1", ...messages: any[]) {
  return { type: "human", id, messages };
}

function createAssistantGroup(id = "g1", ...messages: any[]) {
  return { type: "assistant", id, messages };
}

function createClarificationGroup(id = "g1", ...messages: any[]) {
  return { type: "assistant:clarification", id, messages };
}

function createPresentFilesGroup(id = "g1", ...messages: any[]) {
  return { type: "assistant:present-files", id, messages };
}

function createSubagentGroup(id = "g1", ...messages: any[]) {
  return { type: "assistant:subagent", id, messages };
}

function createDefaultGroup(id = "g1", ...messages: any[]) {
  return { type: "assistant:processing", id, messages };
}

function createHumanMessage(id = "hm-1", content = "Hello") {
  return { type: "human", id, content };
}

function createAIMessage(
  id = "ai-1",
  content: any = "Hi there",
  toolCalls?: any[],
) {
  const msg: any = { type: "ai", id, content };
  if (toolCalls) msg.tool_calls = toolCalls;
  return msg;
}

function createToolMessage(
  id = "tool-1",
  toolCallId = "tc-1",
  content = "done",
) {
  return { type: "tool", id, tool_call_id: toolCallId, content };
}

function createTaskToolCall(
  id = "task-1",
  subagentType = "research",
  description = "desc",
  prompt = "prompt",
) {
  return {
    name: "task",
    id,
    args: { subagent_type: subagentType, description, prompt },
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe("MESSAGE_LIST_DEFAULT_PADDING_BOTTOM", () => {
  test("exports the correct value", () => {
    expect(MESSAGE_LIST_DEFAULT_PADDING_BOTTOM).toBe(24);
  });
});

describe("MessageList", () => {
  // ========================================================================
  // Loading states
  // ========================================================================
  describe("loading states", () => {
    test("shows skeleton when isThreadLoading is true and messages array is empty", () => {
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ isThreadLoading: true, messages: [] })}
        />,
      );
      expect(screen.getByTestId("skeleton")).toBeInTheDocument();
      expect(screen.queryByTestId("conversation")).not.toBeInTheDocument();
    });

    test("does not show skeleton when isThreadLoading is true but messages exist", () => {
      mockGetMessageGroups.mockReturnValue([
        createHumanGroup("g1", createHumanMessage()),
      ]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({
            isThreadLoading: true,
            messages: [createHumanMessage()],
          })}
        />,
      );
      expect(screen.queryByTestId("skeleton")).not.toBeInTheDocument();
      expect(screen.getByTestId("conversation")).toBeInTheDocument();
    });

    test("does not show skeleton when isThreadLoading is false", () => {
      render(<MessageList threadId="t1" thread={createThread()} />);
      expect(screen.queryByTestId("skeleton")).not.toBeInTheDocument();
    });
  });

  // ========================================================================
  // Layout and styling
  // ========================================================================
  describe("layout and styling", () => {
    test("renders conversation container", () => {
      render(<MessageList threadId="t1" thread={createThread()} />);
      expect(screen.getByTestId("conversation")).toBeInTheDocument();
    });

    test("applies custom className to conversation", () => {
      render(
        <MessageList
          threadId="t1"
          thread={createThread()}
          className="my-custom-class"
        />,
      );
      const conv = screen.getByTestId("conversation");
      expect(conv.getAttribute("data-class")).toContain("my-custom-class");
    });

    test("uses default padding of 24px", () => {
      render(<MessageList threadId="t1" thread={createThread()} />);
      const paddingDiv = screen
        .getByTestId("conversation-content")
        .querySelector("div:last-child");
      expect(paddingDiv?.getAttribute("style")).toBe("height: 24px;");
    });

    test("uses custom padding value", () => {
      render(
        <MessageList
          threadId="t1"
          thread={createThread()}
          paddingBottom={48}
        />,
      );
      const paddingDiv = screen
        .getByTestId("conversation-content")
        .querySelector("div:last-child");
      expect(paddingDiv?.getAttribute("style")).toBe("height: 48px;");
    });
  });

  // ========================================================================
  // Streaming indicator
  // ========================================================================
  describe("streaming indicator", () => {
    test("shows streaming indicator when isLoading is true", () => {
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ isLoading: true })}
        />,
      );
      expect(screen.getByTestId("streaming-indicator")).toBeInTheDocument();
    });

    test("does not show streaming indicator when isLoading is false", () => {
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ isLoading: false })}
        />,
      );
      expect(
        screen.queryByTestId("streaming-indicator"),
      ).not.toBeInTheDocument();
    });
  });

  // ========================================================================
  // Human / Assistant groups
  // ========================================================================
  describe("human and assistant groups", () => {
    test("renders MessageListItem for each message in a human group", () => {
      const msgs = [
        createHumanMessage("h1", "Hello"),
        createHumanMessage("h2", "World"),
      ];
      mockGetMessageGroups.mockReturnValue([createHumanGroup("g1", ...msgs)]);
      render(
        <MessageList threadId="t1" thread={createThread({ messages: msgs })} />,
      );
      const items = screen.getAllByTestId("message-list-item");
      expect(items).toHaveLength(2);
      expect(items[0]!.getAttribute("data-message-id")).toBe("h1");
      expect(items[1]!.getAttribute("data-message-id")).toBe("h2");
    });

    test("passes showCopyButton=true for human groups", () => {
      const msg = createHumanMessage("h1");
      mockGetMessageGroups.mockReturnValue([createHumanGroup("g1", msg)]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
        />,
      );
      expect(
        screen
          .getByTestId("message-list-item")
          .getAttribute("data-show-copy-button"),
      ).toBe("true");
    });

    test("passes showCopyButton=false for assistant groups", () => {
      const msg = createAIMessage("a1");
      mockGetMessageGroups.mockReturnValue([createAssistantGroup("g1", msg)]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
        />,
      );
      expect(
        screen
          .getByTestId("message-list-item")
          .getAttribute("data-show-copy-button"),
      ).toBe("false");
    });

    test("applies group/assistant-turn class to assistant group wrapper", () => {
      const msg = createAIMessage("a1");
      mockGetMessageGroups.mockReturnValue([createAssistantGroup("g1", msg)]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
        />,
      );
      const wrapper = screen.getByTestId("message-list-item").parentElement;
      expect(wrapper?.className).toContain("group/assistant-turn");
    });

    test("does not apply group/assistant-turn class to human group wrapper", () => {
      const msg = createHumanMessage("h1");
      mockGetMessageGroups.mockReturnValue([createHumanGroup("g1", msg)]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
        />,
      );
      const wrapper = screen.getByTestId("message-list-item").parentElement;
      expect(wrapper?.className).not.toContain("group/assistant-turn");
    });

    test("passes threadId and isLoading to MessageListItem", () => {
      const msg = createAIMessage("a1");
      mockGetMessageGroups.mockReturnValue([createAssistantGroup("g1", msg)]);
      render(
        <MessageList
          threadId="t42"
          thread={createThread({ isLoading: true, messages: [msg] })}
        />,
      );
      const item = screen.getByTestId("message-list-item");
      expect(item.getAttribute("data-thread-id")).toBe("t42");
      expect(item.getAttribute("data-is-loading")).toBe("true");
    });
  });

  // ========================================================================
  // Assistant copy button
  // ========================================================================
  describe("assistant copy button", () => {
    test("renders CopyButton when getAssistantTurnCopyData returns data", () => {
      const msg = createAIMessage("a1", "Response text");
      mockGetMessageGroups.mockReturnValue([createAssistantGroup("g1", msg)]);
      mockGetAssistantTurnCopyData.mockReturnValue("Response text");
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
        />,
      );
      expect(screen.getByTestId("copy-button")).toBeInTheDocument();
    });

    test("does not render CopyButton when getAssistantTurnCopyData returns null", () => {
      const msg = createAIMessage("a1");
      mockGetMessageGroups.mockReturnValue([createAssistantGroup("g1", msg)]);
      mockGetAssistantTurnCopyData.mockReturnValue(null);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
        />,
      );
      expect(screen.queryByTestId("copy-button")).not.toBeInTheDocument();
    });

    test("does not render CopyButton for human groups", () => {
      const msg = createHumanMessage("h1");
      mockGetMessageGroups.mockReturnValue([createHumanGroup("g1", msg)]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
        />,
      );
      expect(screen.queryByTestId("copy-button")).not.toBeInTheDocument();
    });

    test("passes isStreaming flag to getAssistantTurnCopyData", () => {
      const msg = createAIMessage("a1", "text");
      mockGetMessageGroups.mockReturnValue([createAssistantGroup("g1", msg)]);
      mockIsAssistantMessageGroupStreaming.mockReturnValue(true);
      mockGetStreamingMessageLookup.mockReturnValue({
        ids: new Set(["a1"]),
        messages: new Set(),
      });
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ isLoading: true, messages: [msg] })}
        />,
      );
      expect(mockGetAssistantTurnCopyData).toHaveBeenCalledWith([msg], {
        isStreaming: true,
      });
    });
  });

  // ========================================================================
  // assistant:clarification groups
  // ========================================================================
  describe("assistant:clarification groups", () => {
    test("renders MarkdownContent when first message has content", () => {
      const msg = createAIMessage("cl-1", "Please clarify...");
      mockGetMessageGroups.mockReturnValue([
        createClarificationGroup("g1", msg),
      ]);
      mockHasContent.mockReturnValue(true);
      mockExtractContentFromMessage.mockReturnValue("Please clarify...");
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
        />,
      );
      expect(screen.getByTestId("markdown-content")).toBeInTheDocument();
      expect(
        screen.getByTestId("markdown-content").getAttribute("data-content"),
      ).toBe("Please clarify...");
    });

    test("returns null when first message has no content", () => {
      const msg = createAIMessage("cl-1", "");
      mockGetMessageGroups.mockReturnValue([
        createClarificationGroup("g1", msg),
      ]);
      mockHasContent.mockReturnValue(false);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
        />,
      );
      expect(screen.queryByTestId("markdown-content")).not.toBeInTheDocument();
      expect(screen.queryByTestId("message-list-item")).not.toBeInTheDocument();
    });

    test("returns null when group has no messages", () => {
      mockGetMessageGroups.mockReturnValue([createClarificationGroup("g1")]);
      render(<MessageList threadId="t1" thread={createThread()} />);
      expect(screen.queryByTestId("markdown-content")).not.toBeInTheDocument();
    });
  });

  // ========================================================================
  // assistant:present-files groups
  // ========================================================================
  describe("assistant:present-files groups", () => {
    test("always renders ArtifactFileList", () => {
      const msg = createAIMessage("pf-1");
      mockGetMessageGroups.mockReturnValue([
        createPresentFilesGroup("g1", msg),
      ]);
      mockHasPresentFiles.mockReturnValue(true);
      mockExtractPresentFilesFromMessage.mockReturnValue(["file.pdf"]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
        />,
      );
      expect(screen.getByTestId("artifact-file-list")).toBeInTheDocument();
    });

    test("passes extracted files to ArtifactFileList", () => {
      const msg = createAIMessage("pf-1");
      mockGetMessageGroups.mockReturnValue([
        createPresentFilesGroup("g1", msg),
      ]);
      mockHasPresentFiles.mockReturnValue(true);
      mockExtractPresentFilesFromMessage.mockReturnValue([
        "file1.pdf",
        "file2.xlsx",
      ]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
        />,
      );
      const fileList = screen.getByTestId("artifact-file-list");
      expect(fileList.getAttribute("data-files")).toBe(
        JSON.stringify(["file1.pdf", "file2.xlsx"]),
      );
    });

    test("passes threadId to ArtifactFileList", () => {
      const msg = createAIMessage("pf-1");
      mockGetMessageGroups.mockReturnValue([
        createPresentFilesGroup("g1", msg),
      ]);
      mockHasPresentFiles.mockReturnValue(true);
      mockExtractPresentFilesFromMessage.mockReturnValue([]);
      render(
        <MessageList
          threadId="t99"
          thread={createThread({ messages: [msg] })}
        />,
      );
      expect(
        screen.getByTestId("artifact-file-list").getAttribute("data-thread-id"),
      ).toBe("t99");
    });

    test("renders MarkdownContent when first message has content", () => {
      const msg = createAIMessage("pf-1", "Here are the files:");
      mockGetMessageGroups.mockReturnValue([
        createPresentFilesGroup("g1", msg),
      ]);
      mockHasPresentFiles.mockReturnValue(true);
      mockHasContent.mockReturnValue(true);
      mockExtractContentFromMessage.mockReturnValue("Here are the files:");
      mockExtractPresentFilesFromMessage.mockReturnValue([]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
        />,
      );
      expect(screen.getByTestId("markdown-content")).toBeInTheDocument();
      expect(
        screen.getByTestId("markdown-content").getAttribute("data-content"),
      ).toBe("Here are the files:");
    });

    test("does not render MarkdownContent when first message has no content", () => {
      const msg = createAIMessage("pf-1");
      mockGetMessageGroups.mockReturnValue([
        createPresentFilesGroup("g1", msg),
      ]);
      mockHasPresentFiles.mockReturnValue(true);
      mockHasContent.mockReturnValue(false);
      mockExtractPresentFilesFromMessage.mockReturnValue([]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
        />,
      );
      expect(screen.queryByTestId("markdown-content")).not.toBeInTheDocument();
    });

    test("aggregates files from multiple messages", () => {
      const msg1 = createAIMessage("pf-1");
      const msg2 = createAIMessage("pf-2");
      mockGetMessageGroups.mockReturnValue([
        createPresentFilesGroup("g1", msg1, msg2),
      ]);
      mockHasPresentFiles.mockReturnValue(true);
      mockExtractPresentFilesFromMessage
        .mockReturnValueOnce(["a.pdf"])
        .mockReturnValueOnce(["b.xlsx"]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg1, msg2] })}
        />,
      );
      const fileList = screen.getByTestId("artifact-file-list");
      expect(fileList.getAttribute("data-files")).toBe(
        JSON.stringify(["a.pdf", "b.xlsx"]),
      );
    });
  });

  // ========================================================================
  // assistant:subagent groups
  // ========================================================================
  describe("assistant:subagent groups", () => {
    test("creates subtask for each task tool call and calls updateSubtask", () => {
      const updateSubtask = vi.fn();
      mockUseUpdateSubtask.mockReturnValue(updateSubtask);

      const taskCall = createTaskToolCall(
        "task-1",
        "researcher",
        "Do research",
        "Research prompt",
      );
      const aiMsg = createAIMessage("sub-ai-1", "", [taskCall]);
      const toolMsg = createToolMessage(
        "sub-tool-1",
        "task-1",
        "Task Succeeded. Result: done",
      );

      mockGetMessageGroups.mockReturnValue([
        createSubagentGroup("g1", aiMsg, toolMsg),
      ]);
      mockExtractTextFromMessage.mockReturnValue(
        "Task Succeeded. Result: done",
      );
      mockParseSubtaskResult.mockReturnValue({
        status: "completed",
        result: "done",
      });

      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [aiMsg, toolMsg] })}
        />,
      );

      // Verify updateSubtask was called with the subtask
      expect(updateSubtask).toHaveBeenCalledWith({
        id: "task-1",
        subagent_type: "researcher",
        description: "Do research",
        prompt: "Research prompt",
        status: "in_progress",
      });

      // Verify updateSubtask was called with parsed result
      expect(updateSubtask).toHaveBeenCalledWith({
        id: "task-1",
        status: "completed",
        result: "done",
      });
    });

    test("renders 'executing N tasks' message when tasks exist", () => {
      const taskCall = createTaskToolCall("task-1");
      const aiMsg = createAIMessage("sub-ai-1", "", [taskCall]);
      mockGetMessageGroups.mockReturnValue([createSubagentGroup("g1", aiMsg)]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [aiMsg] })}
        />,
      );
      expect(screen.getByText("Executing 1 tasks")).toBeInTheDocument();
    });

    test("shows correct count for multiple tasks", () => {
      const taskCall1 = createTaskToolCall("task-1");
      const taskCall2 = createTaskToolCall("task-2");
      const aiMsg = createAIMessage("sub-ai-1", "", [taskCall1, taskCall2]);
      mockGetMessageGroups.mockReturnValue([createSubagentGroup("g1", aiMsg)]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [aiMsg] })}
        />,
      );
      expect(screen.getByText("Executing 2 tasks")).toBeInTheDocument();
    });

    test("renders SubtaskCard for each task tool call", () => {
      const taskCall1 = createTaskToolCall("task-1");
      const taskCall2 = createTaskToolCall("task-2");
      const aiMsg = createAIMessage("sub-ai-1", "", [taskCall1, taskCall2]);
      mockGetMessageGroups.mockReturnValue([createSubagentGroup("g1", aiMsg)]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [aiMsg] })}
        />,
      );
      const cards = screen.getAllByTestId("subtask-card");
      expect(cards).toHaveLength(2);
      expect(cards[0]!.getAttribute("data-task-id")).toBe("task-1");
      expect(cards[1]!.getAttribute("data-task-id")).toBe("task-2");
    });

    test("passes isLoading to SubtaskCard", () => {
      const taskCall = createTaskToolCall("task-1");
      const aiMsg = createAIMessage("sub-ai-1", "", [taskCall]);
      mockGetMessageGroups.mockReturnValue([createSubagentGroup("g1", aiMsg)]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ isLoading: true, messages: [aiMsg] })}
        />,
      );
      expect(
        screen.getByTestId("subtask-card").getAttribute("data-is-loading"),
      ).toBe("true");
    });

    test("renders MessageGroup for AI messages with reasoning", () => {
      const aiMsg = createAIMessage("sub-reason-1", "thinking...");
      mockGetMessageGroups.mockReturnValue([createSubagentGroup("g1", aiMsg)]);
      mockHasReasoning.mockReturnValue(true);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [aiMsg] })}
        />,
      );
      expect(screen.getByTestId("message-group")).toBeInTheDocument();
    });

    test("does not render MessageGroup for AI messages without reasoning", () => {
      const taskCall = createTaskToolCall("task-1");
      const aiMsg = createAIMessage("sub-ai-1", "", [taskCall]);
      mockGetMessageGroups.mockReturnValue([createSubagentGroup("g1", aiMsg)]);
      mockHasReasoning.mockReturnValue(false);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [aiMsg] })}
        />,
      );
      expect(screen.queryByTestId("message-group")).not.toBeInTheDocument();
    });

    test("collects debug message IDs for non-reasoning AI messages", () => {
      const aiMsg = createAIMessage("debug-ai-1", "");
      mockGetMessageGroups.mockReturnValue([createSubagentGroup("g1", aiMsg)]);
      mockHasReasoning.mockReturnValue(false);
      mockBuildTokenDebugSteps.mockReturnValue([
        {
          id: "step-1",
          messageId: "debug-ai-1",
          label: "Step 1",
          secondaryLabels: [],
          usage: null,
          sharedAttribution: false,
        },
      ]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [aiMsg] })}
          tokenUsageInlineMode="step_debug"
        />,
      );
      expect(screen.getByTestId("token-usage-debug")).toBeInTheDocument();
      expect(
        screen.getByTestId("token-usage-debug").getAttribute("data-step-count"),
      ).toBe("1");
    });

    test("does not create subtask for non-task tool calls", () => {
      const updateSubtask = vi.fn();
      mockUseUpdateSubtask.mockReturnValue(updateSubtask);

      const otherToolCall = {
        name: "search",
        id: "s-1",
        args: { query: "test" },
      };
      const aiMsg = createAIMessage("sub-ai-1", "", [otherToolCall]);
      mockGetMessageGroups.mockReturnValue([createSubagentGroup("g1", aiMsg)]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [aiMsg] })}
        />,
      );

      // updateSubtask should not be called with task data
      const taskCalls = updateSubtask.mock.calls.filter(
        (call: any) => call[0]?.subagent_type,
      );
      expect(taskCalls).toHaveLength(0);
    });

    test("handles tool message without tool_call_id gracefully", () => {
      const updateSubtask = vi.fn();
      mockUseUpdateSubtask.mockReturnValue(updateSubtask);

      // Tool message without tool_call_id
      const toolMsg = { type: "tool", id: "t-1", content: "done" } as any;
      const aiMsg = createAIMessage("sub-ai-1", "");
      mockGetMessageGroups.mockReturnValue([
        createSubagentGroup("g1", aiMsg, toolMsg),
      ]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [aiMsg, toolMsg] })}
        />,
      );

      // parseSubtaskResult should not be called since tool_call_id is missing
      expect(mockParseSubtaskResult).not.toHaveBeenCalled();
    });

    test("renders multiple groups with different types correctly", () => {
      const humanMsg = createHumanMessage("h1", "Question");
      const aiMsg = createAIMessage("a1", "Answer");
      const subAiMsg = createAIMessage("s1", "", [createTaskToolCall("t1")]);
      mockGetMessageGroups.mockReturnValue([
        createHumanGroup("g1", humanMsg),
        createAssistantGroup("g2", aiMsg),
        createSubagentGroup("g3", subAiMsg),
      ]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [humanMsg, aiMsg, subAiMsg] })}
        />,
      );
      const items = screen.getAllByTestId("message-list-item");
      expect(items).toHaveLength(2); // human + assistant messages
      expect(screen.getByText("Executing 1 tasks")).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Default / fallback groups (assistant:processing)
  // ========================================================================
  describe("default groups (assistant:processing)", () => {
    test("renders MessageGroup with messages", () => {
      const msg = createAIMessage("proc-1", "processing...");
      mockGetMessageGroups.mockReturnValue([createDefaultGroup("g1", msg)]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
        />,
      );
      expect(screen.getByTestId("message-group")).toBeInTheDocument();
      expect(
        screen.getByTestId("message-group").getAttribute("data-count"),
      ).toBe("1");
    });

    test("passes isLoading to MessageGroup", () => {
      const msg = createAIMessage("proc-1");
      mockGetMessageGroups.mockReturnValue([createDefaultGroup("g1", msg)]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ isLoading: true, messages: [msg] })}
        />,
      );
      expect(
        screen.getByTestId("message-group").getAttribute("data-is-loading"),
      ).toBe("true");
    });

    test("passes filtered tokenDebugSteps to MessageGroup", () => {
      const msg1 = createAIMessage("proc-1");
      const msg2 = createAIMessage("proc-2");
      mockGetMessageGroups.mockReturnValue([
        createDefaultGroup("g1", msg1, msg2),
      ]);
      mockBuildTokenDebugSteps.mockReturnValue([
        {
          id: "s1",
          messageId: "proc-1",
          label: "Step 1",
          secondaryLabels: [],
          usage: null,
          sharedAttribution: false,
        },
        {
          id: "s2",
          messageId: "proc-2",
          label: "Step 2",
          secondaryLabels: [],
          usage: null,
          sharedAttribution: false,
        },
        {
          id: "s3",
          messageId: "other-id",
          label: "Step 3",
          secondaryLabels: [],
          usage: null,
          sharedAttribution: false,
        },
      ]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg1, msg2] })}
        />,
      );
      expect(
        screen
          .getByTestId("message-group")
          .getAttribute("data-debug-step-count"),
      ).toBe("2");
    });

    test("passes showTokenDebugSummaries=true when mode is step_debug", () => {
      const msg = createAIMessage("proc-1");
      mockGetMessageGroups.mockReturnValue([createDefaultGroup("g1", msg)]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
          tokenUsageInlineMode="step_debug"
        />,
      );
      expect(
        screen
          .getByTestId("message-group")
          .getAttribute("data-show-debug-summaries"),
      ).toBe("true");
    });

    test("passes showTokenDebugSummaries=false when mode is not step_debug", () => {
      const msg = createAIMessage("proc-1");
      mockGetMessageGroups.mockReturnValue([createDefaultGroup("g1", msg)]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
          tokenUsageInlineMode="per_turn"
        />,
      );
      expect(
        screen
          .getByTestId("message-group")
          .getAttribute("data-show-debug-summaries"),
      ).toBe("false");
    });

    test("does not render token usage list for default groups with step_debug (inlineDebug=false)", () => {
      const msg = createAIMessage("proc-1");
      mockGetMessageGroups.mockReturnValue([createDefaultGroup("g1", msg)]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
          tokenUsageInlineMode="step_debug"
        />,
      );
      expect(screen.queryByTestId("token-usage-debug")).not.toBeInTheDocument();
      expect(screen.queryByTestId("token-usage-list")).not.toBeInTheDocument();
    });
  });

  // ========================================================================
  // Token usage rendering
  // ========================================================================
  describe("token usage rendering", () => {
    test("renders nothing in off mode", () => {
      const msg = createAIMessage("a1", "text");
      mockGetMessageGroups.mockReturnValue([createAssistantGroup("g1", msg)]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
          tokenUsageInlineMode="off"
        />,
      );
      expect(screen.queryByTestId("token-usage-list")).not.toBeInTheDocument();
      expect(screen.queryByTestId("token-usage-debug")).not.toBeInTheDocument();
    });

    test("renders MessageTokenUsageList in per_turn mode", () => {
      const msg = createAIMessage("a1", "text");
      mockGetMessageGroups.mockReturnValue([createAssistantGroup("g1", msg)]);
      mockGetAssistantTurnUsageMessages.mockReturnValue([[msg]]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
          tokenUsageInlineMode="per_turn"
        />,
      );
      expect(screen.getByTestId("token-usage-list")).toBeInTheDocument();
      expect(
        screen.getByTestId("token-usage-list").getAttribute("data-enabled"),
      ).toBe("true");
      expect(
        screen
          .getByTestId("token-usage-list")
          .getAttribute("data-message-count"),
      ).toBe("1");
    });

    test("renders MessageTokenUsageDebugList in step_debug mode for human/assistant groups", () => {
      const msg = createAIMessage("a1", "text");
      mockGetMessageGroups.mockReturnValue([createAssistantGroup("g1", msg)]);
      mockBuildTokenDebugSteps.mockReturnValue([
        {
          id: "s1",
          messageId: "a1",
          label: "Step 1",
          secondaryLabels: [],
          usage: null,
          sharedAttribution: false,
        },
      ]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
          tokenUsageInlineMode="step_debug"
        />,
      );
      expect(screen.getByTestId("token-usage-debug")).toBeInTheDocument();
      expect(
        screen.getByTestId("token-usage-debug").getAttribute("data-step-count"),
      ).toBe("1");
    });

    test("filters token debug steps by message IDs in step_debug mode", () => {
      const msg = createAIMessage("a1", "text");
      mockGetMessageGroups.mockReturnValue([createAssistantGroup("g1", msg)]);
      mockBuildTokenDebugSteps.mockReturnValue([
        {
          id: "s1",
          messageId: "a1",
          label: "Step 1",
          secondaryLabels: [],
          usage: null,
          sharedAttribution: false,
        },
        {
          id: "s2",
          messageId: "other",
          label: "Step 2",
          secondaryLabels: [],
          usage: null,
          sharedAttribution: false,
        },
      ]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
          tokenUsageInlineMode="step_debug"
        />,
      );
      expect(
        screen.getByTestId("token-usage-debug").getAttribute("data-step-count"),
      ).toBe("1");
    });

    test("passes turnUsageMessages to MessageTokenUsageList", () => {
      const msg = createAIMessage("a1", "text");
      const usageMsg = createAIMessage("a2", "usage data");
      mockGetMessageGroups.mockReturnValue([createAssistantGroup("g1", msg)]);
      mockGetAssistantTurnUsageMessages.mockReturnValue([[usageMsg]]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
          tokenUsageInlineMode="per_turn"
        />,
      );
      expect(
        screen
          .getByTestId("token-usage-list")
          .getAttribute("data-message-count"),
      ).toBe("1");
    });

    test("per_turn mode with missing turnUsageMessages falls back to empty array", () => {
      const msg = createAIMessage("a1", "text");
      mockGetMessageGroups.mockReturnValue([createAssistantGroup("g1", msg)]);
      // Default mock returns [] so turnUsageMessagesByGroupIndex[0] is undefined.
      // The ?? [] fallback in renderTokenUsage should produce an empty messages array.
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
          tokenUsageInlineMode="per_turn"
        />,
      );
      expect(screen.getByTestId("token-usage-list")).toBeInTheDocument();
      expect(
        screen
          .getByTestId("token-usage-list")
          .getAttribute("data-message-count"),
      ).toBe("0");
    });
  });

  // ========================================================================
  // History loading (LoadMoreHistoryIndicator)
  // ========================================================================
  describe("history loading", () => {
    test("renders nothing when hasMoreHistory and isHistoryLoading are both undefined", () => {
      render(<MessageList threadId="t1" thread={createThread()} />);
      expect(
        screen.queryByRole("button", { name: /load more/i }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /loading/i }),
      ).not.toBeInTheDocument();
    });

    test("shows loading state with spinner when isHistoryLoading is true", () => {
      render(
        <MessageList
          threadId="t1"
          thread={createThread()}
          isHistoryLoading={true}
          hasMoreHistory={true}
        />,
      );
      expect(screen.getByTestId("loader-icon")).toBeInTheDocument();
      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });

    test("shows load more button when hasMoreHistory is true", () => {
      render(
        <MessageList
          threadId="t1"
          thread={createThread()}
          hasMoreHistory={true}
          isHistoryLoading={false}
        />,
      );
      expect(screen.getByTestId("chevron-icon")).toBeInTheDocument();
      expect(screen.getByText("Load More")).toBeInTheDocument();
    });

    test("button is disabled when isHistoryLoading is true", () => {
      render(
        <MessageList
          threadId="t1"
          thread={createThread()}
          isHistoryLoading={true}
          hasMoreHistory={true}
        />,
      );
      const button = screen.getByRole("button", { name: /loading/i });
      expect(button).toBeDisabled();
    });

    test("calls loadMoreHistory on button click", () => {
      const loadMore = vi.fn();
      render(
        <MessageList
          threadId="t1"
          thread={createThread()}
          hasMoreHistory={true}
          loadMoreHistory={loadMore}
        />,
      );
      const button = screen.getByRole("button", { name: /load more/i });
      fireEvent.click(button);
      expect(loadMore).toHaveBeenCalledTimes(1);
    });

    test("does not call loadMoreHistory when hasMoreHistory is false", () => {
      const loadMore = vi.fn();
      render(
        <MessageList
          threadId="t1"
          thread={createThread()}
          hasMoreHistory={false}
          loadMoreHistory={loadMore}
        />,
      );
      expect(
        screen.queryByRole("button", { name: /load more/i }),
      ).not.toBeInTheDocument();
    });

    test("throttles rapid clicks", () => {
      vi.useFakeTimers();
      const loadMore = vi.fn();
      render(
        <MessageList
          threadId="t1"
          thread={createThread()}
          hasMoreHistory={true}
          loadMoreHistory={loadMore}
        />,
      );
      const button = screen.getByRole("button", { name: /load more/i });

      // First click should go through immediately
      fireEvent.click(button);
      expect(loadMore).toHaveBeenCalledTimes(1);

      // Second click within throttle window should be throttled
      fireEvent.click(button);
      expect(loadMore).toHaveBeenCalledTimes(1);

      // After throttle period, click should work again
      act(() => {
        vi.advanceTimersByTime(1300);
      });
      fireEvent.click(button);
      expect(loadMore).toHaveBeenCalledTimes(2);

      vi.useRealTimers();
    });

    test("IntersectionObserver triggers loadMoreHistory when sentinel enters viewport", () => {
      const loadMore = vi.fn();
      render(
        <MessageList
          threadId="t1"
          thread={createThread()}
          hasMoreHistory={true}
          loadMoreHistory={loadMore}
        />,
      );

      // Observer should have been set up
      expect(mockObserve).toHaveBeenCalled();

      // Simulate the sentinel element becoming visible
      act(() => {
        intersectionCallback?.([{ isIntersecting: true }]);
      });

      expect(loadMore).toHaveBeenCalledTimes(1);
    });

    test("IntersectionObserver does not trigger loadMoreHistory when entry is not intersecting", () => {
      const loadMore = vi.fn();
      render(
        <MessageList
          threadId="t1"
          thread={createThread()}
          hasMoreHistory={true}
          loadMoreHistory={loadMore}
        />,
      );

      act(() => {
        intersectionCallback?.([{ isIntersecting: false }]);
      });

      expect(loadMore).not.toHaveBeenCalled();
    });

    test("IntersectionObserver is not set up when hasMoreHistory is false even while loading", () => {
      render(
        <MessageList
          threadId="t1"
          thread={createThread()}
          hasMoreHistory={false}
          isHistoryLoading={true}
        />,
      );

      // The loading indicator is rendered
      expect(screen.getByText("Loading...")).toBeInTheDocument();
      // But the observer should NOT be created because hasMore is false
      expect(mockObserve).not.toHaveBeenCalled();
    });

    test("throttledLoadMore returns early when a timeout is already pending", () => {
      vi.useFakeTimers();
      const loadMore = vi.fn();
      render(
        <MessageList
          threadId="t1"
          thread={createThread()}
          hasMoreHistory={true}
          loadMoreHistory={loadMore}
        />,
      );
      const button = screen.getByRole("button", { name: /load more/i });

      // First click → fires immediately (remaining <= 0 because Date.now() >> lastLoadRef=0)
      fireEvent.click(button);
      expect(loadMore).toHaveBeenCalledTimes(1);

      // Second click → remaining > 0, no pending timeout → sets timer
      fireEvent.click(button);
      expect(loadMore).toHaveBeenCalledTimes(1);

      // Third click → timeoutRef.current is set → early return (does NOT call loadMore)
      fireEvent.click(button);
      expect(loadMore).toHaveBeenCalledTimes(1);

      // Timer from second click fires
      act(() => {
        vi.advanceTimersByTime(1300);
      });
      expect(loadMore).toHaveBeenCalledTimes(2);

      vi.useRealTimers();
    });

    test("cleanup clears pending timeout on unmount", () => {
      vi.useFakeTimers();
      const loadMore = vi.fn();
      const { unmount } = render(
        <MessageList
          threadId="t1"
          thread={createThread()}
          hasMoreHistory={true}
          loadMoreHistory={loadMore}
        />,
      );
      const button = screen.getByRole("button", { name: /load more/i });

      // First click → fires immediately
      fireEvent.click(button);
      expect(loadMore).toHaveBeenCalledTimes(1);

      // Second click → sets a throttle timeout
      fireEvent.click(button);

      // Unmount before the timeout fires
      unmount();

      // Advance timer — the timeout should have been cleared on unmount
      act(() => {
        vi.advanceTimersByTime(1300);
      });
      expect(loadMore).toHaveBeenCalledTimes(1);

      vi.useRealTimers();
    });
  });

  // ========================================================================
  // Edge cases
  // ========================================================================
  describe("edge cases", () => {
    test("handles empty message groups gracefully", () => {
      mockGetMessageGroups.mockReturnValue([]);
      render(<MessageList threadId="t1" thread={createThread()} />);
      expect(screen.getByTestId("conversation")).toBeInTheDocument();
      expect(screen.queryByTestId("message-list-item")).not.toBeInTheDocument();
    });

    test("handles multiple groups of different types", () => {
      const humanMsg = createHumanMessage("h1", "Question");
      const aiMsg = createAIMessage("a1", "Answer");
      const clarMsg = createAIMessage("cl1", "Clarify?");
      mockGetMessageGroups.mockReturnValue([
        createHumanGroup("g1", humanMsg),
        createAssistantGroup("g2", aiMsg),
        createClarificationGroup("g3", clarMsg),
      ]);
      mockHasContent.mockReturnValue(true);
      mockExtractContentFromMessage.mockReturnValue("Clarify?");
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [humanMsg, aiMsg, clarMsg] })}
        />,
      );
      const items = screen.getAllByTestId("message-list-item");
      expect(items).toHaveLength(2);
      expect(screen.getByTestId("markdown-content")).toBeInTheDocument();
    });

    test("renders nothing when clarification group has empty messages array", () => {
      mockGetMessageGroups.mockReturnValue([
        { type: "assistant:clarification", id: "g1", messages: [] },
      ]);
      render(<MessageList threadId="t1" thread={createThread()} />);
      expect(screen.queryByTestId("markdown-content")).not.toBeInTheDocument();
      expect(screen.queryByTestId("message-list-item")).not.toBeInTheDocument();
    });

    test("handles present-files group with no files extracted", () => {
      const msg = createAIMessage("pf-1");
      mockGetMessageGroups.mockReturnValue([
        createPresentFilesGroup("g1", msg),
      ]);
      mockHasPresentFiles.mockReturnValue(false);
      mockHasContent.mockReturnValue(false);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
        />,
      );
      expect(screen.getByTestId("artifact-file-list")).toBeInTheDocument();
      expect(
        screen.getByTestId("artifact-file-list").getAttribute("data-files"),
      ).toBe("[]");
    });

    test("handles subagent group with AI messages having no tool calls", () => {
      const aiMsg = createAIMessage("sub-1", "Some text");
      mockGetMessageGroups.mockReturnValue([createSubagentGroup("g1", aiMsg)]);
      mockHasReasoning.mockReturnValue(false);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [aiMsg] })}
        />,
      );
      expect(screen.queryByTestId("subtask-card")).not.toBeInTheDocument();
      expect(screen.queryByText(/Executing/)).not.toBeInTheDocument();
    });

    test("handles thread with isThreadLoading true and non-empty messages", () => {
      const msg = createHumanMessage("h1", "Hello");
      mockGetMessageGroups.mockReturnValue([createHumanGroup("g1", msg)]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ isThreadLoading: true, messages: [msg] })}
        />,
      );
      expect(screen.queryByTestId("skeleton")).not.toBeInTheDocument();
      expect(screen.getByTestId("conversation")).toBeInTheDocument();
      expect(screen.getByTestId("message-list-item")).toBeInTheDocument();
    });

    test("renders groups with unknown/fallback type using MessageGroup", () => {
      const msg = createAIMessage("unk-1", "content");
      mockGetMessageGroups.mockReturnValue([
        { type: "some-unknown-type", id: "g1", messages: [msg] },
      ]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
        />,
      );
      expect(screen.getByTestId("message-group")).toBeInTheDocument();
    });

    test("passes correct props to renderTokenUsage for present-files groups", () => {
      const msg = createAIMessage("pf-1");
      mockGetMessageGroups.mockReturnValue([
        createPresentFilesGroup("g1", msg),
      ]);
      mockHasPresentFiles.mockReturnValue(true);
      mockExtractPresentFilesFromMessage.mockReturnValue([]);
      mockGetAssistantTurnUsageMessages.mockReturnValue([[msg]]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [msg] })}
          tokenUsageInlineMode="per_turn"
        />,
      );
      expect(screen.getByTestId("token-usage-list")).toBeInTheDocument();
    });

    test("passes debugMessageIds for subagent groups in step_debug mode", () => {
      const aiMsg = createAIMessage("sub-debug-1", "");
      mockGetMessageGroups.mockReturnValue([createSubagentGroup("g1", aiMsg)]);
      mockHasReasoning.mockReturnValue(false);
      mockBuildTokenDebugSteps.mockReturnValue([
        {
          id: "sd-1",
          messageId: "sub-debug-1",
          label: "Sub Step",
          secondaryLabels: [],
          usage: null,
          sharedAttribution: false,
        },
      ]);
      render(
        <MessageList
          threadId="t1"
          thread={createThread({ messages: [aiMsg] })}
          tokenUsageInlineMode="step_debug"
        />,
      );
      expect(screen.getByTestId("token-usage-debug")).toBeInTheDocument();
      expect(
        screen.getByTestId("token-usage-debug").getAttribute("data-step-count"),
      ).toBe("1");
    });
  });
});
