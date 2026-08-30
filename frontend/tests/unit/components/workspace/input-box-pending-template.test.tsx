import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks -- must be declared before the component import
// ---------------------------------------------------------------------------

const mockSetInput = vi.fn();
const mockTextInputValue = { current: "" };

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    changeLocale: vi.fn(),
    t: {
      common: { close: "Close", cancel: "Cancel", create: "Create" },
      inputBox: {
        placeholder: "How can I assist you today?",
        addAttachments: "Add attachments",
        mode: "Mode",
        flashMode: "Flash",
        flashModeDescription: "Fast and efficient",
        reasoningMode: "Reasoning",
        reasoningModeDescription: "Reasoning before action",
        proMode: "Pro",
        proModeDescription: "Reasoning, planning and executing",
        ultraMode: "Ultra",
        ultraModeDescription: "Pro mode with subagents",
        reasoningEffort: "Reasoning Effort",
        reasoningEffortMinimal: "Minimal",
        reasoningEffortMinimalDescription: "Retrieval + Direct Output",
        reasoningEffortLow: "Low",
        reasoningEffortLowDescription: "Simple Logic Check",
        reasoningEffortMedium: "Medium",
        reasoningEffortMediumDescription: "Multi-layer Logic Analysis",
        reasoningEffortHigh: "High",
        reasoningEffortHighDescription: "Full-dimensional Logic Deduction",
        searchModels: "Search models...",
        surpriseMe: "Surprise",
        surpriseMePrompt: "Surprise me",
        followupLoading: "Generating follow-up questions...",
        followupConfirmTitle: "Send suggestion?",
        followupConfirmDescription: "You already have text in the input.",
        followupConfirmAppend: "Append & send",
        followupConfirmReplace: "Replace & send",
        suggestions: [],
        suggestionsCreate: [],
      },
    },
  }),
}));

vi.mock("@/core/models/hooks", () => ({
  useModels: vi.fn(),
}));

vi.mock("@/components/workspace/messages/context", () => ({
  useThread: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: vi.fn(),
}));

vi.mock("@/core/api/fetcher", () => ({
  fetch: vi.fn(),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: () => "http://localhost:8000",
}));

vi.mock("@/core/threads/utils", () => ({
  textOfMessage: vi.fn((m: { content?: string }) => m.content ?? ""),
}));

vi.mock("@/components/ai-elements/model-selector", () => ({
  ModelSelector: ({ children, ...props }: any) => (
    <div data-testid="model-selector" {...props}>
      {children}
    </div>
  ),
  ModelSelectorTrigger: ({ children, ...props }: any) => (
    <div data-testid="model-selector-trigger" {...props}>
      {children}
    </div>
  ),
  ModelSelectorContent: ({ children }: any) => <div>{children}</div>,
  ModelSelectorInput: (props: any) => <input {...props} />,
  ModelSelectorList: ({ children }: any) => <div>{children}</div>,
  ModelSelectorItem: ({ children, onSelect, ...props }: any) => (
    <button
      data-testid={`model-item-${props.value}`}
      onClick={onSelect}
      {...props}
    >
      {children}
    </button>
  ),
  ModelSelectorName: ({ children, ...props }: any) => (
    <span {...props}>{children}</span>
  ),
}));

vi.mock("@/components/ai-elements/suggestion", () => ({
  Suggestion: ({ suggestion, onClick, ...props }: any) => (
    <button data-testid="suggestion" onClick={onClick} {...props}>
      {suggestion}
    </button>
  ),
  Suggestions: ({ children, ...props }: any) => (
    <div data-testid="suggestions" {...props}>
      {children}
    </div>
  ),
}));

vi.mock("@/components/ui/confetti-button", () => ({
  ConfettiButton: ({ children, onClick, ...props }: any) => (
    <button data-testid="confetti-button" onClick={onClick} {...props}>
      {children}
    </button>
  ),
}));

vi.mock("@/components/workspace/mode-hover-guide", () => ({
  ModeHoverGuide: ({ children }: any) => (
    <div data-testid="mode-hover-guide">{children}</div>
  ),
}));

vi.mock("@/components/workspace/tooltip", () => ({
  Tooltip: ({ children, content }: any) => (
    <div
      data-testid="tooltip"
      title={typeof content === "string" ? content : undefined}
    >
      {children}
    </div>
  ),
}));

vi.mock("@/core/skills/hooks", () => ({
  useSkills: () => ({
    skills: [],
    isLoading: false,
    error: null,
  }),
}));

