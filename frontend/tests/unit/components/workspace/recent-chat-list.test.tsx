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
const mockReplace = vi.fn();
let mockPathname = "/workspace/chats/thread-1";
let mockParams: Record<string, string> = {
  thread_id: "thread-1",
};
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
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
  DialogDescription: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
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
    deleteTitle: "Delete conversation",
    deleteThreadConfirm: (title: string) => `Delete ${title}`,
    deleteFailed: "Failed to delete conversation",
    cancel: "Cancel",
    save: "Save",
    exportSuccess: "Export successful",
    exportFailed: "Failed to export conversation",
  },
  conversation: {
    noMessages: "No messages to export",
  },
  chats: {
    branchLabel: "Branch",
    loadOlderChats: "Load older chats",
    loadingMore: "Loading more",
    pinChat: "Pin chat",
    pinChatFailed: "Failed to update pinned chat",
    unpinChat: "Unpin chat",
    // 合并后删除确认收敛进 ThreadDeleteDialogProvider 宿主对话框。
    deleteChat: "Delete conversation",
    deleteConfirm: (title: string) => `Delete ${title}?`,
    deleteFailed: "Failed to delete chat",
  },
  threads: {
    getState: (state: string) => state,
  },
  // 合并后行内菜单带上游"移入项目"子菜单，需要 projects 键。
  projects: {
    moveToProject: "Move to project",
    moveToProjectHint: "Pick a project",
    removeFromProject: "Remove from project",
    newProject: "New project",
    namePlaceholder: "Project name",
    create: "Create",
    moveFailed: "Failed to move chat",
    createFailed: "Failed to create project",
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

// 合并后组件接入 AuthProvider 权限判定（THREADS_DELETE 门控删除入口），
// 本测试不渲染真实 Provider，mock 为无权限列表用户（hasPermission 对 null 放行）。
vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: () => ({ user: null }),
}));

