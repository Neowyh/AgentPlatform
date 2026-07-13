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

import AdminLayout from "@/app/workspace/admin/layout";

describe("AdminLayout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(cleanup);

  test.each(["super_admin", "department_admin"] as const)(
    "renders admin content for %s",
    async (system_role) => {
      mockGetServerSideUser.mockResolvedValue({
        tag: "authenticated",
        user: {
          id: "admin-id",
          email: "admin@example.com",
          system_role,
          needs_setup: false,
        },
      });

      render(await AdminLayout({ children: <p>admin content</p> }));

      expect(screen.getByText("admin content")).toBeInTheDocument();
      expect(mockRedirect).not.toHaveBeenCalled();
    },
  );

  test("redirects a normal user before rendering admin content", async () => {
    mockGetServerSideUser.mockResolvedValue({
      tag: "authenticated",
      user: {
        id: "user-id",
        email: "user@example.com",
        system_role: "user",
        needs_setup: false,
      },
    });

    await expect(
      AdminLayout({ children: <p>admin content</p> }),
    ).rejects.toThrow("NEXT_REDIRECT");
    expect(mockRedirect).toHaveBeenCalledWith("/workspace");
  });

  test("redirects an unauthenticated request to the workspace login flow", async () => {
    mockGetServerSideUser.mockResolvedValue({ tag: "unauthenticated" });

    await expect(
      AdminLayout({ children: <p>admin content</p> }),
    ).rejects.toThrow("NEXT_REDIRECT");
    expect(mockRedirect).toHaveBeenCalledWith("/login");
  });
});
