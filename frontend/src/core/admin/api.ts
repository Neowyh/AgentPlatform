import { extractError } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import type { Tool } from "@/core/tools/types";

import type { AdminResource, Department, User } from "./types";

// ── User management ──────────────────────────────────────────────

export async function listUsers(params?: {
  department_id?: string;
  role?: string;
  limit?: number;
  offset?: number;
}): Promise<{ users: User[]; total: number; limit: number; offset: number }> {
  const baseURL = getBackendBaseURL();
  const searchParams = new URLSearchParams();
  if (params?.department_id)
    searchParams.set("department_id", params.department_id);
  if (params?.role) searchParams.set("role", params.role);
  if (params?.limit !== undefined)
    searchParams.set("limit", String(params.limit));
  if (params?.offset !== undefined)
    searchParams.set("offset", String(params.offset));

  const queryString = searchParams.toString();
  const url = `${baseURL}/api/admin/users${queryString ? `?${queryString}` : ""}`;

  const res = await fetch(url);
  if (!res.ok) return extractError(res, "Failed to list users");
  return res.json() as Promise<{
    users: User[];
    total: number;
    limit: number;
    offset: number;
  }>;
}

export async function updateUserRole(
  userId: string,
  role: string,
): Promise<{ success: boolean; user_id: string; new_role: string }> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(`${baseURL}/api/admin/users/${userId}/role`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role }),
  });
  if (!res.ok) return extractError(res, "Failed to update user role");
  return res.json() as Promise<{
    success: boolean;
    user_id: string;
    new_role: string;
  }>;
}

export async function toggleUserStatus(
  userId: string,
): Promise<{ success: boolean; user_id: string; disabled: boolean }> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(`${baseURL}/api/admin/users/${userId}/status`, {
    method: "PATCH",
  });
  if (!res.ok) return extractError(res, "Failed to toggle user status");
  return res.json() as Promise<{
    success: boolean;
    user_id: string;
    disabled: boolean;
  }>;
}

export async function createUser(data: {
  email: string;
  password: string;
  username: string;
  role: string;
  department_id?: string;
}): Promise<User> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(`${baseURL}/api/admin/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) return extractError(res, "Failed to create user");
  return res.json() as Promise<User>;
}

export async function updateUser(
  userId: string,
  data: { username?: string; department_id?: string },
): Promise<User> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(`${baseURL}/api/admin/users/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) return extractError(res, "Failed to update user");
  return res.json() as Promise<User>;
}

export async function deleteUser(
  userId: string,
  resourceStrategy: "transfer" | "delete" | "soft_delete",
  targetUserId?: string,
): Promise<{ success: boolean; user_id: string; resource_strategy: string }> {
  const baseURL = getBackendBaseURL();
  const params = new URLSearchParams({ resource_strategy: resourceStrategy });
  if (targetUserId) params.set("target_user_id", targetUserId);
  const res = await fetch(
    `${baseURL}/api/admin/users/${userId}?${params.toString()}`,
    { method: "DELETE" },
  );
  if (!res.ok) return extractError(res, "Failed to delete user");
  return res.json() as Promise<{
    success: boolean;
    user_id: string;
    resource_strategy: string;
  }>;
}

// ── Department management ────────────────────────────────────────

export async function listDepartments(params?: {
  limit?: number;
  offset?: number;
}): Promise<{
  departments: Department[];
  total: number;
  limit: number;
  offset: number;
}> {
  const baseURL = getBackendBaseURL();
  const searchParams = new URLSearchParams();
  if (params?.limit !== undefined)
    searchParams.set("limit", String(params.limit));
  if (params?.offset !== undefined)
    searchParams.set("offset", String(params.offset));

  const queryString = searchParams.toString();
  const url = `${baseURL}/api/admin/departments${queryString ? `?${queryString}` : ""}`;

  const res = await fetch(url);
  if (!res.ok) return extractError(res, "Failed to list departments");
  return res.json() as Promise<{
    departments: Department[];
    total: number;
    limit: number;
    offset: number;
  }>;
}

export async function createDepartment(data: {
  name: string;
  description?: string;
}): Promise<Department> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(`${baseURL}/api/admin/departments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) return extractError(res, "Failed to create department");
  return res.json() as Promise<Department>;
}

export async function updateDepartment(
  deptId: string,
  data: { name?: string; description?: string },
): Promise<{ success: boolean }> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(`${baseURL}/api/admin/departments/${deptId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) return extractError(res, "Failed to update department");
  return res.json() as Promise<{ success: boolean }>;
}

