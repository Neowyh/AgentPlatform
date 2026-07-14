import {
  fireEvent,
  render,
  screen,
  cleanup,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks -- must be declared before the component import
// ---------------------------------------------------------------------------

const mockListDepartments = vi.fn();
const mockCreateDepartment = vi.fn();
const mockUpdateDepartment = vi.fn();
const mockDeleteDepartment = vi.fn();
const mockGetDepartmentResources = vi.fn();
const mockToastSuccess = vi.fn();
const mockToastError = vi.fn();
const mockRouterReplace = vi.fn();

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: mockRouterReplace,
    prefetch: vi.fn(),
  }),
  usePathname: () => "/workspace/admin/departments",
}));

vi.mock("@/core/admin/api", () => ({
  listDepartments: (...args: unknown[]) => mockListDepartments(...args),
  createDepartment: (...args: unknown[]) => mockCreateDepartment(...args),
  updateDepartment: (...args: unknown[]) => mockUpdateDepartment(...args),
  deleteDepartment: (...args: unknown[]) => mockDeleteDepartment(...args),
  getDepartmentResources: (...args: unknown[]) =>
    mockGetDepartmentResources(...args),
}));

vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => mockToastSuccess(...args),
    error: (...args: unknown[]) => mockToastError(...args),
  },
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

// ---------------------------------------------------------------------------
// Import component after mocks
// ---------------------------------------------------------------------------

