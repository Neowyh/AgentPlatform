import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const mockGetServerSideUser = vi.fn();
const mockRedirect = vi.fn().mockImplementation(() => {
  throw new Error("NEXT_REDIRECT");
});

vi.mock("next/navigation", () => ({
  redirect: (...args: unknown[]) => mockRedirect(...args),
}));

vi.mock("@/core/auth/server", () => ({
  getServerSideUser: (...args: unknown[]) => mockGetServerSideUser(...args),
}));

import AuditLogsLayout from "@/app/workspace/admin/audit-logs/layout";

describe("AuditLogsLayout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(cleanup);

  test("renders audit logs for a super admin", async () => {
    mockGetServerSideUser.mockResolvedValue({
      tag: "authenticated",
      user: {
        id: "admin-id",
        email: "admin@example.com",
        system_role: "super_admin",
        needs_setup: false,
      },
    });

    render(await AuditLogsLayout({ children: <p>audit content</p> }));

    expect(screen.getByText("audit content")).toBeInTheDocument();
  });

  test("redirects a department admin before rendering audit logs", async () => {
    mockGetServerSideUser.mockResolvedValue({
      tag: "authenticated",
      user: {
        id: "department-admin-id",
        email: "department-admin@example.com",
        system_role: "department_admin",
        needs_setup: false,
      },
    });

    await expect(
      AuditLogsLayout({ children: <p>audit content</p> }),
    ).rejects.toThrow("NEXT_REDIRECT");
    expect(mockRedirect).toHaveBeenCalledWith("/workspace");
  });
});