let mockTextInputContext = {
  value: "",
  setInput: mockSetInput,
  clear: vi.fn(),
};

vi.mock("@/components/ai-elements/prompt-input", () => {
  return {
    usePromptInputController: () => ({
      textInput: mockTextInputContext,
      attachments: {
        files: [],
        add: vi.fn(),
        remove: vi.fn(),
        clear: vi.fn(),
        openFileDialog: vi.fn(),
        fileInputRef: { current: null },
      },
      __registerFileInput: vi.fn(),
    }),
    usePromptInputAttachments: () => ({
      files: [],
      add: vi.fn(),
      remove: vi.fn(),
      clear: vi.fn(),
      openFileDialog: vi.fn(),
      fileInputRef: { current: null },
    }),
    PromptInput: ({ children, onSubmit, className, ...props }: any) => (
      <form
        data-testid="prompt-input"
        className={className}
        onSubmit={(e: any) => {
          e.preventDefault();
          onSubmit?.({ text: mockTextInputContext.value, files: [] }, e);
        }}
        {...props}
      >
        {children}
      </form>
    ),
    PromptInputActionMenu: ({ children }: any) => <div>{children}</div>,
    PromptInputActionMenuContent: ({ children }: any) => <div>{children}</div>,
    PromptInputActionMenuItem: ({ children, onSelect, ...props }: any) => (
      <button onClick={onSelect} {...props}>
        {children}
      </button>
    ),
    PromptInputActionMenuTrigger: ({ children, ...props }: any) => (
      <button {...props}>{children}</button>
    ),
    PromptInputAttachment: () => <div />,
    PromptInputAttachments: ({ children }: any) => <div>{children}</div>,
    PromptInputBody: ({ children, ...props }: any) => (
      <div {...props}>{children}</div>
    ),
    PromptInputButton: ({ children, onClick, ...props }: any) => (
      <button onClick={onClick} {...props}>
        {children}
      </button>
    ),
    PromptInputFooter: ({ children, ...props }: any) => (
      <div {...props}>{children}</div>
    ),
    PromptInputSubmit: ({ status, disabled, ...props }: any) => (
      <button
        type="submit"
        disabled={disabled}
        data-testid="submit-button"
        aria-label={status === "streaming" ? "Stop" : "Submit"}
        {...props}
      />
    ),
    PromptInputTextarea: ({
      placeholder,
      defaultValue,
      disabled,
      ...props
    }: any) => (
      <textarea
        name="message"
        placeholder={placeholder}
        defaultValue={defaultValue}
        disabled={disabled}
        data-testid="chat-input"
        {...props}
      />
    ),
    PromptInputTools: ({ children, ...props }: any) => (
      <div {...props}>{children}</div>
    ),
  };
});

// ---------------------------------------------------------------------------
// Imports after mocks
// ---------------------------------------------------------------------------

import { InputBox } from "@/components/workspace/input-box";
import { useThread } from "@/components/workspace/messages/context";
import { fetch } from "@/core/api/fetcher";
import { useModels } from "@/core/models/hooks";
import { useSearchParams } from "next/navigation";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeModel(overrides: Record<string, any> = {}) {
  return {
    id: "model-1",
    name: "gpt-4o",
    model: "gpt-4o",
    display_name: "GPT-4o",
    supports_thinking: false,
    supports_reasoning_effort: false,
    ...overrides,
  };
}

function makeContext(overrides: Record<string, any> = {}) {
  return {
    model_name: "gpt-4o",
    mode: "flash" as const,
    reasoning_effort: "minimal" as const,
    ...overrides,
  };
}

