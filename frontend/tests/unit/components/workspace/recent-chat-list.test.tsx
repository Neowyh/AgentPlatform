import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

// next/link
vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

// next/navigation
const mockPush = vi.fn();
let mockPathname = "/workspace/chats/thread-1";
let mockParams: Record<string, string> = {
  thread_id: "thread-1",
};
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => mockPathname,
  useParams: () => mockParams,
}));

// sonner
const mockToastSuccess = vi.fn();
const mockToastError = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => mockToastSuccess(...args),
    error: (...args: unknown[]) => mockToastError(...args),
  },
}));

// Sidebar components – lightweight passthrough
vi.mock("@/components/ui/sidebar", () => ({
  SidebarGroup: ({ children, ...props }: { children: React.ReactNode }) => (
    <div {...props}>{children}</div>
  ),
  SidebarGroupLabel: ({
    children,
    ...props
  }: {
    children: React.ReactNode;
  }) => <div {...props}>{children}</div>,
  SidebarGroupContent: ({
    children,
    ...props
  }: {
    children: React.ReactNode;
  }) => <div {...props}>{children}</div>,
  SidebarMenu: ({ children, ...props }: { children: React.ReactNode }) => (
    <div {...props}>{children}</div>
  ),
  SidebarMenuItem: ({ children, ...props }: { children: React.ReactNode }) => (
    <div {...props}>{children}</div>
  ),
  SidebarMenuButton: ({
    children,
    isActive,
    asChild,
    ...props
  }: {
    children: React.ReactNode;
    isActive?: boolean;
    asChild?: boolean;
  }) => (
    <div data-active={isActive} {...props}>
      {children}
    </div>
  ),
  SidebarMenuAction: ({
    children,
    ...props
  }: {
    children: React.ReactNode;
  }) => <button {...props}>{children}</button>,
}));

// Dialog
vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({
    children,
    open,
  }: {
    children: React.ReactNode;
    open?: boolean;
  }) => (open ? <div data-testid="dialog">{children}</div> : null),
  DialogContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dialog-content">{children}</div>
  ),
  DialogHeader: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DialogTitle: ({ children }: { children: React.ReactNode }) => (
    <h2>{children}</h2>
  ),
  DialogFooter: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

// DropdownMenu
vi.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dropdown-menu">{children}</div>
  ),
  DropdownMenuTrigger: ({
    children,
    asChild,
    ...props
  }: {
    children: React.ReactNode;
    asChild?: boolean;
  }) => (
    <div data-testid="dropdown-trigger" {...props}>
      {children}
    </div>
  ),
  DropdownMenuContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dropdown-content">{children}</div>
  ),
  DropdownMenuItem: ({
    children,
    onSelect,
    ...props
  }: {
    children: React.ReactNode;
    onSelect?: () => void;
  }) => (
    <button role="menuitem" onClick={onSelect} {...props}>
      {children}
    </button>
  ),
  DropdownMenuSeparator: () => <hr data-testid="separator" />,
  DropdownMenuSub: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DropdownMenuSubTrigger: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DropdownMenuSubContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

// Input
vi.mock("@/components/ui/input", () => ({
  Input: ({ ...props }: Record<string, unknown>) => (
    <input data-testid="rename-input" {...props} />
  ),
}));

// Button
vi.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    ...props
  }: {
    children: React.ReactNode;
    [key: string]: unknown;
  }) => <button {...props}>{children}</button>,
}));

// i18n
const mockT = {
  sidebar: {
    recentChats: "Recent Chats",
    demoChats: "Demo Chats",
  },
  common: {
    more: "More",
    rename: "Rename",
    share: "Share",
    export: "Export",
    exportAsMarkdown: "Export as Markdown",
    exportAsJSON: "Export as JSON",
    delete: "Delete",
    cancel: "Cancel",
    save: "Save",
    exportSuccess: "Export successful",
  },
  conversation: {
    noMessages: "No messages to export",
  },
  clipboard: {
    linkCopied: "Link copied",
    failedToCopyToClipboard: "Failed to copy",
  },
};
vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: mockT,
    changeLocale: vi.fn(),
  }),
}));

