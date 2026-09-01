import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/styles/globals.css", () => ({}));
vi.mock("katex/dist/katex.min.css", () => ({}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en",
    t: {
      common: { loading: "Loading..." },
      agents: {
        createPageTitle: "Create Agent",
        createPageSubtitle: "Describe your agent...",
        nameStepTitle: "Name Your Agent",
        nameStepHint: "Choose a unique name",
        nameStepPlaceholder: "agent-name",
        nameStepContinue: "Continue",
        nameStepInvalidError: "Invalid name format",
        nameStepAlreadyExistsError: "Name already exists",
        nameStepNetworkError: "Network error",
        nameStepCheckError: "Check failed",
        nameStepBootstrapMessage: "Create agent {name}",
        visibility: "可见性",
        visibilityPrivate: "私有",
        visibilityDepartment: "部门共享",
        visibilityPublic: "公开",
        visibilityAdminOnly: "部门共享和公开选项仅管理员可用",
        saveHint: "Save hint message",
        saveCommandMessage: "save",
        saveRequested: "Save requested",
        saving: "Saving...",
        save: "Save",
        more: "More",
        agentCreated: "Agent Created",
        startChatting: "Start Chatting",
        backToGallery: "Back to Gallery",
        agentCreatedPendingRefresh: "Agent created, pending refresh",
      },
    },
  }),
}));

vi.mock("@/core/agents/api", () => ({
  checkAgentName: vi.fn().mockResolvedValue({ available: true }),
  getAgent: vi.fn().mockResolvedValue(null),
  AgentNameCheckError: class extends Error {
    reason: string;
    constructor(reason: string) {
      super("Name check error");
      this.reason = reason;
    }
  },
}));

vi.mock("@/core/agents", () => ({
  useAgent: () => ({
    agent: null,
    isLoading: false,
    error: null,
  }),
}));

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: () => ({
    user: null,
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
}));

vi.mock("@/core/utils/uuid", () => ({
  uuid: () => "mock-uuid-123",
}));

vi.mock("@/lib/ime", () => ({
  isIMEComposing: () => false,
}));

vi.mock("@/lib/utils", () => ({
  cn: (...args: any[]) => args.filter(Boolean).join(" "),
}));

vi.mock("@/components/ai-elements/prompt-input", () => ({
  PromptInput: ({ children, onSubmit }: any) => (
    <div data-testid="prompt-input">{children}</div>
  ),
  PromptInputFooter: ({ children }: any) => <div>{children}</div>,
  PromptInputSubmit: (props: any) => (
    <button data-testid="prompt-submit">Submit</button>
  ),
  PromptInputTextarea: (props: any) => (
    <textarea data-testid="prompt-textarea" />
  ),
}));

vi.mock("@/components/ui/alert", () => ({
  Alert: ({ children }: any) => <div data-testid="alert">{children}</div>,
  AlertDescription: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, variant, onClick, disabled }: any) => (
    <button
      data-testid="button"
      data-variant={variant}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  ),
}));

vi.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: any) => (
    <div data-testid="dropdown-menu">{children}</div>
  ),
  DropdownMenuContent: ({ children }: any) => <div>{children}</div>,
  DropdownMenuItem: ({ children, disabled, onSelect }: any) => (
    <button
      disabled={disabled}
      onClick={onSelect}
      data-testid="dropdown-menu-item"
    >
      {children}
    </button>
  ),
  DropdownMenuTrigger: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("@/components/ui/input", () => ({
  Input: (props: any) => (
    <input
      data-testid="agent-name-input"
      placeholder={props.placeholder}
      value={props.value}
      onChange={props.onChange}
      onKeyDown={props.onKeyDown}
      className={props.className}
      autoFocus={props.autoFocus}
    />
  ),
}));

vi.mock("@/components/ui/label", () => ({
  Label: ({ children, ...props }: any) => (
    <label data-testid="label" {...props}>
      {children}
    </label>
  ),
}));

vi.mock("@/components/ui/select", () => ({
  Select: ({ children, value, onValueChange }: any) => (
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
  SelectTrigger: ({ children, id }: any) => (
    <div data-testid="select-trigger">{children}</div>
  ),
  SelectValue: () => <span />,
}));

vi.mock("@/components/workspace/artifacts", () => ({
  ArtifactsProvider: ({ children }: any) => (
    <div data-testid="artifacts-provider">{children}</div>
  ),
}));

vi.mock("@/components/workspace/messages", () => ({
  MessageList: () => <div data-testid="message-list" />,
}));

vi.mock("@/components/workspace/messages/context", () => ({
  ThreadContext: {
    Provider: ({ children }: any) => (
      <div data-testid="thread-context">{children}</div>
    ),
  },
}));

import NewAgentPage from "@/app/workspace/capabilities/experts/new/page";

afterEach(() => {
  vi.clearAllMocks();
});

describe("NewAgentPage", () => {
  test("renders create agent title", () => {
    render(<NewAgentPage />);
    expect(screen.getByText("Create Agent")).toBeInTheDocument();
  });

  test("renders back button", () => {
    render(<NewAgentPage />);
    const buttons = screen.getAllByTestId("button");
    expect(buttons.length).toBeGreaterThan(0);
  });

  test("renders agent name input", () => {
    render(<NewAgentPage />);
    expect(screen.getByTestId("agent-name-input")).toBeInTheDocument();
  });

  test("renders name step title", () => {
    render(<NewAgentPage />);
    expect(screen.getByText("Name Your Agent")).toBeInTheDocument();
  });

  test("renders name step hint", () => {
    render(<NewAgentPage />);
    expect(screen.getByText("Choose a unique name")).toBeInTheDocument();
  });

  test("renders continue button", () => {
    render(<NewAgentPage />);
    const buttons = screen.getAllByTestId("button");
    const continueBtn = buttons.find((b) =>
      b.textContent?.includes("Continue"),
    );
    expect(continueBtn).toBeDefined();
    expect(continueBtn!.textContent).toMatch(/Continue/i);
  });

  test("renders visibility select", () => {
    render(<NewAgentPage />);
    expect(screen.getByTestId("select")).toBeInTheDocument();
  });

  test("renders visibility options", () => {
    render(<NewAgentPage />);
    expect(screen.getByText("私有")).toBeInTheDocument();
  });

  test("shows admin hint for non-admin users", () => {
    render(<NewAgentPage />);
    expect(
      screen.getByText(/部门共享和公开选项仅管理员可用/),
    ).toBeInTheDocument();
  });
});