export async function getDepartmentResources(deptId: string): Promise<{
  department_id: string;
  department_name: string;
  resources: Array<{
    id: string;
    resource_type: string;
    resource_id: string;
    visibility: string;
    owner_id: string;
  }>;
  total_count: number;
}> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(
    `${baseURL}/api/admin/departments/${deptId}/resources`,
  );
  if (!res.ok) return extractError(res, "Failed to get department resources");
  return res.json() as Promise<{
    department_id: string;
    department_name: string;
    resources: Array<{
      id: string;
      resource_type: string;
      resource_id: string;
      visibility: string;
      owner_id: string;
    }>;
    total_count: number;
  }>;
}

export async function deleteDepartment(
  deptId: string,
  targetDeptId?: string,
): Promise<void> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(`${baseURL}/api/admin/departments/${deptId}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_dept_id: targetDeptId ?? null }),
  });
  if (!res.ok) return extractError(res, "Failed to delete department");
}

// ── Resource management ─────────────────────────────────────────

export async function listResources(params?: {
  resource_type?: string;
  limit?: number;
  offset?: number;
}): Promise<{
  resources: AdminResource[];
  total: number;
  limit: number;
  offset: number;
}> {
  const baseURL = getBackendBaseURL();
  const searchParams = new URLSearchParams();
  if (params?.resource_type)
    searchParams.set("resource_type", params.resource_type);
  if (params?.limit !== undefined)
    searchParams.set("limit", String(params.limit));
  if (params?.offset !== undefined)
    searchParams.set("offset", String(params.offset));

  const queryString = searchParams.toString();
  const url = `${baseURL}/api/admin/resources${queryString ? `?${queryString}` : ""}`;

  const res = await fetch(url);
  if (!res.ok) return extractError(res, "Failed to list resources");
  return res.json() as Promise<{
    resources: AdminResource[];
    total: number;
    limit: number;
    offset: number;
  }>;
}

// ── Admin stats ──────────────────────────────────────────────────

export interface AdminStats {
  total_users: number;
  total_departments: number;
  total_agents: number;
  total_tools: number;
  total_skills: number;
  total_workflows: number;
  total_resources: number;
  audit_logs: number;
  pending_applications: number;
}

export async function getAdminStats(): Promise<AdminStats> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(`${baseURL}/api/admin/stats`);
  if (!res.ok) return extractError(res, "Failed to get admin stats");
  return res.json() as Promise<AdminStats>;
}

// ── Tool management ──────────────────────────────────────────────

export async function listTools(params?: {
  group?: string;
  search?: string;
}): Promise<{ tools: Tool[]; total: number }> {
  const baseURL = getBackendBaseURL();
  const searchParams = new URLSearchParams();
  if (params?.group) searchParams.set("group", params.group);
  if (params?.search) searchParams.set("search", params.search);

  const queryString = searchParams.toString();
  const url = `${baseURL}/api/tools${queryString ? `?${queryString}` : ""}`;

  const res = await fetch(url);
  if (!res.ok) return extractError(res, "Failed to list tools");
  return res.json() as Promise<{ tools: Tool[]; total: number }>;
}

export async function testTool(
  toolName: string,
  params: Record<string, unknown>,
): Promise<{
  success: boolean;
  tool: string;
  result?: string;
  error?: string;
}> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(
    `${baseURL}/api/tools/${encodeURIComponent(toolName)}/test`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ params }),
    },
  );
  if (!res.ok) return extractError(res, "Failed to test tool");
  return res.json() as Promise<{
    success: boolean;
    tool: string;
    result?: string;
    error?: string;
  }>;
}

// ── Resource lifecycle (canonical) ───────────────────────────────

async function resourceLifecycleAction(
  resourceId: string,
  action: "archive" | "suspend" | "restore",
  actionLabel: string,
): Promise<void> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(
    `${baseURL}/api/resources/${encodeURIComponent(resourceId)}/${action}`,
    { method: "POST" },
  );
  if (!res.ok) return extractError(res, `Failed to ${actionLabel} resource`);
}

export function archiveResource(resourceId: string): Promise<void> {
  return resourceLifecycleAction(resourceId, "archive", "archive");
}

export function suspendResource(resourceId: string): Promise<void> {
  return resourceLifecycleAction(resourceId, "suspend", "suspend");
}

export function restoreResource(resourceId: string): Promise<void> {
  return resourceLifecycleAction(resourceId, "restore", "restore");
}