// Thread hooks
const mockDeleteMutate = vi.fn();
const mockRenameMutate = vi.fn();
let mockThreads: Array<{
  thread_id: string;
  values?: { title?: string };
  context?: { agent_name?: string };
}> = [];

vi.mock("@/core/threads/hooks", () => ({
  useThreads: () => ({ data: mockThreads }),
  useDeleteThread: () => ({ mutate: mockDeleteMutate }),
  useRenameThread: () => ({ mutate: mockRenameMutate }),
}));

// Thread utils
vi.mock("@/core/threads/utils", () => ({
  pathOfThread: (
    thread: { thread_id: string; context?: { agent_name?: string } } | string,
    ctx?: { agent_name?: string },
  ) => {
    if (typeof thread === "string") {
      const agentName = ctx?.agent_name;
      return agentName
        ? `/workspace/capabilities/experts/${agentName}/chats/${thread}`
        : `/workspace/chats/${thread}`;
    }
    const agentName = thread.context?.agent_name;
    return agentName
      ? `/workspace/capabilities/experts/${agentName}/chats/${thread.thread_id}`
      : `/workspace/chats/${thread.thread_id}`;
  },
  titleOfThread: (thread: { values?: { title?: string }; thread_id: string }) =>
    thread.values?.title ?? "Untitled",
}));

// clipboard
const mockWriteTextToClipboard = vi.fn();
vi.mock("@/core/clipboard", () => ({
  writeTextToClipboard: (...args: unknown[]) =>
    mockWriteTextToClipboard(...args),
}));

// export
const mockExportMarkdown = vi.fn();
const mockExportJSON = vi.fn();
vi.mock("@/core/threads/export", () => ({
  exportThreadAsMarkdown: (...args: unknown[]) => mockExportMarkdown(...args),
  exportThreadAsJSON: (...args: unknown[]) => mockExportJSON(...args),
}));

// API client
const mockGetState = vi.fn();
vi.mock("@/core/api", () => ({
  getAPIClient: () => ({
    threads: {
      getState: (...args: unknown[]) => mockGetState(...args),
    },
  }),
}));

// env
vi.mock("@/env", () => ({
  env: {
    NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false",
  },
}));

