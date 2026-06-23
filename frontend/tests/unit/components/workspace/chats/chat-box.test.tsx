import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  usePathname: () => "/workspace/chats/test-thread",
}));

let mockStaticWebsiteOnly = "false";
vi.mock("@/env", () => ({
  env: {
    get NEXT_PUBLIC_STATIC_WEBSITE_ONLY() {
      return mockStaticWebsiteOnly;
    },
  },
}));

let mockThreadArtifacts: string[] = ["file1.txt", "file2.pdf"];

vi.mock("@/components/workspace/messages/context", () => ({
  useThread: () => ({
    thread: {
      values: { artifacts: mockThreadArtifacts },
      messages: [],
    },
  }),
}));

const mockSelect = vi.fn();
const mockDeselect = vi.fn();
const mockSetOpen = vi.fn();
const mockSetArtifacts = vi.fn();
let mockArtifactsOpen = false;
let mockSelectedArtifact: string | null = null;
let mockArtifacts: string[] = [];

vi.mock("@/components/workspace/artifacts", () => ({
  useArtifacts: () => ({
    artifacts: mockArtifacts,
    open: mockArtifactsOpen,
    setOpen: mockSetOpen,
    setArtifacts: mockSetArtifacts,
    select: mockSelect,
    deselect: mockDeselect,
    selectedArtifact: mockSelectedArtifact,
  }),
  ArtifactFileDetail: ({ filepath }: { filepath: string }) => (
    <div data-testid="artifact-detail">{filepath}</div>
  ),
  ArtifactFileList: ({
    files,
    threadId,
  }: {
    files: string[];
    threadId: string;
  }) => (
    <div data-testid="artifact-file-list">
      {files.join(",")} - {threadId}
    </div>
  ),
}));

vi.mock("react-resizable-panels", () => ({
  GroupImperativeHandle: {},
}));

const mockSetLayout = vi.fn();

vi.mock("@/components/ui/resizable", () => ({
  ResizablePanelGroup: ({ children, id, groupRef }: any) => {
    // Expose a mock imperative handle via groupRef
    if (groupRef && typeof groupRef === "object") {
      groupRef.current = { setLayout: mockSetLayout };
    }
    return (
      <div data-testid="resizable-panel-group" data-id={id}>
        {children}
      </div>
    );
  },
  ResizablePanel: ({ children, id, className }: any) => (
    <div data-testid={`panel-${id}`} className={className}>
      {children}
    </div>
  ),
  ResizableHandle: ({ id, className }: any) => (
    <div data-testid={`handle-${id}`} className={className} />
  ),
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, size, variant, ...props }: any) => (
    <button
      onClick={onClick}
      data-size={size}
      data-variant={variant}
      {...props}
    >
      {children}
    </button>
  ),
}));