// 合并后列表接入上游 Projects 功能（分组模式查询 + 移入项目菜单），
// 这些 hook 走 react-query；本测试固定 flat 模式，mock 最小查询形状。
vi.mock("@/core/projects", () => ({
  useProjects: () => ({ data: undefined, isLoading: false, isError: false }),
  useCreateProject: () => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

// 合并后列表读取本地 projectsDisplayMode 偏好（默认 flat）。
vi.mock("@/core/settings", () => ({
  useLocalSettings: () => [{ projectsDisplayMode: "flat" }, vi.fn()],
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
  // 删除确认对话框宿主（ThreadDeleteDialogProvider）通过 mutateAsync 发起删除，
  // 成功后回调 onDeleted（与真实 useDeleteThread 的 onSuccess 语义一致）。
  useDeleteThread: () => ({
    mutateAsync: mockDeleteMutate,
    mutate: mockDeleteMutate,
    isPending: false,
    isError: false,
  }),
  useRenameThread: () => ({ mutate: mockRenameMutate }),
  usePinThread: () => ({ mutate: vi.fn() }),
  // 合并后接入"移入项目"操作（上游 ThreadSidebarItem 基底）。
  useMoveThreadToProject: () => ({ mutate: vi.fn(), isPending: false }),
  // The list reads from the paginated feed; expose the same fixture threads.
  useInfiniteThreads: () => ({
    data: { pages: [mockThreads], pageParams: [0] },
    fetchNextPage: vi.fn(),
    hasNextPage: false,
    isFetchingNextPage: false,
  }),
}));

// 删除宿主在落位邻居后重置会话视图；本测试只断言路由跳转。
vi.mock("@/components/workspace/chats/use-thread-chat", () => ({
  resetThreadChatAfterDelete: vi.fn(),
}));

// 合并后行内菜单接入上游归档操作（走 react-query mutation）；本测试不触发归档。
vi.mock("@/components/workspace/use-thread-archive-action", () => ({
  useThreadArchiveAction: () => ({
    setArchived: vi.fn(),
    isPending: false,
  }),
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
        ? `/workspace/agents/${agentName}/chats/${thread}`
        : `/workspace/chats/${thread}`;
    }
    const agentName = thread.context?.agent_name;
    return agentName
      ? `/workspace/agents/${agentName}/chats/${thread.thread_id}`
      : `/workspace/chats/${thread.thread_id}`;
  },
  isThreadPinned: () => false,
  sortPinnedThreads: <T,>(threads: T[]): T[] => threads,
  channelSourceOfThread: () => undefined,
  // 合并后列表在分组模式下用 projectIdOfThread 过滤；本测试固定 flat，返回 null 即"未分组"。
  projectIdOfThread: () => null,
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
  // The list calls the format-dispatching wrapper.
  exportThread: (thread: unknown, messages: unknown, format: string) =>
    format === "json"
      ? mockExportJSON(thread, messages)
      : mockExportMarkdown(thread, messages),
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
// 合并后删除确认收敛进 ThreadDeleteDialogProvider 宿主（workspace-sidebar 挂载），
// 列表行只负责发起请求；本测试用真实宿主包一层以保留"删除→落位邻居"端到端断言。
let ThreadDeleteDialogProvider: typeof import("@/components/workspace/thread-delete-dialog").ThreadDeleteDialogProvider;

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
  // 与真实 useDeleteThread 的 onSuccess 一致：删除成功后触发 onDeleted（落位导航）。
  mockDeleteMutate.mockImplementation(
    async (vars: { onDeleted?: () => void }) => {
      vars.onDeleted?.();
    },
  );
  const mod = await import("@/components/workspace/recent-chat-list");
  RecentChatList = mod.RecentChatList;
  const deleteMod = await import("@/components/workspace/thread-delete-dialog");
  ThreadDeleteDialogProvider = deleteMod.ThreadDeleteDialogProvider;
});

afterEach(() => {
  cleanup();
});

function renderList() {
  return render(
    <ThreadDeleteDialogProvider>
      <RecentChatList />
    </ThreadDeleteDialogProvider>,
  );
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("RecentChatList", () => {
  // ── Empty state ──────────────────────────────────────────────────────────

  test("returns null when there are no threads", () => {
    mockThreads = [];
    const { container } = renderList();
    expect(container.firstChild).toBeNull();
  });

  // ── Thread rendering ─────────────────────────────────────────────────────

  test("renders thread list when threads exist", () => {
    mockThreads = [
      { thread_id: "t1", values: { title: "Chat One" } },
      { thread_id: "t2", values: { title: "Chat Two" } },
    ];
    renderList();
    // 合并后列表不再输出 thread-list testid；以行标题断言列表渲染。
    expect(screen.getByText("Chat One")).toBeInTheDocument();
    expect(screen.getByText("Chat Two")).toBeInTheDocument();
  });

  test("renders 'Untitled' for threads without a title", () => {
    mockThreads = [{ thread_id: "t1" }];
    renderList();
    expect(screen.getByText("Untitled")).toBeInTheDocument();
  });

  test("shows 'Recent Chats' label", () => {
    mockThreads = [{ thread_id: "t1", values: { title: "Chat" } }];
    renderList();
    expect(screen.getByText("Recent Chats")).toBeInTheDocument();
  });

  test("links each thread to its path", () => {
    mockThreads = [
      { thread_id: "t1", values: { title: "Chat One" } },
      { thread_id: "t2", values: { title: "Chat Two" } },
    ];
    renderList();
    const links = screen.getAllByText(/Chat (One|Two)/);
    // The merged list wraps the title in a truncating span inside the link.
    expect(links[0]!.closest("a")).toHaveAttribute(
      "href",
      "/workspace/chats/t1",
    );
    expect(links[1]!.closest("a")).toHaveAttribute(
      "href",
      "/workspace/chats/t2",
    );
  });

  test("marks the active thread based on pathname", () => {
    mockPathname = "/workspace/chats/t2";
    mockThreads = [
      { thread_id: "t1", values: { title: "Chat One" } },
      { thread_id: "t2", values: { title: "Chat Two" } },
    ];
    renderList();
    // 合并后行组件不再输出 thread-item testid；以 SidebarMenuButton 的
    // data-active 标记断言当前路径对应的行处于激活态。
    const items = screen.getAllByText(/Chat (One|Two)/);
    expect(items).toHaveLength(2);
    expect(
      screen.getByText("Chat Two").closest("div[data-active='true']"),
    ).not.toBeNull();
    expect(
      screen.getByText("Chat One").closest("div[data-active='true']"),
    ).toBeNull();
  });

  test("renders the correct number of thread items", () => {
    mockThreads = [
      { thread_id: "t1", values: { title: "A" } },
      { thread_id: "t2", values: { title: "B" } },
      { thread_id: "t3", values: { title: "C" } },
    ];
    renderList();
    // 合并后每行渲染一个行内操作菜单；以菜单数量代表行数。
    expect(screen.getAllByTestId("dropdown-menu")).toHaveLength(3);
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
    renderList();

    // Click the delete action on the first thread
    // 合并后删除入口是行内菜单的 Delete 项，确认按钮在宿主对话框里。
    await user.click(screen.getAllByText("Delete")[0]!);
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(mockDeleteMutate).toHaveBeenCalledWith(
      expect.objectContaining({ threadId: "t1" }),
    );
  });

  test("navigates to next thread after deleting the active thread", async () => {
    const user = userEvent.setup();
    mockThreads = [
      { thread_id: "t1", values: { title: "First" } },
      { thread_id: "t2", values: { title: "Second" } },
    ];
    mockPathname = "/workspace/chats/t1";
    mockParams = { thread_id: "t1" };
    renderList();

    // 合并后删除入口是行内菜单的 Delete 项，确认按钮在宿主对话框里。
    await user.click(screen.getAllByText("Delete")[0]!);
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(mockReplace).toHaveBeenCalledWith("/workspace/chats/t2");
  });

  test("navigates to previous thread when deleting the last thread", async () => {
    const user = userEvent.setup();
    mockThreads = [
      { thread_id: "t1", values: { title: "First" } },
      { thread_id: "t2", values: { title: "Second" } },
    ];
    mockPathname = "/workspace/chats/t2";
    mockParams = { thread_id: "t2" };
    renderList();

    // 合并后删除入口是行内菜单的 Delete 项，确认按钮在宿主对话框里。
    await user.click(screen.getAllByText("Delete")[1]!);
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(mockReplace).toHaveBeenCalledWith("/workspace/chats/t1");
  });

  test("navigates to 'new' when deleting the only thread", async () => {
    const user = userEvent.setup();
    mockThreads = [{ thread_id: "t1", values: { title: "Only" } }];
    mockPathname = "/workspace/chats/t1";
    mockParams = { thread_id: "t1" };
    renderList();

    // 合并后删除入口是行内菜单的 Delete 项，确认按钮在宿主对话框里。
    await user.click(screen.getAllByText("Delete")[0]!);
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(mockReplace).toHaveBeenCalledWith("/workspace/chats/new");
  });

  test("does not navigate when deleting a non-active thread", async () => {
    const user = userEvent.setup();
    mockThreads = [
      { thread_id: "t1", values: { title: "First" } },
      { thread_id: "t2", values: { title: "Second" } },
    ];
    mockPathname = "/workspace/chats/t1";
    mockParams = { thread_id: "t1" };
    renderList();

    // 合并后删除入口是行内菜单的 Delete 项，确认按钮在宿主对话框里。
    await user.click(screen.getAllByText("Delete")[1]!);
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(mockDeleteMutate).toHaveBeenCalledWith(
      expect.objectContaining({ threadId: "t2" }),
    );
    expect(mockReplace).not.toHaveBeenCalled();
  });

  // ── Rename ───────────────────────────────────────────────────────────────

  test("opens rename dialog when rename action is clicked", async () => {
    const user = userEvent.setup();
    mockThreads = [{ thread_id: "t1", values: { title: "My Chat" } }];
    renderList();

    // 合并后重命名入口是行内菜单的 Rename 项。
    await user.click(screen.getAllByText("Rename")[0]!);

    await waitFor(() => {
      expect(screen.getByTestId("dialog")).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue("My Chat")).toBeInTheDocument();
  });

  test("submits rename with trimmed value", async () => {
    const user = userEvent.setup();
    mockThreads = [{ thread_id: "t1", values: { title: "Old" } }];
    renderList();

    // Open rename dialog
    // 合并后重命名入口是行内菜单的 Rename 项。
    await user.click(screen.getAllByText("Rename")[0]!);

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

    expect(mockRenameMutate).toHaveBeenCalledWith(
      { threadId: "t1", title: "New Title" },
      expect.anything(),
    );
  });

  test("does not submit rename when value is empty", async () => {
    const user = userEvent.setup();
    mockThreads = [{ thread_id: "t1", values: { title: "Old" } }];
    renderList();

    // 合并后重命名入口是行内菜单的 Rename 项。
    await user.click(screen.getAllByText("Rename")[0]!);

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
    renderList();

    // 合并后重命名入口是行内菜单的 Rename 项。
    await user.click(screen.getAllByText("Rename")[0]!);

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
    renderList();

    // 合并后重命名入口是行内菜单的 Rename 项。
    await user.click(screen.getAllByText("Rename")[0]!);

    await waitFor(() => {
      expect(screen.getByTestId("rename-input")).toBeInTheDocument();
    });

    const input = screen.getByTestId("rename-input");
    await user.clear(input);
    await user.type(input, "New Name");
    await user.keyboard("{Enter}");

    expect(mockRenameMutate).toHaveBeenCalledWith(
      { threadId: "t1", title: "New Name" },
      expect.anything(),
    );
  });

  // ── Share ────────────────────────────────────────────────────────────────

  test("copies share URL to clipboard", async () => {
    const user = userEvent.setup();
    mockThreads = [{ thread_id: "t1", values: { title: "Chat" } }];
    renderList();

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
    renderList();

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
    renderList();

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
    renderList();

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
    renderList();

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
    renderList();

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
    renderList();

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
    mockPathname = "/workspace/agents/my-agent/chats/t1";
    mockParams = { thread_id: "t1", agent_name: "my-agent" };
    renderList();

    // 合并后删除入口是行内菜单的 Delete 项，确认按钮在宿主对话框里。
    await user.click(screen.getAllByText("Delete")[0]!);
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(mockReplace).toHaveBeenCalledWith(
      "/workspace/agents/my-agent/chats/new",
    );
  });

  // ── Dropdown actions visibility ──────────────────────────────────────────

  test("renders dropdown menu with all actions for each thread", () => {
    mockThreads = [{ thread_id: "t1", values: { title: "Chat" } }];
    renderList();
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
    renderList();
    const dropdowns = screen.getAllByTestId("dropdown-menu");
    expect(dropdowns).toHaveLength(2);
  });
});