import DepartmentsPage from "@/app/workspace/admin/departments/page";
import { useAuth } from "@/core/auth/AuthProvider";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockDepartments = [
  {
    id: "dept-1",
    name: "Engineering",
    description: "Software development team",
    member_count: 10,
    agent_count: 3,
    skill_count: 5,
    created_at: "2025-01-01T00:00:00Z",
  },
  {
    id: "dept-2",
    name: "Marketing",
    description: "Marketing and growth",
    member_count: 5,
    agent_count: 1,
    skill_count: 2,
    created_at: "2025-02-01T00:00:00Z",
  },
  {
    id: "dept-3",
    name: "Sales",
    description: "",
    member_count: 0,
    agent_count: 0,
    skill_count: 0,
    created_at: "2025-03-01T00:00:00Z",
  },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DepartmentsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: "test-admin-id",
        email: "admin@example.com",
        system_role: "super_admin",
        needs_setup: false,
      },
      isAuthenticated: true,
      isLoading: false,
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });
    mockListDepartments.mockResolvedValue({
      departments: mockDepartments,
      total: 3,
      limit: 50,
      offset: 0,
    });
    mockCreateDepartment.mockResolvedValue({
      id: "dept-new",
      name: "New Dept",
      description: "New department",
      member_count: 0,
      agent_count: 0,
      skill_count: 0,
      created_at: "2025-06-01T00:00:00Z",
    });
    mockUpdateDepartment.mockResolvedValue({ success: true });
    mockDeleteDepartment.mockResolvedValue(undefined);
    mockGetDepartmentResources.mockResolvedValue({
      resources: [],
      department_name: "Engineering",
    });
  });

  afterEach(() => {
    cleanup();
  });

  // ── Rendering ──────────────────────────────────────────────────────

  test("renders the page header with title and description", async () => {
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByText("部门管理")).toBeInTheDocument();
      expect(screen.getByText("管理组织部门和资源分配")).toBeInTheDocument();
    });
  });

  test("renders a back link to /workspace/admin", async () => {
    render(<DepartmentsPage />);
    await waitFor(() => {
      const links = screen.getAllByRole("link");
      const backLink = links.find(
        (l) => l.getAttribute("href") === "/workspace/admin",
      );
      expect(backLink).toBeTruthy();
    });
  });

  test("renders the create department button in header", async () => {
    render(<DepartmentsPage />);
    await waitFor(() => {
      const createButtons = screen.getAllByText("新建部门");
      expect(createButtons).toHaveLength(1);
    });
  });

  // ── Loading state ──────────────────────────────────────────────────

  test("shows loading indicator while fetching departments", () => {
    mockListDepartments.mockReturnValue(new Promise(() => {}));
    render(<DepartmentsPage />);
    expect(screen.getByText("加载中...")).toBeInTheDocument();
    expect(screen.queryByTestId("department-list")).not.toBeInTheDocument();
  });

  // ── Success state ──────────────────────────────────────────────────

  test("renders department list after loading", async () => {
    render(<DepartmentsPage />);
    await waitFor(() => {
      const deptCards = screen.getAllByTestId("department-card");
      expect(deptCards).toHaveLength(3);
    });
  });

  test("displays department names", async () => {
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByText("Engineering")).toBeInTheDocument();
      expect(screen.getByText("Marketing")).toBeInTheDocument();
      expect(screen.getByText("Sales")).toBeInTheDocument();
    });
  });

  test("displays department descriptions", async () => {
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByText("Software development team")).toBeInTheDocument();
      expect(screen.getByText("Marketing and growth")).toBeInTheDocument();
    });
  });

  test("shows 'no description' placeholder when description is empty", async () => {
    render(<DepartmentsPage />);
    await waitFor(() => {
      // Sales has empty description, should show "暂无描述"
      const noDesc = screen.getAllByText("暂无描述");
      expect(noDesc).toHaveLength(1);
    });
  });

  test("displays member count for each department", async () => {
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByText("10 成员")).toBeInTheDocument();
      expect(screen.getByText("5 成员")).toBeInTheDocument();
      expect(screen.getByText("0 成员")).toBeInTheDocument();
    });
  });

  test("displays agent count for each department", async () => {
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByText("3 智能体")).toBeInTheDocument();
      expect(screen.getByText("1 智能体")).toBeInTheDocument();
      expect(screen.getByText("0 智能体")).toBeInTheDocument();
    });
  });

  test("displays skill count for each department", async () => {
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByText("5 技能")).toBeInTheDocument();
      expect(screen.getByText("2 技能")).toBeInTheDocument();
      expect(screen.getByText("0 技能")).toBeInTheDocument();
    });
  });

  test("displays creation date for each department", async () => {
    render(<DepartmentsPage />);
    await waitFor(() => {
      const createdTexts = screen.getAllByText(/创建于/);
      expect(createdTexts).toHaveLength(3);
    });
  });

  // ── Empty state ────────────────────────────────────────────────────

  test("shows empty state when no departments exist", async () => {
    mockListDepartments.mockResolvedValue({
      departments: [],
      total: 0,
      limit: 50,
      offset: 0,
    });
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByText("暂无部门")).toBeInTheDocument();
    });
  });

  test("shows create button in empty state", async () => {
    mockListDepartments.mockResolvedValue({
      departments: [],
      total: 0,
      limit: 50,
      offset: 0,
    });
    render(<DepartmentsPage />);
    await waitFor(() => {
      const createButtons = screen.getAllByText("新建部门");
      expect(createButtons).toHaveLength(2);
    });
  });

  // ── Error state ────────────────────────────────────────────────────

  test("shows error message when API call fails", async () => {
    mockListDepartments.mockRejectedValue(new Error("Server error"));
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
  });

  test("shows stringified error for non-Error throws", async () => {
    mockListDepartments.mockRejectedValue("unknown failure");
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByText("unknown failure")).toBeInTheDocument();
    });
  });

  test("does not render department list in error state", async () => {
    mockListDepartments.mockRejectedValue(new Error("fail"));
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.queryByTestId("department-list")).not.toBeInTheDocument();
    });
  });

  // ── API calls ──────────────────────────────────────────────────────

  test("calls listDepartments on mount", () => {
    render(<DepartmentsPage />);
    expect(mockListDepartments).toHaveBeenCalledTimes(1);
  });

  // ── Create department ──────────────────────────────────────────────

  test("opens create dialog when clicking create button", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const createButtons = screen.getAllByText("新建部门");
    await user.click(createButtons[0]!);

    await waitFor(() => {
      expect(screen.getByText("创建一个新的组织部门")).toBeInTheDocument();
    });
  });

  test("create dialog has name and description inputs", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const createButtons = screen.getAllByText("新建部门");
    await user.click(createButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
      expect(
        screen.getByPlaceholderText("请输入部门描述（可选）"),
      ).toBeInTheDocument();
    });
  });

  test("shows toast error when creating with empty name", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const createButtons = screen.getAllByText("新建部门");
    await user.click(createButtons[0]!);

    await waitFor(() => {
      expect(screen.getByText("创建")).toBeInTheDocument();
    });

    // Click the create/submit button without filling name
    const submitButton = screen.getByText("创建");
    await user.click(submitButton);

    expect(mockToastError).toHaveBeenCalledWith("请输入部门名称");
    expect(mockCreateDepartment).not.toHaveBeenCalled();
  });

  test(
    "calls createDepartment on successful form submission",
    { timeout: 30000 },
    async () => {
      const user = userEvent.setup();
      render(<DepartmentsPage />);
      await waitFor(() => {
        expect(screen.getByTestId("department-list")).toBeInTheDocument();
      });

      // Open create dialog
      const createButtons = screen.getAllByText("新建部门");
      await user.click(createButtons[0]!);

      await waitFor(() => {
        expect(
          screen.getByPlaceholderText("请输入部门名称"),
        ).toBeInTheDocument();
      });

      // Fill in the form
      const nameInput = screen.getByPlaceholderText("请输入部门名称");
      const descInput = screen.getByPlaceholderText("请输入部门描述（可选）");
      await user.type(nameInput, "New Department");
      await user.type(descInput, "A brand new department");

      // Submit
      const submitButton = screen.getByText("创建");
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockCreateDepartment).toHaveBeenCalledWith({
          name: "New Department",
          description: "A brand new department",
        });
        expect(mockToastSuccess).toHaveBeenCalledWith("部门已创建");
      });
    },
  );

  test("shows toast error when createDepartment fails", async () => {
    const user = userEvent.setup();
    mockCreateDepartment.mockRejectedValue(new Error("Duplicate name"));
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const createButtons = screen.getAllByText("新建部门");
    await user.click(createButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("请输入部门名称"), "Dup Dept");
    await user.click(screen.getByText("创建"));

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("Duplicate name");
    });
  });

  // ── Edit department ────────────────────────────────────────────────

  test("opens edit dialog when clicking edit button", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTestId("department-edit-button");
    await user.click(editButtons[0]!);

    await waitFor(() => {
      expect(screen.getByText("修改部门信息")).toBeInTheDocument();
    });
  });

  test("edit dialog pre-fills with department data", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTestId("department-edit-button");
    fireEvent.click(editButtons[0]!); // Edit "Engineering"

    await waitFor(() => {
      const nameInput = screen.getByPlaceholderText("请输入部门名称");
      expect((nameInput as HTMLInputElement).value).toBe("Engineering");
      const descInput = screen.getByPlaceholderText("请输入部门描述（可选）");
      expect((descInput as HTMLInputElement).value).toBe(
        "Software development team",
      );
    });
  });

  test("calls updateDepartment on edit form submission", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTestId("department-edit-button");
    await user.click(editButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    // Clear and type new name
    const nameInput = screen.getByPlaceholderText("请输入部门名称");
    await user.clear(nameInput);
    await user.type(nameInput, "Updated Engineering");

    const saveButton = screen.getByText("保存");
    await user.click(saveButton);

    await waitFor(() => {
      expect(mockUpdateDepartment).toHaveBeenCalledWith("dept-1", {
        name: "Updated Engineering",
        description: "Software development team",
      });
      expect(mockToastSuccess).toHaveBeenCalledWith("部门已更新");
    });
  });

  test("shows toast error when editing with empty name", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTestId("department-edit-button");
    await user.click(editButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    const nameInput = screen.getByPlaceholderText("请输入部门名称");
    await user.clear(nameInput);

    const saveButton = screen.getByText("保存");
    await user.click(saveButton);

    expect(mockToastError).toHaveBeenCalledWith("请输入部门名称");
    expect(mockUpdateDepartment).not.toHaveBeenCalled();
  });

  test("shows toast error when updateDepartment fails", async () => {
    const user = userEvent.setup();
    mockUpdateDepartment.mockRejectedValue(new Error("Update failed"));
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTestId("department-edit-button");
    await user.click(editButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    await user.click(screen.getByText("保存"));

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("Update failed");
    });
  });

  // ── Delete department ──────────────────────────────────────────────

  test("calls deleteDepartment when delete is confirmed", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTestId("department-delete-button");
    await user.click(deleteButtons[0]!);

    await waitFor(() => {
      expect(mockDeleteDepartment).toHaveBeenCalledWith("dept-1");
      expect(mockToastSuccess).toHaveBeenCalledWith("部门已删除");
    });

    vi.restoreAllMocks();
  });

  test("does not call deleteDepartment when delete is cancelled", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(false);

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTestId("department-delete-button");
    await user.click(deleteButtons[0]!);

    expect(mockDeleteDepartment).not.toHaveBeenCalled();

    vi.restoreAllMocks();
  });

  test("shows toast error when deleteDepartment fails", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockDeleteDepartment.mockRejectedValue(new Error("Delete failed"));

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTestId("department-delete-button");
    await user.click(deleteButtons[0]!);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("Delete failed");
    });

    vi.restoreAllMocks();
  });

  // ── Dialog cancel ──────────────────────────────────────────────────

  test("closes create dialog when cancel is clicked", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const createButtons = screen.getAllByText("新建部门");
    await user.click(createButtons[0]!);

    await waitFor(() => {
      expect(screen.getByText("创建一个新的组织部门")).toBeInTheDocument();
    });

    const cancelButton = screen.getByText("取消");
    await user.click(cancelButton);

    await waitFor(() => {
      expect(
        screen.queryByText("创建一个新的组织部门"),
      ).not.toBeInTheDocument();
    });
  });

  test("closes edit dialog when cancel is clicked", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTestId("department-edit-button");
    await user.click(editButtons[0]!);

    await waitFor(() => {
      expect(screen.getByText("修改部门信息")).toBeInTheDocument();
    });

    const cancelButton = screen.getByText("取消");
    await user.click(cancelButton);

    await waitFor(() => {
      expect(screen.queryByText("修改部门信息")).not.toBeInTheDocument();
    });
  });

  // ── Trims whitespace in inputs ─────────────────────────────────────

  test("trims whitespace from name and description on create", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const createButtons = screen.getAllByText("新建部门");
    await user.click(createButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    await user.type(
      screen.getByPlaceholderText("请输入部门名称"),
      "  Spaced Name  ",
    );
    await user.type(
      screen.getByPlaceholderText("请输入部门描述（可选）"),
      "  Spaced Desc  ",
    );

    await user.click(screen.getByText("创建"));

    await waitFor(() => {
      expect(mockCreateDepartment).toHaveBeenCalledWith({
        name: "Spaced Name",
        description: "Spaced Desc",
      });
    });
  });

  // ── Non-Error throws from API calls ────────────────────────────────

  test("shows stringified error when createDepartment throws non-Error", async () => {
    const user = userEvent.setup();
    mockCreateDepartment.mockRejectedValue("raw string error");
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const createButtons = screen.getAllByText("新建部门");
    await user.click(createButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("请输入部门名称"), "New Dept");
    await user.click(screen.getByText("创建"));

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("raw string error");
    });
  });

  test("shows stringified error when updateDepartment throws non-Error", async () => {
    const user = userEvent.setup();
    mockUpdateDepartment.mockRejectedValue("raw update error");
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTestId("department-edit-button");
    await user.click(editButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    await user.click(screen.getByText("保存"));

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("raw update error");
    });
  });

  test("shows stringified error when deleteDepartment throws non-Error", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockDeleteDepartment.mockRejectedValue("raw delete error");

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTestId("department-delete-button");
    await user.click(deleteButtons[0]!);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("raw delete error");
    });

    vi.restoreAllMocks();
  });

  // ── Delete button disabled during deletion ─────────────────────────

  test("disables delete button while deletion is in progress", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    // Make deleteDepartment hang
    mockDeleteDepartment.mockReturnValue(new Promise(() => {}));

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTestId("department-delete-button");
    await user.click(deleteButtons[0]!);

    await waitFor(() => {
      // The button should be disabled during deletion
      expect(deleteButtons[0]).toBeDisabled();
    });

    vi.restoreAllMocks();
  });

  // ── Submit button states ───────────────────────────────────────────

  test("shows 'creating...' text while creation is in progress", async () => {
    const user = userEvent.setup();
    // Make createDepartment hang
    mockCreateDepartment.mockReturnValue(new Promise(() => {}));

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const createButtons = screen.getAllByText("新建部门");
    await user.click(createButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("请输入部门名称"), "New Dept");
    await user.click(screen.getByText("创建"));

    await waitFor(() => {
      expect(screen.getByText("创建中...")).toBeInTheDocument();
    });
  });

  test("shows 'saving...' text while update is in progress", async () => {
    const user = userEvent.setup();
    // Make updateDepartment hang
    mockUpdateDepartment.mockReturnValue(new Promise(() => {}));

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTestId("department-edit-button");
    await user.click(editButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    await user.click(screen.getByText("保存"));

    await waitFor(() => {
      expect(screen.getByText("保存中...")).toBeInTheDocument();
    });
  });

  // ── Edit dialog: description trimming ──────────────────────────────

  test("trims whitespace from name and description on edit", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTestId("department-edit-button");
    await user.click(editButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    // Clear and type with whitespace
    const nameInput = screen.getByPlaceholderText("请输入部门名称");
    await user.clear(nameInput);
    await user.type(nameInput, "  Updated Name  ");

    await user.click(screen.getByText("保存"));

    await waitFor(() => {
      expect(mockUpdateDepartment).toHaveBeenCalledWith("dept-1", {
        name: "Updated Name",
        description: "Software development team",
      });
    });
  });

  // ── API calls ──────────────────────────────────────────────────────

  test("calls listDepartments on mount", () => {
    render(<DepartmentsPage />);
    expect(mockListDepartments).toHaveBeenCalledTimes(1);
  });

  // ── Department card details ────────────────────────────────────────

  test("shows all department cards with correct data", async () => {
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
      expect(screen.getByTestId("department-list")).toHaveTextContent(
        /Engineering/i,
      );
    });

    const deptCards = screen.getAllByTestId("department-card");
    expect(deptCards).toHaveLength(3);

    // Verify edit and delete buttons exist for each card
    const editButtons = screen.getAllByTestId("department-edit-button");
    const deleteButtons = screen.getAllByTestId("department-delete-button");
    expect(editButtons).toHaveLength(3);
    expect(deleteButtons).toHaveLength(3);
  });

  // ── Empty state: create button (lines 183-185) ─────────────────────

  test("opens create dialog from empty state button and resets fields", async () => {
    const user = userEvent.setup();
    mockListDepartments.mockResolvedValue({
      departments: [],
      total: 0,
      limit: 50,
      offset: 0,
    });
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByText("暂无部门")).toBeInTheDocument();
    });

    // Click the create button in the empty state area (not the header one)
    const emptyStateCreateButtons = screen.getAllByText("新建部门");
    // There are two "新建部门" buttons: header [0] and empty state [1]
    await user.click(emptyStateCreateButtons[1]!);

    await waitFor(() => {
      expect(screen.getByText("创建一个新的组织部门")).toBeInTheDocument();
    });

    // Verify inputs are empty (fields reset)
    const nameInput = screen.getByPlaceholderText("请输入部门名称");
    expect((nameInput as HTMLInputElement).value).toBe("");
    const descInput = screen.getByPlaceholderText("请输入部门描述（可选）");
    expect((descInput as HTMLInputElement).value).toBe("");
  });

  // ── Edit dialog: description onChange (line 321) ────────────────────

  test("edit dialog description textarea updates on change", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTestId("department-edit-button");
    await user.click(editButtons[0]!); // Edit "Engineering"

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("请输入部门描述（可选）"),
      ).toBeInTheDocument();
    });

    // Clear and type new description
    const descInput = screen.getByPlaceholderText("请输入部门描述（可选）");
    fireEvent.change(descInput, {
      target: { value: "Updated description text" },
    });

    expect((descInput as HTMLInputElement).value).toBe(
      "Updated description text",
    );

    // Save and verify the updated description is sent
    fireEvent.click(screen.getByText("保存"));

    await waitFor(() => {
      expect(mockUpdateDepartment).toHaveBeenCalledWith("dept-1", {
        name: "Engineering",
        description: "Updated description text",
      });
    });
  });

  // ── Edit dialog: name onChange ──────────────────────────────────────

  test("edit dialog name input updates on change", async () => {
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTestId("department-edit-button");
    fireEvent.click(editButtons[0]!); // Edit "Engineering"

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    const nameInput = screen.getByPlaceholderText("请输入部门名称");
    fireEvent.change(nameInput, { target: { value: "New Name" } });

    expect((nameInput as HTMLInputElement).value).toBe("New Name");
  });

  // ── Create dialog: description onChange ─────────────────────────────

  test("create dialog description textarea updates on change", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const createButtons = screen.getAllByText("新建部门");
    await user.click(createButtons[0]!);

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("请输入部门描述（可选）"),
      ).toBeInTheDocument();
    });

    const descInput = screen.getByPlaceholderText("请输入部门描述（可选）");
    await user.type(descInput, "My description");

    expect((descInput as HTMLInputElement).value).toBe("My description");
  });

  // ── Create dialog: name onChange ────────────────────────────────────

  test("create dialog name input updates on change", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const createButtons = screen.getAllByText("新建部门");
    await user.click(createButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    const nameInput = screen.getByPlaceholderText("请输入部门名称");
    await user.type(nameInput, "My Dept");

    expect((nameInput as HTMLInputElement).value).toBe("My Dept");
  });

  // ── Create: empty name toast with whitespace only ───────────────────

  test("shows toast error when creating with whitespace-only name", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const createButtons = screen.getAllByText("新建部门");
    await user.click(createButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("请输入部门名称"), "   ");
    await user.click(screen.getByText("创建"));

    expect(mockToastError).toHaveBeenCalledWith("请输入部门名称");
    expect(mockCreateDepartment).not.toHaveBeenCalled();
  });

  // ── Edit: empty name toast with whitespace only ─────────────────────

  test("shows toast error when editing with whitespace-only name", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTestId("department-edit-button");
    await user.click(editButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    const nameInput = screen.getByPlaceholderText("请输入部门名称");
    await user.clear(nameInput);
    await user.type(nameInput, "   ");

    await user.click(screen.getByText("保存"));

    expect(mockToastError).toHaveBeenCalledWith("请输入部门名称");
    expect(mockUpdateDepartment).not.toHaveBeenCalled();
  });

  // ── Delete: non-Error throw ────────────────────────────────────────

  test("shows toast error for non-Error throw from deleteDepartment", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockDeleteDepartment.mockRejectedValue("string delete error");

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTestId("department-delete-button");
    await user.click(deleteButtons[0]!);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("string delete error");
    });

    vi.restoreAllMocks();
  });

  // ── Edit: non-Error throw from updateDepartment ─────────────────────

  test("shows toast error for non-Error throw from updateDepartment", async () => {
    const user = userEvent.setup();
    mockUpdateDepartment.mockRejectedValue("string update error");

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTestId("department-edit-button");
    await user.click(editButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    await user.click(screen.getByText("保存"));

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("string update error");
    });
  });

  // ── Create: non-Error throw from createDepartment ───────────────────

  test("shows toast error for non-Error throw from createDepartment", async () => {
    const user = userEvent.setup();
    mockCreateDepartment.mockRejectedValue("string create error");

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const createButtons = screen.getAllByText("新建部门");
    await user.click(createButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("请输入部门名称"), "New");
    await user.click(screen.getByText("创建"));

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("string create error");
    });
  });

  // ── Create: successful creation closes dialog and resets ────────────

  test("create success closes dialog and resets form fields", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const createButtons = screen.getAllByText("新建部门");
    await user.click(createButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("请输入部门名称"), "New Dept");
    await user.type(
      screen.getByPlaceholderText("请输入部门描述（可选）"),
      "Desc",
    );
    await user.click(screen.getByText("创建"));

    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith("部门已创建");
      expect(mockCreateDepartment).toHaveBeenCalled();
    });

    // After success, dialog should close
    await waitFor(() => {
      expect(
        screen.queryByText("创建一个新的组织部门"),
      ).not.toBeInTheDocument();
    });
  });

  // ── Edit: successful update closes dialog and resets ────────────────

  test("edit success closes dialog and resets form fields", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTestId("department-edit-button");
    await user.click(editButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    const nameInput = screen.getByPlaceholderText("请输入部门名称");
    await user.clear(nameInput);
    await user.type(nameInput, "Updated");

    await user.click(screen.getByText("保存"));

    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith("部门已更新");
      expect(mockUpdateDepartment).toHaveBeenCalled();
    });

    // After success, dialog should close
    await waitFor(() => {
      expect(screen.queryByText("修改部门信息")).not.toBeInTheDocument();
    });
  });

  // ── Edit dialog: description textarea onChange via fireEvent ────────

  test("edit dialog description textarea onChange is triggered", async () => {
    const user = userEvent.setup();
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTestId("department-edit-button");
    await user.click(editButtons[0]!);

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("请输入部门描述（可选）"),
      ).toBeInTheDocument();
    });

    const descInput = screen.getByPlaceholderText("请输入部门描述（可选）");
    // The description should be pre-filled
    expect((descInput as HTMLInputElement).value).toBe(
      "Software development team",
    );

    // Clear and type new value
    await user.clear(descInput);
    await user.type(descInput, "New");

    expect((descInput as HTMLInputElement).value).toBe("New");
  });

  // ── Loading to loaded transition ────────────────────────────────────

  test("hides loading indicator after departments are loaded", async () => {
    render(<DepartmentsPage />);
    // Initially shows loading
    expect(screen.getByText("加载中...")).toBeInTheDocument();
    // After load, loading is gone
    await waitFor(() => {
      expect(screen.queryByText("加载中...")).not.toBeInTheDocument();
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
      expect(screen.getByTestId("department-list")).toHaveTextContent(
        /Engineering/i,
      );
    });
  });

  // ── Loading to error transition ─────────────────────────────────────

  test("hides loading indicator after error", async () => {
    mockListDepartments.mockRejectedValue(new Error("Network error"));
    render(<DepartmentsPage />);
    expect(screen.getByText("加载中...")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("加载中...")).not.toBeInTheDocument();
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  // ── Loading to empty transition ─────────────────────────────────────

  test("hides loading indicator when no departments exist", async () => {
    mockListDepartments.mockResolvedValue({
      departments: [],
      total: 0,
      limit: 50,
      offset: 0,
    });
    render(<DepartmentsPage />);
    expect(screen.getByText("加载中...")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("加载中...")).not.toBeInTheDocument();
      expect(screen.getByText("暂无部门")).toBeInTheDocument();
    });
  });

  // ── Department card with description present ────────────────────────

  test("displays description when department has one", async () => {
    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByText("Software development team")).toBeInTheDocument();
      expect(screen.getByText("Marketing and growth")).toBeInTheDocument();
    });
  });

  // ── Create form: button disabled during submission ──────────────────

  test("create button is disabled while submission is in progress", async () => {
    const user = userEvent.setup();
    mockCreateDepartment.mockReturnValue(new Promise(() => {}));

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const createButtons = screen.getAllByText("新建部门");
    await user.click(createButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("请输入部门名称"), "New");
    await user.click(screen.getByText("创建"));

    await waitFor(() => {
      expect(screen.getByText("创建中...")).toBeInTheDocument();
    });
  });

  // ── Edit form: button disabled during submission ────────────────────

  test("save button is disabled while update is in progress", async () => {
    const user = userEvent.setup();
    mockUpdateDepartment.mockReturnValue(new Promise(() => {}));

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTestId("department-edit-button");
    await user.click(editButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    await user.click(screen.getByText("保存"));

    await waitFor(() => {
      expect(screen.getByText("保存中...")).toBeInTheDocument();
    });
  });

  // ── Delete button: disabled during deletion ─────────────────────────

  test("delete button is disabled while deletion is in progress", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockDeleteDepartment.mockReturnValue(new Promise(() => {}));

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTestId("department-delete-button");
    await user.click(deleteButtons[0]!);

    await waitFor(() => {
      expect(deleteButtons[0]).toBeDisabled();
    });

    vi.restoreAllMocks();
  });

  // ── Edit dialog: non-Error throw from updateDepartment ─────────────

  test("shows toast error for non-Error throw from updateDepartment on edit", async () => {
    const user = userEvent.setup();
    mockUpdateDepartment.mockRejectedValue("string update err");

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTestId("department-edit-button");
    await user.click(editButtons[0]!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("请输入部门名称")).toBeInTheDocument();
    });

    await user.click(screen.getByText("保存"));

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("string update err");
    });
  });

  // ── Department card with member_count as null ───────────────────────

  test("handles department with null member_count", async () => {
    mockListDepartments.mockResolvedValue({
      departments: [
        {
          id: "dept-null",
          name: "Null Dept",
          description: "Has null member count",
          member_count: null,
          agent_count: 0,
          skill_count: 0,
          created_at: "2025-01-01T00:00:00Z",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByText("Null Dept")).toBeInTheDocument();
      // React renders null as nothing, so the text becomes " 成员" (with leading space)
      expect(screen.getByText(/成员/)).toBeInTheDocument();
    });
  });

  // ── Resource reallocation delete flow ─────────────────────────────

  test("opens reallocation dialog when department has resources", async () => {
    const user = userEvent.setup();
    mockGetDepartmentResources.mockResolvedValue({
      resources: [
        {
          id: "res-1",
          resource_type: "agent",
          resource_id: "agent-alpha",
          visibility: "department",
          owner_id: "user-1",
        },
        {
          id: "res-2",
          resource_type: "skill",
          resource_id: "skill-beta",
          visibility: "private",
          owner_id: "user-2",
        },
      ],
      department_name: "Engineering",
    });

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    await user.click(screen.getAllByTestId("department-delete-button")[0]!);

    await waitFor(() => {
      expect(screen.getByText("删除部门 - 资源重分配")).toBeInTheDocument();
      expect(screen.getByText("agent-alpha")).toBeInTheDocument();
      expect(screen.getByText("skill-beta")).toBeInTheDocument();
      expect(screen.getByText("部门级")).toBeInTheDocument();
      expect(screen.getByText("私有")).toBeInTheDocument();
    });
  });

  test("deletes department with resources as private by default", async () => {
    const user = userEvent.setup();
    mockGetDepartmentResources.mockResolvedValue({
      resources: [
        {
          id: "res-1",
          resource_type: "agent",
          resource_id: "agent-alpha",
          visibility: "department",
          owner_id: "user-1",
        },
      ],
      department_name: "Engineering",
    });

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    await user.click(screen.getAllByTestId("department-delete-button")[0]!);
    await waitFor(() => {
      expect(screen.getByText("确认删除")).toBeInTheDocument();
    });
    await user.click(screen.getByText("确认删除"));

    await waitFor(() => {
      expect(mockDeleteDepartment).toHaveBeenCalledWith("dept-1", undefined);
      expect(mockToastSuccess).toHaveBeenCalledWith("部门已删除");
    });
  });

  test("deletes department with resources reassigned to another department", async () => {
    const user = userEvent.setup();
    mockGetDepartmentResources.mockResolvedValue({
      resources: [
        {
          id: "res-1",
          resource_type: "agent",
          resource_id: "agent-alpha",
          visibility: "department",
          owner_id: "user-1",
        },
      ],
      department_name: "Engineering",
    });

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    await user.click(screen.getAllByTestId("department-delete-button")[0]!);
    await waitFor(() => {
      expect(screen.getByLabelText("重分配到目标部门")).toBeInTheDocument();
    });
    await user.click(screen.getByLabelText("重分配到目标部门"));
    await user.click(screen.getByText("确认删除"));

    await waitFor(() => {
      expect(mockDeleteDepartment).toHaveBeenCalledWith("dept-1", "dept-2");
    });
  });

  test("changes and clears reallocation target before canceling", async () => {
    const user = userEvent.setup();
    mockGetDepartmentResources.mockResolvedValue({
      resources: [
        {
          id: "res-1",
          resource_type: "agent",
          resource_id: "agent-alpha",
          visibility: "department",
          owner_id: "user-1",
        },
      ],
      department_name: "Engineering",
    });

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    await user.click(screen.getAllByTestId("department-delete-button")[0]!);
    await waitFor(() => {
      expect(screen.getByLabelText("重分配到目标部门")).toBeInTheDocument();
    });

    await user.click(screen.getByLabelText("重分配到目标部门"));
    const targetSelect = screen.getByDisplayValue("Marketing");
    fireEvent.change(targetSelect, { target: { value: "dept-3" } });
    expect(targetSelect).toHaveValue("dept-3");

    await user.click(
      screen.getByLabelText("降级为私有（资源变为私有，部门关联清除）"),
    );
    expect(screen.queryByDisplayValue("Marketing")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "取消" }));
    await waitFor(() => {
      expect(
        screen.queryByText("删除部门 - 资源重分配"),
      ).not.toBeInTheDocument();
    });
    expect(mockDeleteDepartment).not.toHaveBeenCalled();
  });

  test("shows error when loading resources for delete fails", async () => {
    const user = userEvent.setup();
    mockGetDepartmentResources.mockRejectedValue(
      new Error("Resource lookup failed"),
    );

    render(<DepartmentsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });

    await user.click(screen.getAllByTestId("department-delete-button")[0]!);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("Resource lookup failed");
    });
  });

  test("does not fetch departments outside the admin route boundary", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: "regular-user",
        email: "user@example.com",
        system_role: "user",
        needs_setup: false,
      },
      isAuthenticated: true,
      isLoading: false,
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(<DepartmentsPage />);

    expect(mockListDepartments).not.toHaveBeenCalled();
  });

  test("department admins can view departments but cannot mutate them", async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: "dept-admin",
        email: "dept-admin@example.com",
        system_role: "department_admin",
        needs_setup: false,
      },
      isAuthenticated: true,
      isLoading: false,
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(<DepartmentsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("department-list")).toBeInTheDocument();
    });
    expect(screen.queryByText("新建部门")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("department-edit-button"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("department-delete-button"),
    ).not.toBeInTheDocument();
  });
});