// ime util
vi.mock("@/lib/ime", () => ({
  isIMEComposing: () => false,
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let RecentChatList: typeof import("@/components/workspace/recent-chat-list").RecentChatList;

beforeEach(async () => {
  vi.clearAllMocks();
  mockThreads = [];
  mockPathname = "/workspace/chats/thread-1";
  mockParams = { thread_id: "thread-1" };
  mockWriteTextToClipboard.mockResolvedValue(true);
  mockGetState.mockResolvedValue({
    values: {
      messages: [
        { type: "human", content: "hello" },
        { type: "ai", content: "hi" },
      ],
    },
  });
  const mod = await import("@/components/workspace/recent-chat-list");
  RecentChatList = mod.RecentChatList;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("RecentChatList", () => {
  // ── Empty state ──────────────────────────────────────────────────────────

  test("returns null when there are no threads", () => {
    mockThreads = [];
    const { container } = render(<RecentChatList />);
    expect(container.firstChild).toBeNull();
  });

  // ── Thread rendering ─────────────────────────────────────────────────────

  test("renders thread list when threads exist", () => {
    mockThreads = [
      { thread_id: "t1", values: { title: "Chat One" } },
      { thread_id: "t2", values: { title: "Chat Two" } },
    ];
    render(<RecentChatList />);
    expect(screen.getByTestId("thread-list")).toBeInTheDocument();
    expect(screen.getByText("Chat One")).toBeInTheDocument();
    expect(screen.getByText("Chat Two")).toBeInTheDocument();
  });

  test("renders 'Untitled' for threads without a title", () => {
    mockThreads = [{ thread_id: "t1" }];
    render(<RecentChatList />);
    expect(screen.getByText("Untitled")).toBeInTheDocument();
  });

  test("shows 'Recent Chats' label", () => {
    mockThreads = [{ thread_id: "t1", values: { title: "Chat" } }];
    render(<RecentChatList />);
    expect(screen.getByText("Recent Chats")).toBeInTheDocument();
  });

  test("links each thread to its path", () => {
    mockThreads = [
      { thread_id: "t1", values: { title: "Chat One" } },
      { thread_id: "t2", values: { title: "Chat Two" } },
    ];
    render(<RecentChatList />);
    const links = screen.getAllByText(/Chat (One|Two)/);
    expect(links[0]).toHaveAttribute("href", "/workspace/chats/t1");
    expect(links[1]).toHaveAttribute("href", "/workspace/chats/t2");
  });

  test("marks the active thread based on pathname", () => {
    mockPathname = "/workspace/chats/t2";
    mockThreads = [
      { thread_id: "t1", values: { title: "Chat One" } },
      { thread_id: "t2", values: { title: "Chat Two" } },
    ];
    render(<RecentChatList />);
    const threadItems = screen.getAllByTestId("thread-item");
    // The second item should have an active child
    expect(threadItems).toHaveLength(2);
  });

  test("renders the correct number of thread items", () => {
    mockThreads = [
      { thread_id: "t1", values: { title: "A" } },
      { thread_id: "t2", values: { title: "B" } },
      { thread_id: "t3", values: { title: "C" } },
    ];
    render(<RecentChatList />);
    expect(screen.getAllByTestId("thread-item")).toHaveLength(3);
  });

  // ── Delete ───────────────────────────────────────────────────────────────

  test("deletes a thread via the dropdown action", async () => {
    const user = userEvent.setup();
    mockThreads = [
      { thread_id: "t1", values: { title: "Chat One" } },
      { thread_id: "t2", values: { title: "Chat Two" } },
    ];
    mockPathname = "/workspace/chats/t1";
    mockParams = { thread_id: "t1" };
    render(<RecentChatList />);

    // Click the delete action on the first thread
    const deleteButtons = screen.getAllByTestId("thread-delete-action");
    await user.click(deleteButtons[0]!);

    expect(mockDeleteMutate).toHaveBeenCalledWith({ threadId: "t1" });
  });

  test("navigates to next thread after deleting the active thread", async () => {
    const user = userEvent.setup();
    mockThreads = [
      { thread_id: "t1", values: { title: "First" } },
      { thread_id: "t2", values: { title: "Second" } },
    ];
    mockPathname = "/workspace/chats/t1";
    mockParams = { thread_id: "t1" };
    render(<RecentChatList />);

    const deleteButtons = screen.getAllByTestId("thread-delete-action");
    await user.click(deleteButtons[0]!);

    expect(mockPush).toHaveBeenCalledWith("/workspace/chats/t2");
  });

  test("navigates to previous thread when deleting the last thread", async () => {
    const user = userEvent.setup();
    mockThreads = [
      { thread_id: "t1", values: { title: "First" } },
      { thread_id: "t2", values: { title: "Second" } },
    ];
    mockPathname = "/workspace/chats/t2";
    mockParams = { thread_id: "t2" };
    render(<RecentChatList />);

    const deleteButtons = screen.getAllByTestId("thread-delete-action");
    await user.click(deleteButtons[1]!);

    expect(mockPush).toHaveBeenCalledWith("/workspace/chats/t1");
  });

  test("navigates to 'new' when deleting the only thread", async () => {
    const user = userEvent.setup();
    mockThreads = [{ thread_id: "t1", values: { title: "Only" } }];
    mockPathname = "/workspace/chats/t1";
    mockParams = { thread_id: "t1" };
    render(<RecentChatList />);

    const deleteButtons = screen.getAllByTestId("thread-delete-action");
    await user.click(deleteButtons[0]!);

    expect(mockPush).toHaveBeenCalledWith("/workspace/chats/new");
  });

  test("does not navigate when deleting a non-active thread", async () => {
    const user = userEvent.setup();
    mockThreads = [
      { thread_id: "t1", values: { title: "First" } },
      { thread_id: "t2", values: { title: "Second" } },
    ];
    mockPathname = "/workspace/chats/t1";
    mockParams = { thread_id: "t1" };
    render(<RecentChatList />);

    const deleteButtons = screen.getAllByTestId("thread-delete-action");
    await user.click(deleteButtons[1]!);

    expect(mockDeleteMutate).toHaveBeenCalledWith({ threadId: "t2" });
    expect(mockPush).not.toHaveBeenCalled();
  });

  // ── Rename ───────────────────────────────────────────────────────────────

  test("opens rename dialog when rename action is clicked", async () => {
    const user = userEvent.setup();
    mockThreads = [{ thread_id: "t1", values: { title: "My Chat" } }];
    render(<RecentChatList />);

    const renameButtons = screen.getAllByTestId("thread-rename-action");
    await user.click(renameButtons[0]!);

    await waitFor(() => {
      expect(screen.getByTestId("dialog")).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue("My Chat")).toBeInTheDocument();
  });

  test("submits rename with trimmed value", async () => {
    const user = userEvent.setup();
    mockThreads = [{ thread_id: "t1", values: { title: "Old" } }];
    render(<RecentChatList />);

    // Open rename dialog
    const renameButtons = screen.getAllByTestId("thread-rename-action");
    await user.click(renameButtons[0]!);

    await waitFor(() => {
      expect(screen.getByTestId("rename-input")).toBeInTheDocument();
    });

    // Clear and type new name
    const input = screen.getByTestId("rename-input");
    await user.clear(input);
    await user.type(input, "  New Title  ");

    // Click save
    const saveButton = screen.getByText("Save");
    await user.click(saveButton);

    expect(mockRenameMutate).toHaveBeenCalledWith({
      threadId: "t1",
      title: "New Title",
    });
  });

  test("does not submit rename when value is empty", async () => {
    const user = userEvent.setup();
    mockThreads = [{ thread_id: "t1", values: { title: "Old" } }];
    render(<RecentChatList />);

    const renameButtons = screen.getAllByTestId("thread-rename-action");
    await user.click(renameButtons[0]!);

    await waitFor(() => {
      expect(screen.getByTestId("rename-input")).toBeInTheDocument();
    });

    const input = screen.getByTestId("rename-input");
    await user.clear(input);

    const saveButton = screen.getByText("Save");
    await user.click(saveButton);

    expect(mockRenameMutate).not.toHaveBeenCalled();
  });

  test("closes rename dialog when cancel is clicked", async () => {
    const user = userEvent.setup();
    mockThreads = [{ thread_id: "t1", values: { title: "Chat" } }];
    render(<RecentChatList />);

    const renameButtons = screen.getAllByTestId("thread-rename-action");
    await user.click(renameButtons[0]!);

    await waitFor(() => {
      expect(screen.getByTestId("dialog")).toBeInTheDocument();
    });

    const cancelButton = screen.getByText("Cancel");
    await user.click(cancelButton);

    await waitFor(() => {
      expect(screen.queryByTestId("dialog")).not.toBeInTheDocument();
    });
  });

  test("submits rename on Enter key press", async () => {
    const user = userEvent.setup();
    mockThreads = [{ thread_id: "t1", values: { title: "Old" } }];
    render(<RecentChatList />);

    const renameButtons = screen.getAllByTestId("thread-rename-action");
    await user.click(renameButtons[0]!);

    await waitFor(() => {
      expect(screen.getByTestId("rename-input")).toBeInTheDocument();
    });

    const input = screen.getByTestId("rename-input");
    await user.clear(input);
    await user.type(input, "New Name");
    await user.keyboard("{Enter}");

    expect(mockRenameMutate).toHaveBeenCalledWith({
      threadId: "t1",
      title: "New Name",
    });
  });

  // ── Share ────────────────────────────────────────────────────────────────

  test("copies share URL to clipboard", async () => {
    const user = userEvent.setup();
    mockThreads = [{ thread_id: "t1", values: { title: "Chat" } }];
    render(<RecentChatList />);

    // Find and click the share menu item
    const shareItem = screen.getByText("Share");
    await user.click(shareItem);

    await waitFor(() => {
      expect(mockWriteTextToClipboard).toHaveBeenCalled();
    });
    expect(mockToastSuccess).toHaveBeenCalledWith("Link copied");
  });

  test("shows error toast when clipboard copy fails", async () => {
    const user = userEvent.setup();
    mockWriteTextToClipboard.mockResolvedValue(false);
    mockThreads = [{ thread_id: "t1", values: { title: "Chat" } }];
    render(<RecentChatList />);

    const shareItem = screen.getByText("Share");
    await user.click(shareItem);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("Failed to copy");
    });
  });

  test("shows error toast when clipboard throws", async () => {
    const user = userEvent.setup();
    mockWriteTextToClipboard.mockRejectedValue(new Error("fail"));
    mockThreads = [{ thread_id: "t1", values: { title: "Chat" } }];
    render(<RecentChatList />);

    const shareItem = screen.getByText("Share");
    await user.click(shareItem);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("Failed to copy");
    });
  });

  // ── Export ───────────────────────────────────────────────────────────────

  test("exports thread as markdown", async () => {
    const user = userEvent.setup();
    mockThreads = [{ thread_id: "t1", values: { title: "Chat" } }];
    render(<RecentChatList />);

    const mdItem = screen.getByText("Export as Markdown");
    await user.click(mdItem);

    await waitFor(() => {
      expect(mockGetState).toHaveBeenCalledWith("t1");
    });
    await waitFor(() => {
      expect(mockExportMarkdown).toHaveBeenCalled();
    });
    expect(mockToastSuccess).toHaveBeenCalledWith("Export successful");
  });

  test("exports thread as JSON", async () => {
    const user = userEvent.setup();
    mockThreads = [{ thread_id: "t1", values: { title: "Chat" } }];
    render(<RecentChatList />);

    const jsonItem = screen.getByText("Export as JSON");
    await user.click(jsonItem);

    await waitFor(() => {
      expect(mockExportJSON).toHaveBeenCalled();
    });
    expect(mockToastSuccess).toHaveBeenCalledWith("Export successful");
  });

  test("shows error when no messages to export", async () => {
    const user = userEvent.setup();
    mockGetState.mockResolvedValue({ values: { messages: [] } });
    mockThreads = [{ thread_id: "t1", values: { title: "Chat" } }];
    render(<RecentChatList />);

    const mdItem = screen.getByText("Export as Markdown");
    await user.click(mdItem);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("No messages to export");
    });
  });

  test("shows error toast when export fails", async () => {
    const user = userEvent.setup();
    mockGetState.mockRejectedValue(new Error("network error"));
    mockThreads = [{ thread_id: "t1", values: { title: "Chat" } }];
    render(<RecentChatList />);

    const mdItem = screen.getByText("Export as Markdown");
    await user.click(mdItem);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith(
        "Failed to export conversation",
      );
    });
  });

  // ── Agent name context ───────────────────────────────────────────────────

  test("uses agent_name in path when deleting and navigating to 'new'", async () => {
    const user = userEvent.setup();
    mockThreads = [{ thread_id: "t1", values: { title: "Chat" } }];
    mockPathname = "/workspace/capabilities/experts/my-agent/chats/t1";
    mockParams = { thread_id: "t1", agent_name: "my-agent" };
    render(<RecentChatList />);

    const deleteButtons = screen.getAllByTestId("thread-delete-action");
    await user.click(deleteButtons[0]!);

    expect(mockPush).toHaveBeenCalledWith(
      "/workspace/capabilities/experts/my-agent/chats/new",
    );
  });

  // ── Dropdown actions visibility ──────────────────────────────────────────

  test("renders dropdown menu with all actions for each thread", () => {
    mockThreads = [{ thread_id: "t1", values: { title: "Chat" } }];
    render(<RecentChatList />);
    expect(screen.getByText("Rename")).toBeInTheDocument();
    expect(screen.getByText("Share")).toBeInTheDocument();
    expect(screen.getByText("Export")).toBeInTheDocument();
    expect(screen.getByText("Delete")).toBeInTheDocument();
  });

  test("renders multiple dropdown menus for multiple threads", () => {
    mockThreads = [
      { thread_id: "t1", values: { title: "A" } },
      { thread_id: "t2", values: { title: "B" } },
    ];
    render(<RecentChatList />);
    const dropdowns = screen.getAllByTestId("dropdown-menu");
    expect(dropdowns).toHaveLength(2);
  });
});
