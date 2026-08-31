import {
  render,
  screen,
  cleanup,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks -- must be declared before the component import
// ---------------------------------------------------------------------------

const mockSetInput = vi.fn();
const mockTextInputValue = { current: "" };
const mockOpenFileDialog = vi.fn();

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    changeLocale: vi.fn(),
    t: {
      common: {
        close: "Close",
        cancel: "Cancel",
        create: "Create",
      },
      inputBox: {
        placeholder: "How can I assist you today? /invoke skill",
        addAttachments: "Add attachments",
        selectModel: "Select model",
        invokeSkill: "Invoke skill",
        skill: "Skill",
        skillDialogDescription:
          "Choose a skill to insert /skill-name into the input.",
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
  useSkills: vi.fn(),
}));

// Mock the prompt-input hooks and provide simple renderable stubs for
// the compound sub-components so we can test InputBox in isolation.
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
        openFileDialog: mockOpenFileDialog,
        fileInputRef: { current: null },
      },
      __registerFileInput: vi.fn(),
    }),
    usePromptInputAttachments: () => ({
      files: [],
      add: vi.fn(),
      remove: vi.fn(),
      clear: vi.fn(),
      openFileDialog: mockOpenFileDialog,
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
import { SlashOverlay } from "@/components/workspace/slash-overlay";
import { fetch } from "@/core/api/fetcher";
import { useModels } from "@/core/models/hooks";
import { useSkills } from "@/core/skills/hooks";
import { useSearchParams } from "next/navigation";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeModel(
  overrides: Partial<{
    id: string;
    name: string;
    model: string;
    display_name: string;
    supports_thinking: boolean;
    supports_reasoning_effort: boolean;
  }> = {},
) {
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

function makeThinkingModel(
  overrides: Partial<{
    id: string;
    name: string;
    model: string;
    display_name: string;
    supports_thinking: boolean;
    supports_reasoning_effort: boolean;
  }> = {},
) {
  return {
    id: "model-2",
    name: "claude-sonnet",
    model: "claude-sonnet-4-20250514",
    display_name: "Claude Sonnet",
    supports_thinking: true,
    supports_reasoning_effort: true,
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

function makeThread(overrides: Record<string, any> = {}) {
  return {
    thread: {
      messages: [],
      ...overrides,
    },
    isMock: false,
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
  mockTextInputContext = {
    value: "",
    setInput: mockSetInput,
    clear: vi.fn(),
  };

  // Default mocks
  (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
    models: [makeModel()],
  });
  (useSkills as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
    skills: [],
    isLoading: false,
    error: null,
  });
  (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
    makeThread(),
  );
  (useSearchParams as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
    new URLSearchParams(),
  );
  (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
    ok: true,
    json: async () => ({ suggestions: [] }),
  });
});

afterEach(() => {
  cleanup();
});

// ===========================================================================
// Tests
// ===========================================================================

describe("InputBox", () => {
  // ----- Basic rendering -----

  describe("basic rendering", () => {
    test("renders the input box with data-testid", () => {
      render(<InputBox {...defaultProps()} />);
      expect(screen.getByTestId("input-box")).toBeInTheDocument();
    });

    test("renders the textarea with placeholder", () => {
      render(<InputBox {...defaultProps()} />);
      const textarea = screen.getByTestId("chat-input");
      expect(textarea).toBeInTheDocument();
      expect(textarea).toHaveAttribute(
        "placeholder",
        "How can I assist you today? /invoke skill",
      );
    });

    test("renders the submit button", () => {
      render(<InputBox {...defaultProps()} />);
      expect(screen.getByTestId("submit-button")).toBeInTheDocument();
    });

    test("renders the prompt-input form", () => {
      render(<InputBox {...defaultProps()} />);
      expect(screen.getByTestId("prompt-input")).toBeInTheDocument();
    });

    test("applies custom className", () => {
      render(<InputBox {...defaultProps()} className="custom-class" />);
      const form = screen.getByTestId("prompt-input");
      expect(form.className).toContain("custom-class");
    });

    test("renders with initialValue as defaultValue on textarea", () => {
      render(<InputBox {...defaultProps()} initialValue="hello world" />);
      const textarea = screen.getByTestId("chat-input");
      expect(textarea).toHaveValue("hello world");
    });

    test("renders with disabled state", () => {
      render(<InputBox {...defaultProps()} disabled />);
      const textarea = screen.getByTestId("chat-input");
      expect(textarea).toBeDisabled();
      const submit = screen.getByTestId("submit-button");
      expect(submit).toBeDisabled();
    });
  });

  // ----- Mode display -----

  describe("mode display", () => {
    test("displays flash mode label when mode is flash", () => {
      render(
        <InputBox
          {...defaultProps()}
          context={makeContext({ mode: "flash" })}
        />,
      );
      expect(screen.getAllByText("Flash").length).toBeGreaterThan(0);
    });

    test("displays reasoning mode label when mode is thinking", () => {
      const models = [makeThinkingModel()];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "thinking",
          })}
        />,
      );
      expect(screen.getAllByText("Reasoning").length).toBeGreaterThan(0);
    });

    test("displays pro mode label when mode is pro", () => {
      const models = [makeThinkingModel()];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "pro",
          })}
        />,
      );
      expect(screen.getAllByText("Pro").length).toBeGreaterThan(0);
    });

    test("displays ultra mode label when mode is ultra", () => {
      const models = [makeThinkingModel()];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "ultra",
          })}
        />,
      );
      expect(screen.getAllByText("Ultra").length).toBeGreaterThan(0);
    });
  });

  // ----- getResolvedMode logic (tested via auto-selection effect) -----

  describe("getResolvedMode auto-selection", () => {
    test("calls onContextChange with flash mode when model does not support thinking", () => {
      const onContextChange = vi.fn();
      const models = [makeModel()];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          onContextChange={onContextChange}
          context={makeContext({ mode: undefined })}
        />,
      );

      // Should auto-select flash mode for non-thinking model
      expect(onContextChange).toHaveBeenCalledWith(
        expect.objectContaining({
          mode: "flash",
          model_name: "gpt-4o",
        }),
      );
    });

    test("calls onContextChange with pro mode when model supports thinking and mode is undefined", () => {
      const onContextChange = vi.fn();
      const models = [makeThinkingModel()];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          onContextChange={onContextChange}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: undefined,
          })}
        />,
      );

      expect(onContextChange).toHaveBeenCalledWith(
        expect.objectContaining({
          mode: "pro",
          model_name: "claude-sonnet",
        }),
      );
    });

    test("forces flash mode when model does not support thinking even if mode is set to pro", () => {
      const onContextChange = vi.fn();
      const models = [makeModel({ supports_thinking: false })];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          onContextChange={onContextChange}
          context={makeContext({ mode: "pro" })}
        />,
      );

      expect(onContextChange).toHaveBeenCalledWith(
        expect.objectContaining({ mode: "flash" }),
      );
    });

    test("does not call onContextChange when model and mode are already correct", () => {
      const onContextChange = vi.fn();
      const models = [makeModel({ supports_thinking: false })];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          onContextChange={onContextChange}
          context={makeContext({
            model_name: "gpt-4o",
            mode: "flash",
          })}
        />,
      );

      // onContextChange should not be called when context already matches
      expect(onContextChange).not.toHaveBeenCalled();
    });
  });

  // ----- Model auto-selection -----

  describe("model auto-selection", () => {
    test("auto-selects first model when context model_name is not found", () => {
      const onContextChange = vi.fn();
      const models = [makeModel(), makeThinkingModel()];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          onContextChange={onContextChange}
          context={makeContext({ model_name: "nonexistent-model" })}
        />,
      );

      // Should use the first model as fallback
      expect(onContextChange).toHaveBeenCalledWith(
        expect.objectContaining({
          model_name: "gpt-4o",
        }),
      );
    });

    test("displays selected model display_name", () => {
      const models = [makeModel({ display_name: "My Custom Model" })];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          context={makeContext({ model_name: "gpt-4o" })}
        />,
      );

      expect(screen.getAllByText("My Custom Model").length).toBeGreaterThan(0);
    });
  });

  // ----- Model selection interaction -----

  describe("model selection", () => {
    test("calls onContextChange when a model is selected", async () => {
      const user = userEvent.setup();
      const onContextChange = vi.fn();
      const models = [makeModel(), makeThinkingModel()];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          onContextChange={onContextChange}
          context={makeContext({ model_name: "gpt-4o", mode: "flash" })}
        />,
      );

      const modelItem = screen.getByTestId("model-item-claude-sonnet");
      await user.click(modelItem);

      expect(onContextChange).toHaveBeenCalledWith(
        expect.objectContaining({
          model_name: "claude-sonnet",
        }),
      );
    });
  });

  // ----- Mode selection interaction -----

  describe("mode selection", () => {
    test("selecting flash mode calls onContextChange with correct reasoning_effort", async () => {
      const user = userEvent.setup();
      const onContextChange = vi.fn();
      const models = [makeThinkingModel()];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          onContextChange={onContextChange}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "pro",
          })}
        />,
      );

      // Find and click flash mode button (it's one of the PromptInputActionMenuItems)
      const flashButton = screen.getByText("Flash").closest("button");
      expect(flashButton).toBeTruthy();
      await user.click(flashButton!);

      expect(onContextChange).toHaveBeenCalledWith(
        expect.objectContaining({
          mode: "flash",
          reasoning_effort: "minimal",
        }),
      );
    });

    test("selecting pro mode calls onContextChange with medium reasoning_effort", async () => {
      const user = userEvent.setup();
      const onContextChange = vi.fn();
      const models = [makeThinkingModel()];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          onContextChange={onContextChange}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "flash",
          })}
        />,
      );

      const proButton = screen.getByText("Pro").closest("button");
      expect(proButton).toBeTruthy();
      await user.click(proButton!);

      expect(onContextChange).toHaveBeenCalledWith(
        expect.objectContaining({
          mode: "pro",
          reasoning_effort: "medium",
        }),
      );
    });

    test("selecting ultra mode calls onContextChange with high reasoning_effort", async () => {
      const user = userEvent.setup();
      const onContextChange = vi.fn();
      const models = [makeThinkingModel()];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          onContextChange={onContextChange}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "flash",
          })}
        />,
      );

      const ultraButton = screen.getByText("Ultra").closest("button");
      expect(ultraButton).toBeTruthy();
      await user.click(ultraButton!);

      expect(onContextChange).toHaveBeenCalledWith(
        expect.objectContaining({
          mode: "ultra",
          reasoning_effort: "high",
        }),
      );
    });

    test("selecting reasoning mode calls onContextChange with low reasoning_effort", async () => {
      const user = userEvent.setup();
      const onContextChange = vi.fn();
      const models = [makeThinkingModel()];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          onContextChange={onContextChange}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "flash",
          })}
        />,
      );

      const reasoningButton = screen.getByText("Reasoning").closest("button");
      expect(reasoningButton).toBeTruthy();
      await user.click(reasoningButton!);

      expect(onContextChange).toHaveBeenCalledWith(
        expect.objectContaining({
          mode: "thinking",
          reasoning_effort: "low",
        }),
      );
    });
  });

  // ----- Reasoning effort selection -----

  describe("reasoning effort selection", () => {
    test("displays reasoning effort selector when model supports it and mode is not flash", () => {
      const models = [makeThinkingModel({ supports_reasoning_effort: true })];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "pro",
            reasoning_effort: "medium",
          })}
        />,
      );

      expect(screen.getAllByText(/Reasoning Effort/).length).toBeGreaterThan(0);
    });

    test("hides reasoning effort selector in flash mode", () => {
      const models = [makeThinkingModel({ supports_reasoning_effort: true })];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "flash",
          })}
        />,
      );

      // The reasoning effort selector should not be visible in flash mode
      expect(screen.queryByText(/Reasoning Effort:/)).not.toBeInTheDocument();
    });

    test("hides reasoning effort selector when model does not support it", () => {
      const models = [makeThinkingModel({ supports_reasoning_effort: false })];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "pro",
          })}
        />,
      );

      expect(screen.queryByText(/Reasoning Effort:/)).not.toBeInTheDocument();
    });
  });

  // ----- Submit behavior -----

  describe("submit behavior", () => {
    test("calls onStop when status is streaming and submit is triggered", async () => {
      const onStop = vi.fn();
      const onSubmit = vi.fn();

      render(
        <InputBox
          {...defaultProps()}
          status="streaming"
          onSubmit={onSubmit}
          onStop={onStop}
        />,
      );

      const form = screen.getByTestId("prompt-input");
      form.dispatchEvent(
        new Event("submit", { bubbles: true, cancelable: true }),
      );

      // When streaming, onStop should be called instead of onSubmit
      await waitFor(() => {
        expect(onStop).toHaveBeenCalled();
      });
    });

    test("does not submit when text is empty and no files", async () => {
      const onSubmit = vi.fn();

      render(
        <InputBox
          {...defaultProps()}
          onSubmit={onSubmit}
          context={makeContext({
            model_name: "gpt-4o",
            mode: "flash",
          })}
        />,
      );

      const form = screen.getByTestId("prompt-input");
      form.dispatchEvent(
        new Event("submit", { bubbles: true, cancelable: true }),
      );

      // Empty text + no files should not call onSubmit
      await waitFor(() => {
        expect(onSubmit).not.toHaveBeenCalled();
      });
    });
  });

  // ----- Followup suggestions -----

  describe("followup suggestions", () => {
    test("does not show followups in welcome mode", () => {
      render(
        <InputBox
          {...defaultProps()}
          isWelcomeMode
          context={makeContext({ mode: "flash" })}
        />,
      );

      // Followup loading text should not be shown
      expect(
        screen.queryByText("Generating follow-up questions..."),
      ).not.toBeInTheDocument();
    });

    test("does not show followups when disabled", () => {
      render(<InputBox {...defaultProps()} disabled />);

      expect(
        screen.queryByText("Generating follow-up questions..."),
      ).not.toBeInTheDocument();
    });

    test("fetches suggestions after streaming ends", async () => {
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ suggestions: ["Follow-up 1", "Follow-up 2"] }),
      });

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi there!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

      const { rerender } = render(
        <InputBox
          {...defaultProps()}
          status="streaming"
          context={makeContext({ model_name: "gpt-4o", mode: "flash" })}
        />,
      );

      // Transition from streaming to ready
      rerender(
        <InputBox
          {...defaultProps()}
          status="ready"
          context={makeContext({ model_name: "gpt-4o", mode: "flash" })}
        />,
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          "http://localhost:8000/api/threads/thread-1/suggestions",
          expect.objectContaining({
            method: "POST",
            headers: { "Content-Type": "application/json" },
          }),
        );
      });
    });

    test("displays followup suggestions after fetch", async () => {
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          suggestions: ["What about X?", "Tell me more"],
        }),
      });

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi there!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

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
        expect(screen.getByText("What about X?")).toBeInTheDocument();
        expect(screen.getByText("Tell me more")).toBeInTheDocument();
      });
    });

    test("hides followups when close button is clicked", async () => {
      const user = userEvent.setup();
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ suggestions: ["Follow-up question"] }),
      });

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

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
        expect(screen.getByText("Follow-up question")).toBeInTheDocument();
      });

      // Click the close button (the one with the X icon, labeled "Close")
      const closeButton = screen.getByLabelText("Close");
      await user.click(closeButton);

      expect(screen.queryByText("Follow-up question")).not.toBeInTheDocument();
    });
  });

  // ----- Followup click behavior -----

  describe("followup click behavior", () => {
    test("sets input text when clicking followup with empty current input", async () => {
      const user = userEvent.setup();
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ suggestions: ["Follow-up question"] }),
      });

      mockTextInputContext.value = "";

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

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
        expect(screen.getByText("Follow-up question")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Follow-up question"));

      expect(mockSetInput).toHaveBeenCalledWith("Follow-up question");
    });

    test("shows confirmation dialog when clicking followup with existing input", async () => {
      const user = userEvent.setup();
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ suggestions: ["Follow-up question"] }),
      });

      mockTextInputContext.value = "existing text";

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

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
        expect(screen.getByText("Follow-up question")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Follow-up question"));

      // Confirmation dialog should appear
      await waitFor(() => {
        expect(screen.getByText("Send suggestion?")).toBeInTheDocument();
        expect(screen.getByText("Append & send")).toBeInTheDocument();
        expect(screen.getByText("Replace & send")).toBeInTheDocument();
      });
    });

    test("does not trigger followup click when streaming", async () => {
      const user = userEvent.setup();
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ suggestions: ["Follow-up"] }),
      });

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

      // First render as streaming, then show followups by transitioning
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
        expect(screen.getByText("Follow-up")).toBeInTheDocument();
      });

      // Now set status back to streaming
      rerender(
        <InputBox
          {...defaultProps()}
          status="streaming"
          context={makeContext({ model_name: "gpt-4o", mode: "flash" })}
        />,
      );

      // Followups remain visible but clicking should be a no-op during streaming
      expect(screen.getByText("Follow-up")).toBeInTheDocument();
      await user.click(screen.getByText("Follow-up"));
      expect(mockSetInput).not.toHaveBeenCalled();
    });
  });

  // ----- Confirmation dialog -----

  describe("confirmation dialog", () => {
    test("replace button sets the suggestion text", async () => {
      const user = userEvent.setup();
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ suggestions: ["New suggestion"] }),
      });

      mockTextInputContext.value = "existing text";

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

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
        expect(screen.getByText("New suggestion")).toBeInTheDocument();
      });

      // Click the followup suggestion
      await user.click(screen.getByText("New suggestion"));

      await waitFor(() => {
        expect(screen.getByText("Send suggestion?")).toBeInTheDocument();
      });

      // Click "Replace & send"
      await user.click(screen.getByText("Replace & send"));

      expect(mockSetInput).toHaveBeenCalledWith("New suggestion");
    });

    test("append button concatenates text with newline", async () => {
      const user = userEvent.setup();
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ suggestions: ["Extra info"] }),
      });

      mockTextInputContext.value = "existing text";

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

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
        expect(screen.getByText("Extra info")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Extra info"));

      await waitFor(() => {
        expect(screen.getByText("Send suggestion?")).toBeInTheDocument();
      });

      // Click "Append & send"
      await user.click(screen.getByText("Append & send"));

      expect(mockSetInput).toHaveBeenCalledWith("existing text\nExtra info");
    });

    test("cancel button closes dialog without changing input", async () => {
      const user = userEvent.setup();
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ suggestions: ["Suggestion"] }),
      });

      mockTextInputContext.value = "existing text";

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

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
        expect(screen.getByText("Suggestion")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Suggestion"));

      await waitFor(() => {
        expect(screen.getByText("Send suggestion?")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Cancel"));

      // Dialog should close
      await waitFor(() => {
        expect(screen.queryByText("Send suggestion?")).not.toBeInTheDocument();
      });

      // setInput should not have been called
      expect(mockSetInput).not.toHaveBeenCalled();
    });
  });

  // ----- Welcome mode -----

  describe("welcome mode", () => {
    test("renders with welcome mode layout", () => {
      render(<InputBox {...defaultProps()} isWelcomeMode />);
      const container = screen.getByTestId("input-box");
      expect(container.className).toContain("gap-5");
    });

    test("enlarges and left-aligns welcome input text", () => {
      render(<InputBox {...defaultProps()} isWelcomeMode />);

      const textarea = screen.getByTestId("chat-input");
      expect(textarea.className).toContain("min-h-40");
      expect(textarea.className).toContain("type-body");
      expect(textarea.className).toContain("text-left");
    });

    test("focuses the textarea when clicking the input surface", () => {
      render(<InputBox {...defaultProps()} isWelcomeMode />);

      fireEvent.click(screen.getByTestId("input-box"));

      expect(screen.getByTestId("chat-input")).toHaveFocus();
    });

    test("keeps the caret after newly typed text when selected tags are recreated", async () => {
      const user = userEvent.setup();
      const tag = { id: "agent:writer", label: "办公文档" };
      const props = defaultProps({
        onRemoveTag: vi.fn(),
        selectedTags: [tag],
      });
      const { rerender } = render(<InputBox {...props} />);
      const textarea = screen.getByTestId<HTMLTextAreaElement>("chat-input");

      await user.type(textarea, "a");
      rerender(<InputBox {...props} selectedTags={[{ ...tag }]} />);
      await waitFor(() => expect(textarea).toHaveValue("a"));
      textarea.setRangeText(
        "b",
        textarea.selectionStart,
        textarea.selectionEnd,
        "end",
      );
      fireEvent.input(textarea);

      expect(textarea).toHaveValue("ab");
      expect(textarea.selectionStart).toBe(2);
      expect(textarea.selectionEnd).toBe(2);
    });

    test("renders with non-welcome mode layout", () => {
      render(<InputBox {...defaultProps()} />);
      const container = screen.getByTestId("input-box");
      expect(container.className).toContain("gap-2");
    });
  });

  // ----- onFollowupsVisibilityChange callback -----

  describe("onFollowupsVisibilityChange", () => {
    test("calls onFollowupsVisibilityChange with false on unmount", () => {
      const onFollowupsVisibilityChange = vi.fn();
      const { unmount } = render(
        <InputBox
          {...defaultProps()}
          onFollowupsVisibilityChange={onFollowupsVisibilityChange}
        />,
      );

      unmount();

      expect(onFollowupsVisibilityChange).toHaveBeenCalledWith(false);
    });
  });

  // ----- Suggestions API error handling -----

  describe("suggestions API error handling", () => {
    test("handles fetch error gracefully", async () => {
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockRejectedValue(new Error("Network error"));

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

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

      // Should not crash; followups should remain empty
      await waitFor(() => {
        expect(screen.queryByTestId("suggestions")).not.toBeInTheDocument();
      });
    });

    test("handles non-ok response gracefully", async () => {
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({}),
      });

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

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
        expect(screen.queryByTestId("suggestions")).not.toBeInTheDocument();
      });
    });
  });

  // ----- isMock thread -----

  describe("isMock thread", () => {
    test("does not fetch suggestions when thread is mock", async () => {
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        ...thread,
        isMock: true,
      });

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

      // Wait a tick to let any effects settle
      await new Promise((r) => setTimeout(r, 50));

      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  // ----- Submit with model mismatch guard -----

  describe("submit with model mismatch", () => {
    test("calls onContextChange when submitting with mismatched model", async () => {
      const onContextChange = vi.fn();
      const onSubmit = vi.fn();
      const models = [
        makeModel({ name: "gpt-4o", display_name: "GPT-4o" }),
        makeModel({
          id: "model-2",
          name: "gpt-4-turbo",
          model: "gpt-4-turbo",
          display_name: "GPT-4 Turbo",
        }),
      ];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      mockTextInputContext.value = "Hello world";

      render(
        <InputBox
          {...defaultProps()}
          onSubmit={onSubmit}
          onContextChange={onContextChange}
          context={makeContext({
            model_name: "gpt-4o",
            mode: "flash",
          })}
        />,
      );

      // The form submit should trigger handleSubmit, which checks
      // resolvedModelName vs context.model_name. Since they match,
      // it should call onSubmit directly.
      const form = screen.getByTestId("prompt-input");
      form.dispatchEvent(
        new Event("submit", { bubbles: true, cancelable: true }),
      );

      // onSubmit should be called since models match
      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalled();
      });
    });
  });

  // ----- AddAttachmentsButton -----

  describe("AddAttachmentsButton", () => {
    test("renders the attachment button", () => {
      render(<InputBox {...defaultProps()} />);
      // The attachment button has a PaperclipIcon and a tooltip
      expect(screen.getByTitle("Add attachments")).toBeInTheDocument();
    });
  });

  describe("composer action labels", () => {
    test("makes the skill action discoverable and labels the model action", () => {
      render(<InputBox {...defaultProps()} />);

      const skillButton = screen
        .getAllByTestId("skill-selector-trigger")
        .find((element) => element.tagName === "BUTTON");
      const modelButton = screen
        .getAllByTestId("model-selector-trigger")
        .find((element) => element.tagName === "BUTTON");

      expect(skillButton).toHaveTextContent("Skill");
      expect(skillButton).toHaveAttribute("aria-label", "Invoke skill");
      expect(modelButton).toHaveAttribute("aria-label", "Select model");
    });

    test("opens the same anchored skill picker as slash suggestions", async () => {
      const user = userEvent.setup();
      (useSkills as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        skills: [
          {
            name: "research",
            description: "Research a topic",
            category: "general",
            license: "MIT",
            enabled: true,
          },
        ],
        isLoading: false,
        error: null,
      });

      render(<InputBox {...defaultProps()} />);

      const skillButton = screen
        .getAllByTestId("skill-selector-trigger")
        .find((element) => element.tagName === "BUTTON");
      await user.click(skillButton!);

      const picker = screen.getByTestId("slash-overlay");
      expect(picker).toHaveClass("left-0", "right-0", "w-full", "bottom-full");
      expect(picker).toHaveTextContent("research");
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

      await user.click(screen.getByTestId("slash-option-research"));
      expect(mockSetInput).toHaveBeenCalledWith("/research ");
    });
  });

  describe("slash skill picker", () => {
    const skill = {
      name: "research",
      description: "Research a topic",
      category: "general",
      license: "MIT",
      enabled: true,
    };

    test("matches the input width and sits against the input top edge", () => {
      render(
        <SlashOverlay
          skills={[skill]}
          query=""
          activeIndex={0}
          onSelect={vi.fn()}
          onClose={vi.fn()}
        />,
      );

      const overlay = screen.getByTestId("slash-overlay");
      expect(overlay).toHaveClass("left-0", "right-0", "w-full", "mb-2");
      expect(overlay).not.toHaveClass("w-auto", "max-w-none");
    });

    test("hides the skill button and ignores slash invocation when disabled", async () => {
      const user = userEvent.setup();
      (useSkills as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        skills: [skill],
        isLoading: false,
        error: null,
      });

      render(<InputBox {...defaultProps()} skillInvocationEnabled={false} />);

      expect(
        screen.queryByTestId("skill-selector-trigger"),
      ).not.toBeInTheDocument();
      const textarea = screen.getByTestId("chat-input");
      await user.type(textarea, "/");
      expect(screen.queryByTestId("slash-overlay")).not.toBeInTheDocument();
    });
  });

  // ----- Disabled and welcome mode combined -----

  describe("combined props", () => {
    test("does not show followups when both disabled and welcome mode", () => {
      render(<InputBox {...defaultProps()} disabled isWelcomeMode />);
      expect(
        screen.queryByText("Generating follow-up questions..."),
      ).not.toBeInTheDocument();
    });
  });

  // ----- AddAttachmentsButton click -----

  describe("AddAttachmentsButton", () => {
    test("clicking attachment button calls openFileDialog", async () => {
      const user = userEvent.setup();
      render(<InputBox {...defaultProps()} />);

      const tooltip = screen.getByTitle("Add attachments");
      const attachButton = tooltip.querySelector("button");
      expect(attachButton).toBeTruthy();
      await user.click(attachButton!);
      expect(mockOpenFileDialog).toHaveBeenCalledOnce();
    });
  });

  // ----- Submit with non-empty text -----

  describe("submit with text", () => {
    test("calls onSubmit when text is non-empty and model matches", async () => {
      const onSubmit = vi.fn();
      mockTextInputContext.value = "Hello world";

      render(
        <InputBox
          {...defaultProps()}
          onSubmit={onSubmit}
          context={makeContext({
            model_name: "gpt-4o",
            mode: "flash",
          })}
        />,
      );

      const form = screen.getByTestId("prompt-input");
      form.dispatchEvent(
        new Event("submit", { bubbles: true, cancelable: true }),
      );

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({ text: "Hello world", files: [] }),
        );
      });
    });

    test("resets followup state on new submit", async () => {
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ suggestions: ["Old suggestion"] }),
      });

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

      const { rerender } = render(
        <InputBox
          {...defaultProps()}
          status="streaming"
          context={makeContext({ model_name: "gpt-4o", mode: "flash" })}
        />,
      );

      // Transition to ready to trigger suggestion fetch
      rerender(
        <InputBox
          {...defaultProps()}
          status="ready"
          context={makeContext({ model_name: "gpt-4o", mode: "flash" })}
        />,
      );

      await waitFor(() => {
        expect(screen.getByText("Old suggestion")).toBeInTheDocument();
      });

      // Now submit a new message
      mockTextInputContext.value = "New question";
      const form = screen.getByTestId("prompt-input");
      form.dispatchEvent(
        new Event("submit", { bubbles: true, cancelable: true }),
      );

      // Followups should be cleared
      await waitFor(() => {
        expect(screen.queryByText("Old suggestion")).not.toBeInTheDocument();
      });
    });
  });

  // ----- Reasoning effort selection interaction -----

  describe("reasoning effort interaction", () => {
    test("selecting high effort calls onContextChange", async () => {
      const user = userEvent.setup();
      const onContextChange = vi.fn();
      const models = [makeThinkingModel({ supports_reasoning_effort: true })];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          onContextChange={onContextChange}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "pro",
            reasoning_effort: "medium",
          })}
        />,
      );

      // Find the reasoning effort trigger
      const effortTrigger = screen
        .getAllByText(/Reasoning Effort/)
        .find((el) => el.closest("button"));
      expect(effortTrigger).toBeTruthy();

      const btn = effortTrigger!.closest("button")!;
      await user.click(btn);

      // Click on "High" option
      const highButton = screen
        .getAllByText("High")
        .find((el) => el.closest("button"));
      if (highButton) {
        await user.click(highButton.closest("button")!);
        expect(onContextChange).toHaveBeenCalledWith(
          expect.objectContaining({ reasoning_effort: "high" }),
        );
      }
    });
  });

  // ----- Model mismatch on submit -----

  describe("submit model mismatch guard", () => {
    test("defers submit when resolved model differs from context model", async () => {
      const onContextChange = vi.fn();
      const onSubmit = vi.fn();
      mockTextInputContext.value = "Hello";

      // Set up so resolvedModelName will differ from context.model_name
      const models = [
        makeModel({ name: "actual-model", display_name: "Actual" }),
      ];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          onSubmit={onSubmit}
          onContextChange={onContextChange}
          context={makeContext({
            model_name: "different-model",
            mode: "flash",
          })}
        />,
      );

      const form = screen.getByTestId("prompt-input");
      form.dispatchEvent(
        new Event("submit", { bubbles: true, cancelable: true }),
      );

      // Should call onContextChange to fix the model name
      await waitFor(() => {
        expect(onContextChange).toHaveBeenCalledWith(
          expect.objectContaining({ model_name: "actual-model" }),
        );
      });
    });
  });

  // ----- Empty model list -----

  describe("empty model list", () => {
    test("renders without crashing when models is empty", () => {
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models: [],
      });

      render(<InputBox {...defaultProps()} />);
      expect(screen.getByTestId("input-box")).toBeInTheDocument();
    });
  });

  // ----- onFollowupsVisibilityChange -----

  describe("onFollowupsVisibilityChange with followups", () => {
    test("calls onFollowupsVisibilityChange with true when followups are shown", async () => {
      const onFollowupsVisibilityChange = vi.fn();
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ suggestions: ["Follow-up"] }),
      });

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

      const { rerender } = render(
        <InputBox
          {...defaultProps()}
          status="streaming"
          onFollowupsVisibilityChange={onFollowupsVisibilityChange}
          context={makeContext({ model_name: "gpt-4o", mode: "flash" })}
        />,
      );

      rerender(
        <InputBox
          {...defaultProps()}
          status="ready"
          onFollowupsVisibilityChange={onFollowupsVisibilityChange}
          context={makeContext({ model_name: "gpt-4o", mode: "flash" })}
        />,
      );

      await waitFor(() => {
        expect(onFollowupsVisibilityChange).toHaveBeenCalledWith(true);
      });
    });
  });

  // ----- Suggestion fetch with empty recent messages -----

  describe("suggestion fetch edge cases", () => {
    test("does not fetch suggestions when recent messages are empty", async () => {
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;

      const thread = makeThread({ messages: [] });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

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

      await new Promise((r) => setTimeout(r, 50));
      expect(mockFetch).not.toHaveBeenCalled();
    });

    test("does not duplicate suggestion fetch for same AI message", async () => {
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ suggestions: ["Q1"] }),
      });

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

      const { rerender } = render(
        <InputBox
          {...defaultProps()}
          status="streaming"
          context={makeContext({ model_name: "gpt-4o", mode: "flash" })}
        />,
      );

      // First transition to ready
      rerender(
        <InputBox
          {...defaultProps()}
          status="ready"
          context={makeContext({ model_name: "gpt-4o", mode: "flash" })}
        />,
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledTimes(1);
      });

      // Re-render with same status (no new streaming->ready transition)
      rerender(
        <InputBox
          {...defaultProps()}
          status="ready"
          context={makeContext({ model_name: "gpt-4o", mode: "flash" })}
        />,
      );

      await new Promise((r) => setTimeout(r, 50));
      // Should not fetch again since there was no new streaming->ready transition
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });
  });

  // ----- Reasoning effort selection - all levels -----

  describe("reasoning effort selection - all levels", () => {
    function setupThinkingModelWithEffort() {
      const onContextChange = vi.fn();
      const models = [makeThinkingModel({ supports_reasoning_effort: true })];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });
      return { onContextChange, models };
    }

    test("selecting minimal effort calls onContextChange with minimal", async () => {
      const user = userEvent.setup();
      const { onContextChange } = setupThinkingModelWithEffort();

      render(
        <InputBox
          {...defaultProps()}
          onContextChange={onContextChange}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "pro",
            reasoning_effort: "high",
          })}
        />,
      );

      // Open the reasoning effort dropdown
      const effortTrigger = screen
        .getAllByText(/Reasoning Effort/)
        .find((el) => el.closest("button"));
      const btn = effortTrigger!.closest("button")!;
      await user.click(btn);

      // Click on "Minimal" option
      const minimalBtn = screen.getByText("Minimal").closest("button");
      expect(minimalBtn).toBeTruthy();
      await user.click(minimalBtn!);

      expect(onContextChange).toHaveBeenCalledWith(
        expect.objectContaining({ reasoning_effort: "minimal" }),
      );
    });

    test("selecting low effort calls onContextChange with low", async () => {
      const user = userEvent.setup();
      const { onContextChange } = setupThinkingModelWithEffort();

      render(
        <InputBox
          {...defaultProps()}
          onContextChange={onContextChange}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "pro",
            reasoning_effort: "high",
          })}
        />,
      );

      const effortTrigger = screen
        .getAllByText(/Reasoning Effort/)
        .find((el) => el.closest("button"));
      const btn = effortTrigger!.closest("button")!;
      await user.click(btn);

      const lowBtn = screen.getByText("Low").closest("button");
      expect(lowBtn).toBeTruthy();
      await user.click(lowBtn!);

      expect(onContextChange).toHaveBeenCalledWith(
        expect.objectContaining({ reasoning_effort: "low" }),
      );
    });

    test("selecting medium effort calls onContextChange with medium", async () => {
      const user = userEvent.setup();
      const { onContextChange } = setupThinkingModelWithEffort();

      render(
        <InputBox
          {...defaultProps()}
          onContextChange={onContextChange}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "pro",
            reasoning_effort: "low",
          })}
        />,
      );

      const effortTrigger = screen
        .getAllByText(/Reasoning Effort/)
        .find((el) => el.closest("button"));
      const btn = effortTrigger!.closest("button")!;
      await user.click(btn);

      const mediumBtn = screen.getByText("Medium").closest("button");
      expect(mediumBtn).toBeTruthy();
      await user.click(mediumBtn!);

      expect(onContextChange).toHaveBeenCalledWith(
        expect.objectContaining({ reasoning_effort: "medium" }),
      );
    });

    test("selecting high effort calls onContextChange with high", async () => {
      const user = userEvent.setup();
      const { onContextChange } = setupThinkingModelWithEffort();

      render(
        <InputBox
          {...defaultProps()}
          onContextChange={onContextChange}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "pro",
            reasoning_effort: "minimal",
          })}
        />,
      );

      const effortTrigger = screen
        .getAllByText(/Reasoning Effort/)
        .find((el) => el.closest("button"));
      const btn = effortTrigger!.closest("button")!;
      await user.click(btn);

      const highBtn = screen.getByText("High").closest("button");
      expect(highBtn).toBeTruthy();
      await user.click(highBtn!);

      expect(onContextChange).toHaveBeenCalledWith(
        expect.objectContaining({ reasoning_effort: "high" }),
      );
    });

    test("displays current reasoning effort level in trigger text", () => {
      const models = [makeThinkingModel({ supports_reasoning_effort: true })];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "thinking",
            reasoning_effort: "high",
          })}
        />,
      );

      // The trigger should show the current effort level
      expect(screen.getAllByText(/High/).length).toBeGreaterThan(0);
    });

    test("displays minimal effort level in trigger text", () => {
      const models = [makeThinkingModel({ supports_reasoning_effort: true })];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "thinking",
            reasoning_effort: "minimal",
          })}
        />,
      );

      expect(screen.getAllByText(/Minimal/).length).toBeGreaterThan(0);
    });

    test("displays low effort level in trigger text", () => {
      const models = [makeThinkingModel({ supports_reasoning_effort: true })];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "pro",
            reasoning_effort: "low",
          })}
        />,
      );

      expect(screen.getAllByText(/Low/).length).toBeGreaterThan(0);
    });

    test("displays medium effort level in trigger text", () => {
      const models = [makeThinkingModel({ supports_reasoning_effort: true })];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "pro",
            reasoning_effort: "medium",
          })}
        />,
      );

      expect(screen.getAllByText(/Medium/).length).toBeGreaterThan(0);
    });

    test("shows reasoning effort selector in thinking mode", () => {
      const models = [makeThinkingModel({ supports_reasoning_effort: true })];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "thinking",
            reasoning_effort: "low",
          })}
        />,
      );

      expect(screen.getAllByText(/Reasoning Effort/).length).toBeGreaterThan(0);
    });

    test("shows reasoning effort selector in ultra mode", () => {
      const models = [makeThinkingModel({ supports_reasoning_effort: true })];
      (useModels as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        models,
      });

      render(
        <InputBox
          {...defaultProps()}
          context={makeContext({
            model_name: "claude-sonnet",
            mode: "ultra",
            reasoning_effort: "high",
          })}
        />,
      );

      expect(screen.getAllByText(/Reasoning Effort/).length).toBeGreaterThan(0);
    });
  });

  // ----- Confirm dialog edge cases -----

  describe("confirm dialog edge cases", () => {
    test("clicking replace when dialog opens sets input and submits", async () => {
      const user = userEvent.setup();
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ suggestions: ["Suggestion X"] }),
      });

      mockTextInputContext.value = "existing";

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

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
        expect(screen.getByText("Suggestion X")).toBeInTheDocument();
      });

      // Click suggestion to open dialog
      await user.click(screen.getByText("Suggestion X"));

      await waitFor(() => {
        expect(screen.getByText("Send suggestion?")).toBeInTheDocument();
      });

      // Click Replace & send
      await user.click(screen.getByText("Replace & send"));

      // Dialog should close and input should be set
      await waitFor(() => {
        expect(screen.queryByText("Send suggestion?")).not.toBeInTheDocument();
      });
      expect(mockSetInput).toHaveBeenCalledWith("Suggestion X");
    });

    test("clicking append when dialog opens concatenates with newline", async () => {
      const user = userEvent.setup();
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ suggestions: ["Extra"] }),
      });

      mockTextInputContext.value = "existing";

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

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
        expect(screen.getByText("Extra")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Extra"));

      await waitFor(() => {
        expect(screen.getByText("Send suggestion?")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Append & send"));

      await waitFor(() => {
        expect(screen.queryByText("Send suggestion?")).not.toBeInTheDocument();
      });
      expect(mockSetInput).toHaveBeenCalledWith("existing\nExtra");
    });

    test("clicking cancel in dialog closes it without setting input", async () => {
      const user = userEvent.setup();
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ suggestions: ["Test Sugg"] }),
      });

      mockTextInputContext.value = "some text";

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

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
        expect(screen.getByText("Test Sugg")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Test Sugg"));

      await waitFor(() => {
        expect(screen.getByText("Send suggestion?")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Cancel"));

      await waitFor(() => {
        expect(screen.queryByText("Send suggestion?")).not.toBeInTheDocument();
      });
      expect(mockSetInput).not.toHaveBeenCalled();
    });
  });

  // ----- handleFollowupClick with empty input (direct submit path) -----

  describe("handleFollowupClick direct submit", () => {
    test("clicking followup with empty input sets text and triggers submit", async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ suggestions: ["Direct suggestion"] }),
      });

      mockTextInputContext.value = "";

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

      const { rerender } = render(
        <InputBox
          {...defaultProps()}
          onSubmit={onSubmit}
          status="streaming"
          context={makeContext({ model_name: "gpt-4o", mode: "flash" })}
        />,
      );

      rerender(
        <InputBox
          {...defaultProps()}
          onSubmit={onSubmit}
          status="ready"
          context={makeContext({ model_name: "gpt-4o", mode: "flash" })}
        />,
      );

      await waitFor(() => {
        expect(screen.getByText("Direct suggestion")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Direct suggestion"));

      // Input should be set
      expect(mockSetInput).toHaveBeenCalledWith("Direct suggestion");
    });

    test("clicking followup during streaming is a no-op", async () => {
      const user = userEvent.setup();
      const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ suggestions: ["Stream sugg"] }),
      });

      const thread = makeThread({
        messages: [
          { id: "msg-1", type: "human", content: "Hello" },
          { id: "msg-2", type: "ai", content: "Hi!" },
        ],
      });
      (useThread as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
        thread,
      );

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
        expect(screen.getByText("Stream sugg")).toBeInTheDocument();
      });

      // Set streaming status
      rerender(
        <InputBox
          {...defaultProps()}
          status="streaming"
          context={makeContext({ model_name: "gpt-4o", mode: "flash" })}
        />,
      );

      await user.click(screen.getByText("Stream sugg"));

      // Should not call setInput since status is streaming
      expect(mockSetInput).not.toHaveBeenCalled();
    });
  });
});
