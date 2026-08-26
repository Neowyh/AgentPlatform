import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

const mockListResources = vi.fn();
const mockListUsers = vi.fn();
const mockArchiveResource = vi.fn();
const mockSuspendResource = vi.fn();
const mockRestoreResource = vi.fn();
const mockReplace = vi.fn();
let mockUser: { system_role: string } | null = {
  system_role: "department_admin",
};

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

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
}));

vi.mock("@/core/admin/api", () => ({
  listResources: (...args: unknown[]) => mockListResources(...args),
  listUsers: (...args: unknown[]) => mockListUsers(...args),
  archiveResource: (...args: unknown[]) => mockArchiveResource(...args),
  suspendResource: (...args: unknown[]) => mockSuspendResource(...args),
  restoreResource: (...args: unknown[]) => mockRestoreResource(...args),
}));

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: () => ({
    user: mockUser,
  }),
}));

vi.mock("lucide-react", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    ArchiveIcon: () => null,
    RefreshCwIcon: () => null,
    BanIcon: () => null,
  };
});

import ResourcesPage from "@/app/workspace/admin/resources/page";

describe("ResourcesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser = { system_role: "department_admin" };
    mockListResources.mockResolvedValue({
      resources: Array.from({ length: 60 }, (_, index) => ({
        id: `resource-${index}`,
        resource_type: index % 2 === 0 ? "agent" : "tool",
        resource_type_label: index % 2 === 0 ? "智能体" : "工具",
        resource_id: `resource-${index}`,
        visibility: "public",
        owner_id: null,
        department_id: null,
        created_at: "2024-01-01T00:00:00",
      })),
      total: 61,
      limit: 50,
      offset: 0,
    });
    mockListUsers.mockResolvedValue({
      users: [{ id: "user-1", username: "alice" }],
      total: 1,
      limit: 500,
      offset: 0,
    });
  });

  const baseFilterParams = {
    resource_type: undefined,
    visibility: undefined,
    lifecycle_status: undefined,
    owner_id: undefined,
  };

  test("renders canonical resource total and requests next page", async () => {
    const user = userEvent.setup();
    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getAllByTestId("resource-row")).toHaveLength(60);
    });

    expect(screen.getByText("1 / 2")).toBeInTheDocument();
    expect(mockListResources).toHaveBeenCalledWith({
      ...baseFilterParams,
      limit: 50,
      offset: 0,
    });

    await user.click(screen.getByText("下一页"));

    await waitFor(() => {
      expect(mockListResources).toHaveBeenLastCalledWith({
        ...baseFilterParams,
        limit: 50,
        offset: 50,
      });
    });
  });

  test("applies resource type filter through the canonical endpoint", async () => {
    const user = userEvent.setup();
    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getAllByTestId("resource-row")).toHaveLength(60);
    });

    await user.click(screen.getAllByRole("combobox")[0]!);
    await user.click(screen.getByRole("option", { name: "工作流" }));

    await waitFor(() => {
      expect(mockListResources).toHaveBeenLastCalledWith({
        ...baseFilterParams,
        resource_type: "workflow",
        limit: 50,
        offset: 0,
      });
    });
  });

  test("applies visibility filter", async () => {
    const user = userEvent.setup();
    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getAllByTestId("resource-row")).toHaveLength(60);
    });

    await user.click(screen.getAllByRole("combobox")[1]!);
    await user.click(screen.getByRole("option", { name: "私有" }));

    await waitFor(() => {
      expect(mockListResources).toHaveBeenLastCalledWith({
        ...baseFilterParams,
        visibility: "private",
        limit: 50,
        offset: 0,
      });
    });
  });

  test("applies lifecycle status filter", async () => {
    const user = userEvent.setup();
    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getAllByTestId("resource-row")).toHaveLength(60);
    });

    await user.click(screen.getAllByRole("combobox")[2]!);
    await user.click(screen.getByRole("option", { name: "已归档" }));

    await waitFor(() => {
      expect(mockListResources).toHaveBeenLastCalledWith({
        ...baseFilterParams,
        lifecycle_status: "archived",
        limit: 50,
        offset: 0,
      });
    });
  });

  test("applies owner filter from user dropdown", async () => {
    const user = userEvent.setup();
    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getAllByTestId("resource-row")).toHaveLength(60);
    });

    await user.click(screen.getAllByRole("combobox")[3]!);
    await user.click(screen.getByRole("option", { name: "alice" }));

    await waitFor(() => {
      expect(mockListResources).toHaveBeenLastCalledWith({
        ...baseFilterParams,
        owner_id: "user-1",
        limit: 50,
        offset: 0,
      });
    });
  });

  test("combines type, visibility, status and owner filters", async () => {
    const user = userEvent.setup();
    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getAllByTestId("resource-row")).toHaveLength(60);
    });

    await user.click(screen.getAllByRole("combobox")[0]!);
    await user.click(screen.getByRole("option", { name: "智能体" }));
    await user.click(screen.getAllByRole("combobox")[1]!);
    await user.click(screen.getByRole("option", { name: "部门" }));
    await user.click(screen.getAllByRole("combobox")[2]!);
    await user.click(screen.getByRole("option", { name: "已下架" }));
    await user.click(screen.getAllByRole("combobox")[3]!);
    await user.click(screen.getByRole("option", { name: "alice" }));

    await waitFor(() => {
      expect(mockListResources).toHaveBeenLastCalledWith({
        resource_type: "agent",
        visibility: "department",
        lifecycle_status: "suspended",
        owner_id: "user-1",
        limit: 50,
        offset: 0,
      });
    });
  });

  test("resets to first page when a filter changes", async () => {
    const user = userEvent.setup();
    render(<ResourcesPage />);

    await waitFor(() => expect(screen.getByText("1 / 2")).toBeInTheDocument());
    await user.click(screen.getByText("下一页"));
    await waitFor(() => expect(screen.getByText("2 / 2")).toBeInTheDocument());

    await user.click(screen.getAllByRole("combobox")[1]!);
    await user.click(screen.getByRole("option", { name: "公开" }));

    await waitFor(() => {
      expect(mockListResources).toHaveBeenLastCalledWith({
        ...baseFilterParams,
        visibility: "public",
        limit: 50,
        offset: 0,
      });
    });
  });

  test("does not request resources for a regular user", async () => {
    mockUser = { system_role: "user" };
    render(<ResourcesPage />);

    await waitFor(() =>
      expect(screen.getByText("资源管理")).toBeInTheDocument(),
    );
    expect(mockListResources).not.toHaveBeenCalled();
  });

  test("shows a string error when resource loading fails", async () => {
    mockListResources.mockRejectedValue("service unavailable");
    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getByText("service unavailable")).toBeInTheDocument();
    });
  });

  test("returns to the previous page from page two", async () => {
    const user = userEvent.setup();
    render(<ResourcesPage />);

    await waitFor(() => expect(screen.getByText("1 / 2")).toBeInTheDocument());
    await user.click(screen.getByText("下一页"));
    await waitFor(() => expect(screen.getByText("2 / 2")).toBeInTheDocument());
    await user.click(screen.getByText("上一页"));

    await waitFor(() => expect(screen.getByText("1 / 2")).toBeInTheDocument());
  });

  test("shows lifecycle actions only for canonical resources", async () => {
    mockUser = { system_role: "super_admin" };
    mockListResources.mockResolvedValue({
      resources: [
        {
          id: "11111111-1111-1111-1111-111111111111",
          resource_type: "agent",
          resource_type_label: "智能体",
          resource_id: "reviewer",
          visibility: "department",
          owner_id: "owner-1",
          department_id: null,
          lifecycle_status: "active",
          created_at: "2024-01-01T00:00:00",
        },
        {
          id: "legacy-agent-1",
          resource_type: "agent",
          resource_type_label: "智能体",
          resource_id: "legacy-agent-1",
          visibility: "public",
          owner_id: null,
          department_id: null,
          created_at: "2024-01-01T00:00:00",
        },
      ],
      total: 2,
      limit: 50,
      offset: 0,
    });
    const user = userEvent.setup();
    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getAllByTestId("resource-row")).toHaveLength(2);
    });

    const canonicalRow = screen
      .getAllByTestId("resource-row")
      .find((row) => row.textContent?.includes("reviewer"));
    const legacyRow = screen
      .getAllByTestId("resource-row")
      .find((row) => row.textContent?.includes("legacy-agent-1"));

    expect(canonicalRow).toBeTruthy();
    expect(legacyRow).toBeTruthy();
    expect(
      within(canonicalRow!).getByRole("button", { name: "归档" }),
    ).toBeInTheDocument();
    expect(
      within(legacyRow!).queryByRole("button", { name: "归档" }),
    ).not.toBeInTheDocument();
  });

  test("archives a canonical resource and reloads the list", async () => {
    mockUser = { system_role: "department_admin" };
    mockListResources.mockResolvedValue({
      resources: [
        {
          id: "11111111-1111-1111-1111-111111111111",
          resource_type: "workflow",
          resource_type_label: "工作流",
          resource_id: "wf-1",
          visibility: "private",
          owner_id: "owner-1",
          department_id: null,
          lifecycle_status: "active",
          created_at: "2024-01-01T00:00:00",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
    mockArchiveResource.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getAllByTestId("resource-row")).toHaveLength(1);
    });

    await user.click(screen.getByRole("button", { name: "归档" }));

    await waitFor(() => {
      expect(mockArchiveResource).toHaveBeenCalledWith(
        "11111111-1111-1111-1111-111111111111",
      );
    });
    expect(mockListResources).toHaveBeenCalledTimes(2);
  });

  test("shows suspend and restore only for super admins", async () => {
    mockUser = { system_role: "super_admin" };
    mockListResources.mockResolvedValue({
      resources: [
        {
          id: "11111111-1111-1111-1111-111111111111",
          resource_type: "agent",
          resource_type_label: "智能体",
          resource_id: "reviewer",
          visibility: "department",
          owner_id: "owner-1",
          department_id: null,
          lifecycle_status: "suspended",
          created_at: "2024-01-01T00:00:00",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
    const user = userEvent.setup();
    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getAllByTestId("resource-row")).toHaveLength(1);
    });

    expect(screen.getByRole("button", { name: /恢复/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /恢复/ }));

    await waitFor(() => {
      expect(mockRestoreResource).toHaveBeenCalledWith(
        "11111111-1111-1111-1111-111111111111",
      );
    });
  });

  test("department admins see only archive for canonical resources", async () => {
    mockUser = { system_role: "department_admin" };
    mockListResources.mockResolvedValue({
      resources: [
        {
          id: "11111111-1111-1111-1111-111111111111",
          resource_type: "agent",
          resource_type_label: "智能体",
          resource_id: "reviewer",
          visibility: "department",
          owner_id: "owner-1",
          department_id: null,
          lifecycle_status: "active",
          created_at: "2024-01-01T00:00:00",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getAllByTestId("resource-row")).toHaveLength(1);
    });

    expect(screen.getByRole("button", { name: "归档" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /恢复/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /下架/ }),
    ).not.toBeInTheDocument();
  });
});
