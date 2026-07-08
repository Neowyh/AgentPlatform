import { describe, expect, it } from "vitest";

import type { Department, User, UserRole } from "@/core/admin/types";

describe("User", () => {
  it("can be constructed with all required and optional fields", () => {
    const user: User = {
      id: "u-1",
      username: "alice",
      role: "user",
      department_id: "d-1",
      department_name: "Engineering",
      disabled: false,
      created_at: "2024-01-01T00:00:00Z",
      last_login: "2024-01-15T00:00:00Z",
    };
    expect(user.id).toBe("u-1");
    expect(user.username).toBe("alice");
    expect(user.role).toBe("user");
    expect(user.department_name).toBe("Engineering");
    expect(user.disabled).toBe(false);
  });

  it("handles nullable and missing optional fields", () => {
    const user: User = {
      id: "u-2",
      username: "bob",
      role: "super_admin",
      department_id: null,
      created_at: "2024-01-01T00:00:00Z",
      last_login: null,
    };
    expect(user.department_id).toBeNull();
    expect(user.last_login).toBeNull();
    expect(user.department_name).toBeUndefined();
    expect(user.disabled).toBeUndefined();
  });

  it("accepts all valid UserRole values", () => {
    const roles: UserRole[] = ["user", "department_admin", "super_admin"];
    for (const role of roles) {
      const user: User = {
        id: "u-3",
        username: "test",
        role,
        department_id: null,
        created_at: "2024-01-01T00:00:00Z",
        last_login: null,
      };
      expect(user.role).toBe(role);
    }
  });
});

describe("Department", () => {
  it("can be constructed with all fields", () => {
    const dept: Department = {
      id: "d-1",
      name: "Engineering",
      description: "The engineering team",
      member_count: 10,
      agent_count: 3,
      skill_count: 5,
      created_at: "2024-01-01T00:00:00Z",
    };
    expect(dept.id).toBe("d-1");
    expect(dept.agent_count).toBe(3);
    expect(dept.skill_count).toBe(5);
  });

  it("handles nullable member_count", () => {
    const dept: Department = {
      id: "d-2",
      name: "Empty Dept",
      description: "",
      member_count: null,
      agent_count: 0,
      skill_count: 0,
      created_at: "2024-01-01T00:00:00Z",
    };
    expect(dept.member_count).toBeNull();
  });
});
