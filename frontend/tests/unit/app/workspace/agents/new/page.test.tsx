import { render, screen, fireEvent, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks – declared before any imports so vitest hoists them correctly.
// ---------------------------------------------------------------------------

const mockPush = vi.fn();
const mockSendMessage = vi.fn();

let threadIsLoading = false;
let toolEndCallback: ((args: { name: string }) => void) | undefined;
let finishCallback: (() => void) | undefined;

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      agents: {
        createPageTitle: "Create Agent",
        nameStepTitle: "Name Your Agent",
        nameStepHint: "Choose a unique name",
        nameStepPlaceholder: "agent-name",
        nameStepContinue: "Continue",
        nameStepInvalidError: "Invalid name",
        nameStepAlreadyExistsError: "Already exists",
        nameStepNetworkError: "Network error",
        nameStepCheckError: "Check error",
        nameStepBootstrapMessage: "Hello {name}",
        visibility: "可见性",
        visibilityPrivate: "私有",
        visibilityDepartment: "部门共享",
        visibilityPublic: "公开",
        visibilityAdminOnly: "部门共享和公开选项仅管理员可用",
        more: "More",
        save: "Save",
        saving: "Saving...",
        saveHint: "Save hint",
        saveCommandMessage: "/save",
        saveRequested: "Save requested",
        agentCreated: "Agent created",
        agentCreatedPendingRefresh: "Pending refresh",
        startChatting: "Start Chatting",
        backToGallery: "Back",
        createPageSubtitle: "Describe your agent",
      },
      common: { loading: "Loading..." },
    },
  }),
}));

vi.mock("@/core/agents/api", () => ({
  checkAgentName: vi.fn(),
  getAgent: vi.fn(),
  AgentNameCheckError: class extends Error {
    reason: string;
    constructor(msg: string, reason: string) {
      super(msg);
      this.reason = reason;
    }
  },
}));

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: () => ({ user: null }),
}));

vi.mock("@/core/threads/hooks", () => ({
  useThreadStream: ({ onToolEnd, onFinish }: any) => {
    toolEndCallback = onToolEnd;
    finishCallback = onFinish;
    return {
      thread: {
        isLoading: threadIsLoading,
        messages: [],
        values: {},
        stop: vi.fn(),
        getMessagesMetadata: vi.fn(),
      },
      sendMessage: mockSendMessage,
    };
  },
}));

vi.mock("@/core/utils/uuid", () => ({
  uuid: () => "test-uuid-123",
}));

vi.mock("@/lib/ime", () => ({
  isIMEComposing: vi.fn(() => false),
}));

vi.mock("@/components/ui/input", () => ({
  Input: ({ autoFocus, ...props }: any) => (
    <input data-autofocus={autoFocus ? "" : undefined} {...props} />
  ),
}));

vi.mock("@/components/ui/label", () => ({
  Label: ({ children, ...props }: any) => <label {...props}>{children}</label>,
}));

vi.mock("@/components/ui/select", () => ({
  Select: ({ children, value }: any) => (
    <div data-testid="select" data-value={value}>
      {children}
    </div>
  ),
  SelectContent: ({ children }: any) => <div>{children}</div>,
  SelectItem: ({ children, value, disabled }: any) => (
    <div data-value={value} data-disabled={disabled ? "true" : "false"}>
      {children}
    </div>
  ),
  SelectTrigger: ({ children }: any) => <div>{children}</div>,
  SelectValue: () => null,
}));

