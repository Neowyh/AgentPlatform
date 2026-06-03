import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type { Department, User } from "./types";

// ── User management ──────────────────────────────────────────────

export async function listUsers(params?: {
  department_id?: string;
  role?: string;
}): Promise<{ users: User[]; total: number }> {
  const url = new URL(`${getBackendBaseURL()}/api/admin/users`);
  if (params?.department_id)
    url.searchParams.set("department_id", params.department_id);
  if (params?.role) url.searchParams.set("role", params.role);

  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`Failed to list users: ${res.statusText}`);
  return res.json() as Promise<{ users: User[]; total: number }>;
}

export async function updateUserRole(
  userId: string,
  role: string,
): Promise<User> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/admin/users/${userId}/role`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    },
  );
  if (!res.ok) throw new Error(`Failed to update user role: ${res.statusText}`);
  return res.json() as Promise<User>;
}

export async function disableUser(userId: string): Promise<void> {
  const res = await fetch(`${getBackendBaseURL()}/api/admin/users/${userId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to disable user: ${res.statusText}`);
}

// ── Department management ────────────────────────────────────────

export async function listDepartments(): Promise<{
  departments: Department[];
  total: number;
}> {
  const res = await fetch(`${getBackendBaseURL()}/api/admin/departments`);
  if (!res.ok) throw new Error(`Failed to list departments: ${res.statusText}`);
  return res.json() as Promise<{ departments: Department[]; total: number }>;
}

export async function createDepartment(data: {
  name: string;
  description?: string;
}): Promise<Department> {
  const res = await fetch(`${getBackendBaseURL()}/api/admin/departments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok)
    throw new Error(`Failed to create department: ${res.statusText}`);
  return res.json() as Promise<Department>;
}

export async function updateDepartment(
  deptId: string,
  data: { name?: string; description?: string },
): Promise<Department> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/admin/departments/${deptId}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
  if (!res.ok)
    throw new Error(`Failed to update department: ${res.statusText}`);
  return res.json() as Promise<Department>;
}

export async function deleteDepartment(deptId: string): Promise<void> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/admin/departments/${deptId}`,
    { method: "DELETE" },
  );
  if (!res.ok)
    throw new Error(`Failed to delete department: ${res.statusText}`);
}

// ── Admin stats ──────────────────────────────────────────────────

export interface AdminStats {
  total_users: number;
  total_departments: number;
  total_agents: number;
  total_skills: number;
}

export async function getAdminStats(): Promise<AdminStats> {
  const res = await fetch(`${getBackendBaseURL()}/api/admin/stats`);
  if (!res.ok) throw new Error(`Failed to get admin stats: ${res.statusText}`);
  return res.json() as Promise<AdminStats>;
}
