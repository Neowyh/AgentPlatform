import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/core/api/fetcher", () => ({
  fetch: vi.fn(),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => "http://localhost:3000"),
}));

describe("admin API", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("getAdminStats sends GET request", async () => {
    const { fetch: mockFetch } = await import("@/core/api/fetcher");
    const mockStats = { users: 5, departments: 2, agents: 3, skills: 10 };
    (mockFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockStats),
    });

    const { getAdminStats } = await import("@/core/admin/api");
    const result = await getAdminStats();

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/admin/stats"),
    );
    expect(result).toEqual(mockStats);
  });

  it("listUsers sends GET request", async () => {
    const { fetch: mockFetch } = await import("@/core/api/fetcher");
    const mockUsers = { users: [], total: 0 };
    (mockFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockUsers),
    });

    const { listUsers } = await import("@/core/admin/api");
    const result = await listUsers();

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/admin/users"),
    );
    expect(result).toEqual(mockUsers);
  });

  it("updateUserRole sends PUT request", async () => {
    const { fetch: mockFetch } = await import("@/core/api/fetcher");
    (mockFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ id: "user-1", system_role: "department_admin" }),
    });

    const { updateUserRole } = await import("@/core/admin/api");
    await updateUserRole("user-1", "department_admin");

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/admin/users/user-1"),
      expect.objectContaining({
        method: "PUT",
      }),
    );
  });

  it("listDepartments sends GET request", async () => {
    const { fetch: mockFetch } = await import("@/core/api/fetcher");
    const mockDepts = { departments: [], total: 0 };
    (mockFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDepts),
    });

    const { listDepartments } = await import("@/core/admin/api");
    const result = await listDepartments();

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/admin/departments"),
    );
    expect(result).toEqual(mockDepts);
  });

  it("createDepartment sends POST request", async () => {
    const { fetch: mockFetch } = await import("@/core/api/fetcher");
    (mockFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: "new-dept", name: "New Department" }),
    });

    const { createDepartment } = await import("@/core/admin/api");
    await createDepartment({ name: "New Department", description: "Test" });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/admin/departments"),
      expect.objectContaining({
        method: "POST",
      }),
    );
  });
});
