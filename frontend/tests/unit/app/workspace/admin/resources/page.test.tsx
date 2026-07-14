import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

const mockListResources = vi.fn();
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
}));

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: () => ({
    user: mockUser,
  }),
}));

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
  });

  test("renders canonical resource total and requests next page", async () => {
    const user = userEvent.setup();
    render(<ResourcesPage />);

    await waitFor(() => {
      expect(screen.getAllByTestId("resource-row")).toHaveLength(60);
    });

    expect(screen.getByText("1 / 2")).toBeInTheDocument();
    expect(mockListResources).toHaveBeenCalledWith({
      resource_type: undefined,
      limit: 50,
      offset: 0,
    });

    await user.click(screen.getByText("下一页"));

    await waitFor(() => {
      expect(mockListResources).toHaveBeenLastCalledWith({
        resource_type: undefined,
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

    await user.click(screen.getByText("工作流"));

    await waitFor(() => {
      expect(mockListResources).toHaveBeenLastCalledWith({
        resource_type: "workflow",
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
});