vi.mock("@/components/ui/alert", () => ({
  Alert: ({ children }: any) => <div data-testid="alert">{children}</div>,
  AlertDescription: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: any) => (
    <div data-testid="dropdown-menu">{children}</div>
  ),
  DropdownMenuContent: ({ children }: any) => <div>{children}</div>,
  DropdownMenuItem: ({ children, onSelect, disabled, ...rest }: any) => (
    <div
      {...rest}
      data-disabled={disabled ? "true" : "false"}
      onClick={() => {
        if (!disabled && onSelect) onSelect();
      }}
    >
      {children}
    </div>
  ),
  DropdownMenuTrigger: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("@/components/ai-elements/prompt-input", () => ({
  PromptInput: ({ children, onSubmit }: any) => (
    <div data-testid="prompt-input">
      <button
        data-testid="prompt-submit"
        onClick={() => onSubmit({ text: "test message" })}
      />
      <button
        data-testid="prompt-submit-empty"
        onClick={() => onSubmit({ text: "  " })}
      />
      {children}
    </div>
  ),
  PromptInputFooter: ({ children }: any) => <div>{children}</div>,
  PromptInputSubmit: ({ disabled }: any) => (
    <button data-testid="prompt-submit-btn" disabled={disabled}>
      Submit
    </button>
  ),
  PromptInputTextarea: ({ disabled, placeholder }: any) => (
    <textarea
      data-testid="prompt-textarea"
      disabled={disabled}
      placeholder={placeholder}
    />
  ),
}));

vi.mock("@/components/workspace/artifacts", () => ({
  ArtifactsProvider: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("@/components/workspace/messages", () => ({
  MessageList: ({ threadId }: any) => (
    <div data-testid="message-list" data-thread-id={threadId}>
      Messages
    </div>
  ),
}));

vi.mock("@/components/workspace/messages/context", () => ({
  ThreadContext: {
    Provider: ({ children }: any) => (
      <div data-testid="thread-context">{children}</div>
    ),
  },
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, disabled, variant, ...props }: any) => (
    <button
      onClick={onClick}
      disabled={disabled}
      data-variant={variant}
      {...props}
    >
      {children}
    </button>
  ),
}));

// ---------------------------------------------------------------------------
// Imports – after mocks are set up.
// ---------------------------------------------------------------------------

import NewAgentPage from "@/app/workspace/agents/new/page";
import { checkAgentName, getAgent } from "@/core/agents/api";
import { isIMEComposing } from "@/lib/ime";
import { toast } from "sonner";

const mockedCheckAgentName = vi.mocked(checkAgentName);
const mockedGetAgent = vi.mocked(getAgent);
const mockedToast = vi.mocked(toast);
const mockedIsIMEComposing = vi.mocked(isIMEComposing);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPage() {
  return render(<NewAgentPage />);
}

function getNameInput() {
  return screen.getByPlaceholderText("agent-name");
}

function getContinueButton() {
  return screen.getByText("Continue");
}

/** Navigate from name step to chat step with the given agent name. */
async function goToChatStep(agentName = "chat-agent") {
  renderPage();
  fireEvent.change(getNameInput(), { target: { value: agentName } });
  fireEvent.click(getContinueButton());
  await act(async () => {});
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("NewAgentPage", () => {
  beforeEach(() => {
    // Reset all mock implementations to clean state
    mockPush.mockClear();
    mockSendMessage.mockClear();
    mockSendMessage.mockResolvedValue(undefined);
    mockedCheckAgentName.mockClear();
    mockedCheckAgentName.mockResolvedValue({ available: true, name: "agent" });
    mockedGetAgent.mockClear();
    mockedGetAgent.mockResolvedValue(null as any);
    mockedToast.success.mockClear();
    mockedToast.error.mockClear();
    mockedIsIMEComposing.mockClear();
    mockedIsIMEComposing.mockReturnValue(false);
    threadIsLoading = false;
    toolEndCallback = undefined;
    finishCallback = undefined;
    window.localStorage.clear();
  });

  // =========================================================================
  // Name Step - Rendering
  // =========================================================================

  describe("Name step rendering", () => {
    test("renders the name step with title, hint, input, and continue button", () => {
      renderPage();
      expect(screen.getByText("Name Your Agent")).toBeInTheDocument();
      expect(screen.getByText("Choose a unique name")).toBeInTheDocument();
      expect(getNameInput()).toBeInTheDocument();
      expect(getContinueButton()).toBeInTheDocument();
    });

    test("renders header with create page title", () => {
      renderPage();
      expect(screen.getByText("Create Agent")).toBeInTheDocument();
    });

    test("renders back button with ghost variant in header", () => {
      renderPage();
      const backBtn = document.querySelector(
        "header button[data-variant='ghost']",
      );
      expect(backBtn).toBeInTheDocument();
    });

    test("does not render dropdown menu in name step", () => {
      renderPage();
      expect(screen.queryByText("More")).not.toBeInTheDocument();
    });

    test("renders the bot icon area", () => {
      renderPage();
      const iconArea = document.querySelector(".bg-primary\\/10");
      expect(iconArea).toBeInTheDocument();
    });

    test("renders visibility label", () => {
      renderPage();
      expect(screen.getByText("可见性")).toBeInTheDocument();
    });

    test("renders visibility select with default value private", () => {
      renderPage();
      const select = screen.getByTestId("select");
      expect(select).toHaveAttribute("data-value", "private");
    });

    test("does not render prompt input in name step", () => {
      renderPage();
      expect(screen.queryByTestId("prompt-input")).not.toBeInTheDocument();
    });

    test("does not render message list in name step", () => {
      renderPage();
      expect(screen.queryByTestId("message-list")).not.toBeInTheDocument();
    });
  });

  // =========================================================================
  // Name Step - Admin vs Non-Admin Visibility
  // =========================================================================

  describe("Visibility options based on user role", () => {
    test("non-admin shows hint about admin-only options", () => {
      renderPage();
      expect(
        screen.getByText("部门共享和公开选项仅管理员可用"),
      ).toBeInTheDocument();
    });

    test("non-admin shows department and public as disabled", () => {
      renderPage();
      const deptOption = screen.getByText("部门共享");
      const publicOption = screen.getByText("公开");
      expect(deptOption.closest("[data-disabled]")).toHaveAttribute(
        "data-disabled",
        "true",
      );
      expect(publicOption.closest("[data-disabled]")).toHaveAttribute(
        "data-disabled",
        "true",
      );
    });

    test("private option is not disabled", () => {
      renderPage();
      const privateOption = screen.getByText("私有");
      expect(privateOption.closest("[data-disabled]")).toHaveAttribute(
        "data-disabled",
        "false",
      );
    });
  });

  // =========================================================================
  // Name Step - Input Behavior
  // =========================================================================

  describe("Name input behavior", () => {
    test("input starts with empty value", () => {
      renderPage();
      expect(getNameInput()).toHaveValue("");
    });

    test("input has autoFocus data attribute", () => {
      renderPage();
      expect(getNameInput()).toHaveAttribute("data-autofocus");
    });

    test("input onChange updates value", () => {
      renderPage();
      const input = getNameInput();
      fireEvent.change(input, { target: { value: "my-agent" } });
      expect(input).toHaveValue("my-agent");
    });

    test("input onChange clears name error", () => {
      renderPage();
      const input = getNameInput();

      // First, trigger an error by submitting an invalid name
      fireEvent.change(input, { target: { value: "invalid name!" } });
      fireEvent.click(getContinueButton());
      expect(screen.getByText("Invalid name")).toBeInTheDocument();

      // Now change input - error should clear
      fireEvent.change(input, { target: { value: "valid-name" } });
      expect(screen.queryByText("Invalid name")).not.toBeInTheDocument();
    });

    test("continue button is disabled when input is empty", () => {
      renderPage();
      expect(getContinueButton()).toBeDisabled();
    });

    test("continue button is enabled when input has value", () => {
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "my-agent" } });
      expect(getContinueButton()).not.toBeDisabled();
    });

    test("input has border-destructive class when error is present", () => {
      renderPage();
      const input = getNameInput();
      fireEvent.change(input, { target: { value: "bad!" } });
      fireEvent.click(getContinueButton());
      expect(input.className).toContain("border-destructive");
    });
  });

  // =========================================================================
  // Name Step - Keyboard Handling
  // =========================================================================

  describe("Keyboard handling", () => {
    test("Enter key triggers handleConfirmName when not composing", () => {
      renderPage();
      const input = getNameInput();
      fireEvent.change(input, { target: { value: "my-agent" } });
      fireEvent.keyDown(input, { key: "Enter" });

      expect(mockedCheckAgentName).toHaveBeenCalledWith("my-agent");
    });

    test("Enter key does NOT trigger when IME is composing", () => {
      mockedIsIMEComposing.mockReturnValue(true);
      renderPage();
      const input = getNameInput();
      fireEvent.change(input, { target: { value: "my-agent" } });
      fireEvent.keyDown(input, { key: "Enter" });

      expect(mockedCheckAgentName).not.toHaveBeenCalled();
    });

    test("non-Enter key does not trigger confirm", () => {
      renderPage();
      const input = getNameInput();
      fireEvent.change(input, { target: { value: "my-agent" } });
      fireEvent.keyDown(input, { key: "a" });

      expect(mockedCheckAgentName).not.toHaveBeenCalled();
    });
  });

  // =========================================================================
  // Name Step - handleConfirmName Validation
  // =========================================================================

  describe("handleConfirmName validation", () => {
    test("empty trimmed input returns early without calling API", async () => {
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "   " } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(mockedCheckAgentName).not.toHaveBeenCalled();
    });

    test("invalid name format (with spaces) shows error", async () => {
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "invalid name" } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(screen.getByText("Invalid name")).toBeInTheDocument();
      expect(mockedCheckAgentName).not.toHaveBeenCalled();
    });

    test("invalid name format (with special chars) shows error", async () => {
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "agent@name!" } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(screen.getByText("Invalid name")).toBeInTheDocument();
    });

    test("valid name format proceeds to API check", async () => {
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "valid-agent" } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(mockedCheckAgentName).toHaveBeenCalledWith("valid-agent");
    });

    test("name with underscores is invalid", async () => {
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "my_agent" } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(screen.getByText("Invalid name")).toBeInTheDocument();
    });

    test("name with dots is invalid", async () => {
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "my.agent" } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(screen.getByText("Invalid name")).toBeInTheDocument();
    });

    test("name with only dashes is valid", async () => {
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "---" } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(mockedCheckAgentName).toHaveBeenCalledWith("---");
    });

    test("name with mixed case and numbers is valid", async () => {
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "MyAgent123" } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(mockedCheckAgentName).toHaveBeenCalledWith("MyAgent123");
    });

    test("whitespace-only input after trim returns early", async () => {
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "   " } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(mockedCheckAgentName).not.toHaveBeenCalled();
    });
  });

  // =========================================================================
  // Name Step - handleConfirmName API Responses
  // =========================================================================

  describe("handleConfirmName API responses", () => {
    test("name already taken shows error", async () => {
      mockedCheckAgentName.mockResolvedValue({
        available: false,
        name: "taken-name",
      });
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "taken-name" } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(screen.getByText("Already exists")).toBeInTheDocument();
    });

    test("AgentNameCheckError with backend_unreachable shows network error", async () => {
      const { AgentNameCheckError } = await import("@/core/agents/api");
      mockedCheckAgentName.mockRejectedValue(
        new AgentNameCheckError("unreachable", "backend_unreachable"),
      );
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "test-agent" } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });

    test("unknown error shows generic check error", async () => {
      mockedCheckAgentName.mockRejectedValue(new Error("something broke"));
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "test-agent" } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(screen.getByText("Check error")).toBeInTheDocument();
    });

    test("successful check moves to chat step", async () => {
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "good-agent" } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      const msgList = screen.getByTestId("message-list");
      expect(msgList).toBeInTheDocument();
      expect(msgList).toHaveTextContent(/Messages/i);
      expect(screen.getByTestId("prompt-input")).toBeInTheDocument();
    });

    test("successful check sends bootstrap message", async () => {
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "good-agent" } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(mockSendMessage).toHaveBeenCalledWith(
        "test-uuid-123",
        { text: "Hello good-agent", files: [] },
        { agent_name: "good-agent" },
      );
    });

    test("isCheckingName disables the continue button during API call", async () => {
      let resolveCheck: (v: any) => void;
      mockedCheckAgentName.mockReturnValue(
        new Promise((resolve) => {
          resolveCheck = resolve;
        }) as any,
      );

      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "slow-agent" } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(getContinueButton()).toBeDisabled();

      await act(async () => {
        resolveCheck!({ available: true });
      });
    });
  });

  // =========================================================================
  // Name Step - handleConfirmName trims input
  // =========================================================================

  describe("handleConfirmName trims input", () => {
    test("trims whitespace before validation", async () => {
      renderPage();
      fireEvent.change(getNameInput(), {
        target: { value: "  trimmed-agent  " },
      });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(mockedCheckAgentName).toHaveBeenCalledWith("trimmed-agent");
    });

    test("sends trimmed name in bootstrap message", async () => {
      renderPage();
      fireEvent.change(getNameInput(), {
        target: { value: "  trimmed-agent  " },
      });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(mockSendMessage).toHaveBeenCalledWith(
        "test-uuid-123",
        { text: "Hello trimmed-agent", files: [] },
        { agent_name: "trimmed-agent" },
      );
    });
  });

  // =========================================================================
  // Chat Step - Rendering
  // =========================================================================

  describe("Chat step rendering", () => {
    test("renders message list", async () => {
      await goToChatStep();
      const msgList = screen.getByTestId("message-list");
      expect(msgList).toBeInTheDocument();
      expect(msgList).toHaveTextContent(/Messages/i);
    });

    test("renders prompt input", async () => {
      await goToChatStep();
      expect(screen.getByTestId("prompt-input")).toBeInTheDocument();
    });

    test("renders dropdown menu in chat step header", async () => {
      await goToChatStep();
      expect(screen.getByTestId("dropdown-menu")).toBeInTheDocument();
    });

    test("renders More button in chat step", async () => {
      await goToChatStep();
      expect(screen.getByLabelText("More")).toBeInTheDocument();
    });

    test("does NOT render the name step content", async () => {
      await goToChatStep();
      expect(screen.queryByText("Name Your Agent")).not.toBeInTheDocument();
      expect(
        screen.queryByText("Choose a unique name"),
      ).not.toBeInTheDocument();
    });

    test("message list has correct thread id", async () => {
      await goToChatStep();
      const list = screen.getByTestId("message-list");
      expect(list).toHaveAttribute("data-thread-id", "test-uuid-123");
    });

    test("does not render visibility select in chat step", async () => {
      await goToChatStep();
      expect(screen.queryByText("可见性")).not.toBeInTheDocument();
    });

    test("wraps content with ThreadContext.Provider", async () => {
      await goToChatStep();
      const ctx = screen.getByTestId("thread-context");
      expect(ctx).toBeInTheDocument();
      expect(ctx).toHaveTextContent(/Messages/i);
    });
  });

  // =========================================================================
  // Chat Step - Save Hint
  // =========================================================================

  describe("Save hint", () => {
    test("shows save hint on first visit to chat step", async () => {
      await goToChatStep();
      expect(screen.getByTestId("alert")).toBeInTheDocument();
      expect(screen.getByText("Save hint")).toBeInTheDocument();
    });

    test("does NOT show save hint if localStorage already has the key", async () => {
      window.localStorage.setItem("ideer.agent-create.save-hint-seen", "1");
      await goToChatStep();
      expect(screen.queryByTestId("alert")).not.toBeInTheDocument();
    });

    test("sets localStorage after showing hint", async () => {
      await goToChatStep();
      expect(
        window.localStorage.getItem("ideer.agent-create.save-hint-seen"),
      ).toBe("1");
    });
  });

  // =========================================================================
  // Chat Step - handleChatSubmit
  // =========================================================================

  describe("handleChatSubmit", () => {
    test("sends message when submitting text", async () => {
      await goToChatStep("submit-agent");

      const submitBtn = screen.getByTestId("prompt-submit");
      await act(async () => {
        fireEvent.click(submitBtn);
      });

      // Once for bootstrap, once for the submit
      expect(mockSendMessage).toHaveBeenCalledTimes(2);
      expect(mockSendMessage).toHaveBeenLastCalledWith(
        "test-uuid-123",
        { text: "test message", files: [] },
        { agent_name: "submit-agent" },
      );
    });

    test("does NOT send message when text is empty/whitespace", async () => {
      await goToChatStep("empty-agent");

      const emptySubmitBtn = screen.getByTestId("prompt-submit-empty");
      await act(async () => {
        fireEvent.click(emptySubmitBtn);
      });

      // Only bootstrap message should have been sent (1 call total)
      expect(mockSendMessage).toHaveBeenCalledTimes(1);
    });
  });

  // =========================================================================
  // Chat Step - handleChatSubmit when loading
  // =========================================================================

  describe("handleChatSubmit when loading", () => {
    test("does not send message when thread is loading", async () => {
      threadIsLoading = true;
      await goToChatStep("loading-agent");

      const submitBtn = screen.getByTestId("prompt-submit");
      await act(async () => {
        fireEvent.click(submitBtn);
      });

      // Only bootstrap message (1 call), no additional message
      expect(mockSendMessage).toHaveBeenCalledTimes(1);
    });
  });

  // =========================================================================
  // Chat Step - handleSaveAgent
  // =========================================================================

  describe("handleSaveAgent", () => {
    test("sends save command when clicking save menu item", async () => {
      await goToChatStep("save-agent");

      const saveItem = screen.getByText("Save");
      await act(async () => {
        fireEvent.click(saveItem);
      });

      // Bootstrap + save command
      expect(mockSendMessage).toHaveBeenCalledTimes(2);
      expect(mockSendMessage).toHaveBeenLastCalledWith(
        "test-uuid-123",
        { text: "/save", files: [] },
        { agent_name: "save-agent" },
        { additionalKwargs: { hide_from_ui: true } },
      );
    });

    test("shows success toast after save", async () => {
      await goToChatStep("toast-agent");

      const saveItem = screen.getByText("Save");
      await act(async () => {
        fireEvent.click(saveItem);
      });

      expect(mockedToast.success).toHaveBeenCalledWith("Save requested");
    });

    test("hides save hint after clicking save", async () => {
      await goToChatStep("hint-hide-agent");

      // Hint should be visible initially
      expect(screen.getByTestId("alert")).toBeInTheDocument();

      const saveItem = screen.getByText("Save");
      await act(async () => {
        fireEvent.click(saveItem);
      });

      expect(screen.queryByTestId("alert")).not.toBeInTheDocument();
    });

    test("shows Saving... text when status is requested", async () => {
      await goToChatStep("saving-text-agent");

      const saveItem = screen.getByText("Save");
      await act(async () => {
        fireEvent.click(saveItem);
      });

      expect(screen.getByText("Saving...")).toBeInTheDocument();
    });

    test("save menu item is disabled when thread is loading", async () => {
      threadIsLoading = true;
      await goToChatStep("disabled-save-agent");

      const saveItem = screen.getByText("Save").closest("[data-disabled]");
      expect(saveItem).toHaveAttribute("data-disabled", "true");
    });

    test("shows error toast when save fails", async () => {
      // Set up: bootstrap resolves, save rejects
      mockSendMessage
        .mockResolvedValueOnce(undefined) // bootstrap
        .mockRejectedValueOnce(new Error("Network fail")); // save

      await goToChatStep("fail-save-agent");

      const saveItem = screen.getByText("Save");
      await act(async () => {
        fireEvent.click(saveItem);
      });

      expect(mockedToast.error).toHaveBeenCalledWith("Network fail");
    });

    test("resets setupAgentStatus to idle on error", async () => {
      // Set up: bootstrap resolves, save rejects
      mockSendMessage
        .mockResolvedValueOnce(undefined) // bootstrap
        .mockRejectedValueOnce(new Error("fail")); // save

      await goToChatStep("reset-status-agent");

      const saveItem = screen.getByText("Save");
      await act(async () => {
        fireEvent.click(saveItem);
      });

      // Status should be back to idle, "Save" should be shown (not "Saving...")
      expect(screen.getByText("Save")).toBeInTheDocument();
      expect(screen.queryByText("Saving...")).not.toBeInTheDocument();
    });
  });

  // =========================================================================
  // Chat Step - Agent Created State
  // =========================================================================

  describe("Agent created state", () => {
    test("shows agent created card after onToolEnd with setup_agent", async () => {
      mockedGetAgent.mockResolvedValue({
        name: "created-agent",
        config: {},
      } as any);

      await goToChatStep("created-agent");

      await act(async () => {
        toolEndCallback?.({ name: "setup_agent" });
      });
      await act(async () => {});

      expect(screen.getByText("Agent created")).toBeInTheDocument();
      expect(screen.getByText("Start Chatting")).toBeInTheDocument();
      expect(screen.getByText("Back")).toBeInTheDocument();
    });

    test("hides prompt input when agent is created", async () => {
      mockedGetAgent.mockResolvedValue({
        name: "no-prompt-agent",
        config: {},
      } as any);

      await goToChatStep("no-prompt-agent");

      await act(async () => {
        toolEndCallback?.({ name: "setup_agent" });
      });
      await act(async () => {});

      expect(screen.queryByTestId("prompt-input")).not.toBeInTheDocument();
    });

    test("start chatting button navigates to agent chat page", async () => {
      mockedGetAgent.mockResolvedValue({
        name: "nav-agent",
        config: {},
      } as any);

      await goToChatStep("nav-agent");

      await act(async () => {
        toolEndCallback?.({ name: "setup_agent" });
      });
      await act(async () => {});

      fireEvent.click(screen.getByText("Start Chatting"));
      expect(mockPush).toHaveBeenCalledWith(
        "/workspace/agents/nav-agent/chats/new",
      );
    });

    test("back to gallery button navigates to agents list", async () => {
      mockedGetAgent.mockResolvedValue({
        name: "back-agent",
        config: {},
      } as any);

      await goToChatStep("back-agent");

      await act(async () => {
        toolEndCallback?.({ name: "setup_agent" });
      });
      await act(async () => {});

      fireEvent.click(screen.getByText("Back"));
      expect(mockPush).toHaveBeenCalledWith("/workspace/agents");
    });
  });

  // =========================================================================
  // useThreadStream Callbacks
  // =========================================================================

  describe("useThreadStream callbacks", () => {
    test("onToolEnd with setup_agent fetches agent via getAgentWithRetry", async () => {
      mockedGetAgent.mockResolvedValue({
        name: "toolend-agent",
        config: {},
      } as any);

      await goToChatStep("toolend-agent");

      await act(async () => {
        toolEndCallback?.({ name: "setup_agent" });
      });

      expect(mockedGetAgent).toHaveBeenCalledWith("toolend-agent");
    });

    test("onToolEnd with non-setup_agent tool is ignored", async () => {
      await goToChatStep("ignore-agent");

      await act(async () => {
        toolEndCallback?.({ name: "other_tool" });
      });

      expect(mockedGetAgent).not.toHaveBeenCalled();
    });

    test("onToolEnd shows error toast when getAgentWithRetry returns null", async () => {
      vi.useFakeTimers();
      try {
        mockedGetAgent.mockRejectedValue(new Error("not found"));

        await goToChatStep("retry-null-agent");

        await act(async () => {
          toolEndCallback?.({ name: "setup_agent" });
        });

        // Step through each retry delay so microtasks flush between timers
        for (const delay of [200, 500, 1000, 2000]) {
          await act(async () => {
            vi.advanceTimersByTime(delay);
          });
        }

        expect(mockedToast.error).toHaveBeenCalledWith("Pending refresh");
      } finally {
        vi.useRealTimers();
      }
    }, 10000);

    test("onFinish resets status when agent is null and status is requested", async () => {
      await goToChatStep("finish-reset-agent");

      // Set status to "requested" by clicking save
      const saveItem = screen.getByText("Save");
      await act(async () => {
        fireEvent.click(saveItem);
      });
      expect(screen.getByText("Saving...")).toBeInTheDocument();

      // Trigger onFinish
      await act(async () => {
        finishCallback?.();
      });

      // Status should be back to idle
      expect(screen.getByText("Save")).toBeInTheDocument();
      expect(screen.queryByText("Saving...")).not.toBeInTheDocument();
    });

    test("onFinish does NOT reset status when agent exists", async () => {
      mockedGetAgent.mockResolvedValue({
        name: "finish-keep-agent",
        config: {},
      } as any);

      await goToChatStep("finish-keep-agent");

      // Create the agent
      await act(async () => {
        toolEndCallback?.({ name: "setup_agent" });
      });
      await act(async () => {});

      expect(screen.getByText("Agent created")).toBeInTheDocument();

      // onFinish should not change anything
      await act(async () => {
        finishCallback?.();
      });

      expect(screen.getByText("Agent created")).toBeInTheDocument();
    });

    test("onFinish does NOT reset status when agent is null and status is idle", async () => {
      await goToChatStep("idle-finish-agent");

      // Status is "idle" (not "requested"), agent is null
      // onFinish should NOT change anything
      await act(async () => {
        finishCallback?.();
      });

      // Status should still be idle, Save should be shown
      expect(screen.getByText("Save")).toBeInTheDocument();
      expect(screen.queryByText("Saving...")).not.toBeInTheDocument();
    });
  });

  // =========================================================================
  // handleSaveAgent error with non-Error throw
  // =========================================================================

  describe("handleSaveAgent non-Error throw", () => {
    test("shows String(error) toast when save rejects with non-Error", async () => {
      mockSendMessage
        .mockResolvedValueOnce(undefined) // bootstrap
        .mockRejectedValueOnce("raw string error"); // save

      await goToChatStep("non-error-save-agent");

      const saveItem = screen.getByText("Save");
      await act(async () => {
        fireEvent.click(saveItem);
      });

      expect(mockedToast.error).toHaveBeenCalledWith("raw string error");
      // Status should be back to idle
      expect(screen.getByText("Save")).toBeInTheDocument();
    });
  });

  // =========================================================================
  // Back Button Navigation
  // =========================================================================

  describe("Back button navigation", () => {
    test("back button navigates to agents list", () => {
      renderPage();
      const backBtn = document.querySelector(
        "header button[data-variant='ghost']",
      );
      expect(backBtn).toBeTruthy();
      fireEvent.click(backBtn!);
      expect(mockPush).toHaveBeenCalledWith("/workspace/agents");
    });
  });

  // =========================================================================
  // Edge Cases
  // =========================================================================

  describe("Edge cases", () => {
    test("multiple rapid clicks on continue do not cause errors", async () => {
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "rapid-agent" } });

      fireEvent.click(getContinueButton());
      fireEvent.click(getContinueButton());
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(mockedCheckAgentName).toHaveBeenCalled();
    });

    test("enter key and click both trigger confirm", async () => {
      renderPage();
      const input = getNameInput();
      fireEvent.change(input, { target: { value: "dual-trigger" } });

      fireEvent.keyDown(input, { key: "Enter" });
      await act(async () => {});

      expect(mockedCheckAgentName).toHaveBeenCalledWith("dual-trigger");
    });

    test("empty name with only spaces does not proceed to chat", async () => {
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "     " } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(screen.getByText("Name Your Agent")).toBeInTheDocument();
      expect(screen.queryByTestId("message-list")).not.toBeInTheDocument();
    });

    test("single character name is valid", async () => {
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "a" } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(mockedCheckAgentName).toHaveBeenCalledWith("a");
    });

    test("long valid name is accepted", async () => {
      const longName = "a".repeat(64);
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: longName } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(mockedCheckAgentName).toHaveBeenCalledWith(longName);
    });
  });

  // =========================================================================
  // Loading State
  // =========================================================================

  describe("Loading state", () => {
    test("prompt textarea is disabled when thread is loading", async () => {
      threadIsLoading = true;
      await goToChatStep("loading-agent");

      const textarea = screen.getByTestId("prompt-textarea");
      expect(textarea).toBeDisabled();
    });

    test("submit button is disabled when thread is loading", async () => {
      threadIsLoading = true;
      await goToChatStep("loading-agent2");

      const submitBtn = screen.getByTestId("prompt-submit-btn");
      expect(submitBtn).toBeDisabled();
    });

    test("prompt textarea is enabled when not loading", async () => {
      await goToChatStep("not-loading-agent");

      const textarea = screen.getByTestId("prompt-textarea");
      expect(textarea).not.toBeDisabled();
    });

    test("submit button is enabled when not loading", async () => {
      await goToChatStep("not-loading-agent2");

      const submitBtn = screen.getByTestId("prompt-submit-btn");
      expect(submitBtn).not.toBeDisabled();
    });
  });

  // =========================================================================
  // NAME_RE regex edge cases
  // =========================================================================

  describe("NAME_RE regex validation", () => {
    const validNames = [
      "a",
      "A",
      "abc",
      "ABC",
      "abc123",
      "a-b",
      "a-b-c",
      "123",
      "---",
      "AbCdEf",
      "x9z",
    ];

    const invalidNames = [
      "a b",
      "a_b",
      "a.b",
      "a@b",
      "a!b",
      "a#b",
      "a$b",
      "a%b",
    ];

    validNames.forEach((name) => {
      test(`"${name}" is a valid agent name`, async () => {
        renderPage();
        fireEvent.change(getNameInput(), { target: { value: name } });
        fireEvent.click(getContinueButton());

        await act(async () => {});
        expect(mockedCheckAgentName).toHaveBeenCalledWith(name);
        expect(screen.queryByText("Invalid name")).not.toBeInTheDocument();
      });
    });

    invalidNames.forEach((name) => {
      test(`"${name}" is an invalid agent name`, async () => {
        renderPage();
        fireEvent.change(getNameInput(), { target: { value: name } });
        fireEvent.click(getContinueButton());

        await act(async () => {});
        expect(screen.getByText("Invalid name")).toBeInTheDocument();
      });
    });

    test("empty string is handled as empty (no error shown)", async () => {
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "" } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(screen.queryByText("Invalid name")).not.toBeInTheDocument();
    });

    test("whitespace-only is handled as empty (no error shown)", async () => {
      renderPage();
      fireEvent.change(getNameInput(), { target: { value: "   " } });
      fireEvent.click(getContinueButton());

      await act(async () => {});
      expect(screen.queryByText("Invalid name")).not.toBeInTheDocument();
    });
  });

  // =========================================================================
  // SetupAgentStatus state machine
  // =========================================================================

  describe("SetupAgentStatus state transitions", () => {
    test("idle -> requested -> completed via save and toolEnd", async () => {
      mockedGetAgent.mockResolvedValue({
        name: "status-agent",
        config: {},
      } as any);

      await goToChatStep("status-agent");

      // Initially idle - "Save" text
      expect(screen.getByText("Save")).toBeInTheDocument();

      // Click save -> requested -> "Saving..."
      const saveItem = screen.getByText("Save");
      await act(async () => {
        fireEvent.click(saveItem);
      });
      expect(screen.getByText("Saving...")).toBeInTheDocument();

      // onToolEnd -> completed -> agent created
      await act(async () => {
        toolEndCallback?.({ name: "setup_agent" });
      });
      await act(async () => {});

      expect(screen.getByText("Agent created")).toBeInTheDocument();
    });

    test("idle -> requested -> idle (onFinish resets when no agent)", async () => {
      await goToChatStep("reset-agent");

      const saveItem = screen.getByText("Save");
      await act(async () => {
        fireEvent.click(saveItem);
      });
      expect(screen.getByText("Saving...")).toBeInTheDocument();

      // onFinish resets to idle
      await act(async () => {
        finishCallback?.();
      });
      expect(screen.getByText("Save")).toBeInTheDocument();
    });
  });

  // =========================================================================
  // getAgentWithRetry behavior
  // =========================================================================

  describe("getAgentWithRetry", () => {
    // The retry delays are [200, 500, 1000, 2000]. We advance timers
    // step-by-step with act() between each so microtasks (promise
    // resolutions from `await wait(delay)`) are flushed before the
    // next setTimeout is created.
    const RETRY_DELAYS_MS = [200, 500, 1000, 2000];

    async function advanceThroughRetries() {
      for (const delay of RETRY_DELAYS_MS) {
        await act(async () => {
          vi.advanceTimersByTime(delay);
        });
      }
    }

    test("retries on failure and eventually succeeds", async () => {
      vi.useFakeTimers();
      try {
        mockedGetAgent
          .mockRejectedValueOnce(new Error("fail 1"))
          .mockRejectedValueOnce(new Error("fail 2"))
          .mockResolvedValueOnce({
            name: "retry-agent",
            config: {},
          } as any);

        await goToChatStep("retry-agent");

        await act(async () => {
          toolEndCallback?.({ name: "setup_agent" });
        });

        await advanceThroughRetries();

        expect(screen.getByText("Agent created")).toBeInTheDocument();
      } finally {
        vi.useRealTimers();
      }
    }, 10000);

    test("returns null and shows toast after all retries fail", async () => {
      vi.useFakeTimers();
      try {
        mockedGetAgent.mockRejectedValue(new Error("always fail"));

        await goToChatStep("fail-retry-agent");

        await act(async () => {
          toolEndCallback?.({ name: "setup_agent" });
        });

        await advanceThroughRetries();

        expect(mockedToast.error).toHaveBeenCalledWith("Pending refresh");
      } finally {
        vi.useRealTimers();
      }
    }, 10000);

    test("getAgentWithRetry calls getAgent multiple times on failure", async () => {
      vi.useFakeTimers();
      try {
        mockedGetAgent.mockRejectedValue(new Error("fail"));

        await goToChatStep("multi-retry-agent");

        await act(async () => {
          toolEndCallback?.({ name: "setup_agent" });
        });

        await advanceThroughRetries();

        // Initial call + 4 retries = 5 total
        expect(mockedGetAgent).toHaveBeenCalledTimes(5);
      } finally {
        vi.useRealTimers();
      }
    }, 10000);
  });

  // =========================================================================
  // Save menu item disabled conditions
  // =========================================================================

  describe("Save menu item disabled conditions", () => {
    test("save is disabled when agent already exists", async () => {
      mockedGetAgent.mockResolvedValue({
        name: "exists-agent",
        config: {},
      } as any);

      await goToChatStep("exists-agent");

      await act(async () => {
        toolEndCallback?.({ name: "setup_agent" });
      });
      await act(async () => {});

      // After agent created, the save dropdown item should be disabled
      const saveItem = document.querySelector("[data-disabled='true']");
      expect(saveItem).toBeInTheDocument();
    });

    test("save is NOT disabled when agent does not exist and not loading", async () => {
      await goToChatStep("not-disabled-agent");

      const saveItem = screen.getByText("Save").closest("[data-disabled]");
      expect(saveItem).toHaveAttribute("data-disabled", "false");
    });
  });
});
