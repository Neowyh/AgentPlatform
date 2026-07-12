import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

const mockListResources = vi.fn();
const mockReplace = vi.fn();

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
    user: {
      id: "admin-1",
      email: "admin@example.com",
      system_role: "department_admin",
    },
  }),
}));

import ResourcesPage from "@/app/workspace/admin/resources/page";

describe("ResourcesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
});