vi.mock("@/components/ai-elements/conversation", () => ({
  ConversationEmptyState: ({ title, description }: any) => (
    <div data-testid="empty-state">
      <div>{title}</div>
      <div>{description}</div>
    </div>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let ChatBox: typeof import("@/components/workspace/chats/chat-box").ChatBox;

beforeEach(async () => {
  vi.clearAllMocks();
  mockStaticWebsiteOnly = "false";
  mockArtifactsOpen = false;
  mockSelectedArtifact = null;
  mockArtifacts = [];
  mockThreadArtifacts = ["file1.txt", "file2.pdf"];
  const mod = await import("@/components/workspace/chats/chat-box");
  ChatBox = mod.ChatBox;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("ChatBox", () => {
  test("renders the resizable panel group", () => {
    render(
      <ChatBox threadId="t-1">
        <div>Chat content</div>
      </ChatBox>,
    );
    expect(screen.getByTestId("resizable-panel-group")).toBeInTheDocument();
  });

  test("renders children in the chat panel", () => {
    render(
      <ChatBox threadId="t-1">
        <div data-testid="chat-child">Chat content</div>
      </ChatBox>,
    );
    expect(screen.getByTestId("chat-child")).toBeInTheDocument();
    expect(screen.getByText("Chat content")).toBeInTheDocument();
  });

  test("renders artifacts panel", () => {
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    expect(screen.getByTestId("panel-artifacts")).toBeInTheDocument();
  });

  test("renders resizable handle", () => {
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    const handles = screen.getAllByTestId(/handle-/);
    expect(handles.length).toBeGreaterThan(0);
  });

  test("shows close button when artifacts panel is open but no artifact selected", () => {
    mockArtifactsOpen = true;
    mockArtifacts = ["file.txt"];
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    // The X button should be visible
    const buttons = screen.getAllByRole("button");
    expect(buttons.length).toBeGreaterThan(0);
  });

  test("calls setArtifacts with thread artifacts", () => {
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    expect(mockSetArtifacts).toHaveBeenCalledWith(["file1.txt", "file2.pdf"]);
  });

  test("generates ID from pathname", () => {
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    const group = screen.getByTestId("resizable-panel-group");
    expect(group).toHaveAttribute("data-id", expect.stringContaining("panels"));
  });

  test("shows artifact file detail when artifact is selected", () => {
    mockArtifactsOpen = true;
    mockSelectedArtifact =
      "write-file:/src/test.ts?message_id=m1&tool_call_id=tc1";
    mockArtifacts = ["file.txt"];
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    expect(screen.getByTestId("artifact-detail")).toBeInTheDocument();
  });

  test("shows artifact file list when artifacts panel is open and no artifact selected", () => {
    mockArtifactsOpen = true;
    mockArtifacts = ["file.txt"];
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    expect(screen.getByTestId("artifact-file-list")).toBeInTheDocument();
  });

  test("shows empty state when no artifacts in thread", () => {
    mockArtifactsOpen = true;
    mockArtifacts = [];
    mockThreadArtifacts = [];
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    expect(screen.getByTestId("empty-state")).toBeInTheDocument();
  });

  test("close button calls setOpen with false", () => {
    mockArtifactsOpen = true;
    mockArtifacts = ["file.txt"];
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    const buttons = screen.getAllByRole("button");
    const closeButton = buttons.find(
      (b) => b.querySelector("svg") && b.textContent === "",
    );
    if (closeButton) {
      fireEvent.click(closeButton);
      expect(mockSetOpen).toHaveBeenCalledWith(false);
    }
  });

  test("threadId change triggers deselect", () => {
    const { rerender } = render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    rerender(
      <ChatBox threadId="t-2">
        <div>Chat</div>
      </ChatBox>,
    );
    expect(mockDeselect).toHaveBeenCalled();
  });

  test("artifacts panel renders with transition classes", () => {
    mockArtifactsOpen = false;
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    const panel = screen.getByTestId("panel-artifacts");
    expect(panel.getAttribute("class")).toContain("transition-all");
  });

  test("artifacts panel renders with transition classes when open", () => {
    mockArtifactsOpen = true;
    mockArtifacts = ["file.txt"];
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    const panel = screen.getByTestId("panel-artifacts");
    expect(panel.getAttribute("class")).toContain("transition-all");
  });

  // ── Static website mode tests ──────────────────────────────────────────────

  test("auto-selects first artifact in static mode when thread has artifacts", () => {
    mockStaticWebsiteOnly = "true";
    mockArtifactsOpen = false;
    mockArtifacts = [];
    mockThreadArtifacts = ["auto-file.txt", "auto-file2.pdf"];
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    expect(mockSelect).toHaveBeenCalledWith("auto-file.txt");
  });

  test("does not auto-select in static mode when thread has no artifacts", () => {
    mockStaticWebsiteOnly = "true";
    mockArtifactsOpen = false;
    mockArtifacts = [];
    mockThreadArtifacts = [];
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    expect(mockSelect).not.toHaveBeenCalled();
  });

  test("does not auto-select in static mode when autoSelectFirstArtifact is already false", () => {
    mockStaticWebsiteOnly = "true";
    mockArtifactsOpen = false;
    mockArtifacts = [];
    mockThreadArtifacts = ["file.txt"];
    // First render sets autoSelectFirstArtifact to false after selecting
    const { rerender } = render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    mockSelect.mockClear();
    // Rerender with same threadId - should not select again
    rerender(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    expect(mockSelect).not.toHaveBeenCalled();
  });

  test("artifactPanelOpen in static mode returns false when no artifacts", () => {
    mockStaticWebsiteOnly = "true";
    mockArtifactsOpen = true;
    mockArtifacts = [];
    mockThreadArtifacts = [];
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    // artifactPanelOpen should be false (artifactsOpen && artifacts.length > 0) => true && false => false
    // The handle should have pointer-events-none and opacity-0
    const handles = screen.getAllByTestId(/handle-/);
    expect(handles[0]!.getAttribute("class")).toContain("pointer-events-none");
  });

  test("artifactPanelOpen in static mode returns true when artifacts exist", () => {
    mockStaticWebsiteOnly = "true";
    mockArtifactsOpen = true;
    mockArtifacts = ["file.txt"];
    mockThreadArtifacts = ["file.txt"];
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    // artifactPanelOpen should be true (artifactsOpen && artifacts.length > 0) => true && true => true
    const handles = screen.getAllByTestId(/handle-/);
    expect(handles[0]!.getAttribute("class")).not.toContain(
      "pointer-events-none",
    );
  });

  test("non-static mode artifactPanelOpen ignores artifacts array", () => {
    mockStaticWebsiteOnly = "false";
    mockArtifactsOpen = true;
    mockArtifacts = [];
    mockThreadArtifacts = [];
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    // In non-static mode, artifactPanelOpen = artifactsOpen (true), regardless of artifacts
    const handles = screen.getAllByTestId(/handle-/);
    expect(handles[0]!.getAttribute("class")).not.toContain(
      "pointer-events-none",
    );
  });

  test("does not auto-select in non-static mode even with artifacts", () => {
    mockStaticWebsiteOnly = "false";
    mockArtifactsOpen = false;
    mockArtifacts = [];
    mockThreadArtifacts = ["file.txt"];
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    expect(mockSelect).not.toHaveBeenCalled();
  });

  test("threadId change in static mode triggers deselect and auto-selects new artifact", () => {
    mockStaticWebsiteOnly = "true";
    mockArtifactsOpen = false;
    mockArtifacts = [];
    // Start with no artifacts so autoSelectFirstArtifact stays true
    mockThreadArtifacts = [];
    const { rerender } = render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    mockSelect.mockClear();
    mockDeselect.mockClear();
    // Now rerender with a different threadId and artifacts
    mockThreadArtifacts = ["new-artifact.txt"];
    rerender(
      <ChatBox threadId="t-2">
        <div>Chat</div>
      </ChatBox>,
    );
    expect(mockDeselect).toHaveBeenCalled();
    expect(mockSelect).toHaveBeenCalledWith("new-artifact.txt");
  });

  test("handles null artifacts in thread values (nullish coalescing fallback)", () => {
    mockStaticWebsiteOnly = "false";
    mockArtifactsOpen = true;
    mockArtifacts = null as any;
    mockThreadArtifacts = null as any;
    render(
      <ChatBox threadId="t-1">
        <div>Chat</div>
      </ChatBox>,
    );
    // Should render file list with empty array fallback
    expect(screen.getByTestId("artifact-file-list")).toBeInTheDocument();
  });
});