function defaultProps(overrides: Record<string, any> = {}) {
  return {
    context: makeContext(),
    threadId: "thread-1",
    onSubmit: vi.fn(),
    onStop: vi.fn(),
    onContextChange: vi.fn(),
    onFollowupsVisibilityChange: vi.fn(),
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  mockTextInputContext = {
    value: "",
    setInput: mockSetInput,
    clear: vi.fn(),
  };
  (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
    models: [makeModel()],
  });
  (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
    thread: { messages: [], values: { todos: [] } },
    isMock: false,
  });
  (useSearchParams as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
    new URLSearchParams(),
  );
  (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
    ok: true,
    json: async () => ({ suggestions: [] }),
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

// ===========================================================================
// Tests
// ===========================================================================

describe("InputBox pendingTemplate", () => {
  it("pendingTemplate + empty input → setInput called", () => {
    mockTextInputContext.value = "";
    render(
      <InputBox
        {...defaultProps()}
        pendingTemplate="请帮我处理以下文档：[描述需求]"
        onPendingTemplateConsumed={vi.fn()}
      />,
    );

    expect(mockSetInput).toHaveBeenCalledWith("请帮我处理以下文档：[描述需求]");
  });

  it("pendingTemplate + empty input → onPendingTemplateConsumed called", () => {
    const onPendingTemplateConsumed = vi.fn();
    render(
      <InputBox
        {...defaultProps()}
        pendingTemplate="请帮我处理以下文档：[描述需求]"
        onPendingTemplateConsumed={onPendingTemplateConsumed}
      />,
    );

    expect(onPendingTemplateConsumed).toHaveBeenCalled();
  });

  it("pendingTemplate + empty input → setTimeout 50ms then setSelectionRange", () => {
    render(
      <InputBox
        {...defaultProps()}
        pendingTemplate="请帮我处理以下文档：[描述需求]"
        onPendingTemplateConsumed={vi.fn()}
      />,
    );

    act(() => {
      vi.advanceTimersByTime(50);
    });

    const textarea = document.querySelector("textarea[name='message']");
    expect(textarea).toBeTruthy();
  });

  it("pendingTemplate + non-empty input → replaces the current input", () => {
    mockTextInputContext.value = "existing text";

    render(
      <InputBox
        {...defaultProps()}
        pendingTemplate="请帮我处理以下文档：[描述需求]"
        onPendingTemplateConsumed={vi.fn()}
      />,
    );

    expect(mockSetInput).toHaveBeenCalledWith("请帮我处理以下文档：[描述需求]");
    expect(screen.queryByText("Send suggestion?")).not.toBeInTheDocument();
  });

  it("clears an injected template when the scenario changes", () => {
    const template = "请帮我处理以下文档：[描述需求]";
    const { rerender } = render(
      <InputBox
        {...defaultProps()}
        pendingTemplate={template}
        onPendingTemplateConsumed={vi.fn()}
        clearInjectedTemplateKey={0}
      />,
    );

    mockTextInputContext.value = template;
    rerender(
      <InputBox
        {...defaultProps()}
        onPendingTemplateConsumed={vi.fn()}
        clearInjectedTemplateKey={1}
      />,
    );

    expect(mockTextInputContext.clear).toHaveBeenCalled();
  });

  it("replaces a non-empty input and highlights the template placeholder", () => {
    mockTextInputContext.value = "existing text";
    render(
      <InputBox
        {...defaultProps()}
        pendingTemplate="请帮我处理以下文档：[描述需求]"
        onPendingTemplateConsumed={vi.fn()}
      />,
    );
    act(() => {
      vi.advanceTimersByTime(50);
    });

    const textarea = document.querySelector("textarea[name='message']");
    expect(textarea).toBeTruthy();
  });

  it("confirmReplace(followup) → requestFormSubmit called (regression)", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ suggestions: ["Followup suggestion"] }),
    });

    mockTextInputContext.value = "existing text";

    const thread = {
      thread: {
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
        values: { todos: [] },
      },
      isMock: false,
    };
    (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(thread);

    const { rerender } = render(
      <InputBox
        {...defaultProps()}
        status="streaming"
        context={makeContext({ model_name: "gpt-4o", mode: "flash" })}
      />,
    );

    rerender(
      <InputBox
        {...defaultProps()}
        status="ready"
        context={makeContext({ model_name: "gpt-4o", mode: "flash" })}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Followup suggestion")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Followup suggestion"));

    await waitFor(() => {
      expect(screen.getByText("Send suggestion?")).toBeInTheDocument();
    });

    const requestSubmitSpy = vi.spyOn(
      HTMLFormElement.prototype,
      "requestSubmit",
    );
    await user.click(screen.getByText("Replace & send"));

    // Followup replace path calls requestFormSubmit via setTimeout(0)
    act(() => {
      vi.advanceTimersByTime(0);
    });

    expect(requestSubmitSpy).toHaveBeenCalled();
    requestSubmitSpy.mockRestore();
  });

  it("pendingTemplate with multiple [] → highlight takes the last one", () => {
    render(
      <InputBox
        {...defaultProps()}
        pendingTemplate="请帮我[处理][以下文档]"
        onPendingTemplateConsumed={vi.fn()}
      />,
    );

    expect(mockSetInput).toHaveBeenCalledWith("请帮我[处理][以下文档]");

    act(() => {
      vi.advanceTimersByTime(50);
    });

    const textarea = document.querySelector<HTMLTextAreaElement>(
      "textarea[name='message']",
    );
    expect(textarea).toBeTruthy();
  });
});
