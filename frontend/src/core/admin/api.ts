import { extractError } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import type { Tool } from "@/core/tools/types";

import type { Department, User } from "./types";

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

export async function disableUser(userId: string): Promise<void> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(`${baseURL}/api/admin/users/${userId}`, {
    method: "DELETE",
  });
  if (!res.ok) return extractError(res, "Failed to disable user");
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

export async function deleteDepartment(deptId: string): Promise<void> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(`${baseURL}/api/admin/departments/${deptId}`, {
    method: "DELETE",
  });
  if (!res.ok) return extractError(res, "Failed to delete department");
}

// ── Admin stats ──────────────────────────────────────────────────

export interface AdminStats {
  total_users: number;
  total_departments: number;
  total_agents: number;
  total_tools: number;
  total_skills: number;
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
