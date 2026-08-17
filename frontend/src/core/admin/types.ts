export type UserRole = "user" | "department_admin" | "super_admin";

export interface User {
  id: string;
  username: string;
  role: UserRole;
  department_id: string | null;
  department_name?: string;
  disabled?: boolean;
  created_at: string;
  last_login: string | null;
}

export interface Department {
  id: string;
  name: string;
  description: string;
  member_count: number | null;
  agent_count: number;
  skill_count: number;
  created_at: string;
}

export interface AdminResource {
  id: string;
  resource_type: string;
  resource_type_label: string;
  resource_id: string;
  visibility: string;
  owner_id: string;
  owner_username?: string;
  department_id: string | null;
  lifecycle_status?: string;
  created_at: string | null;
}
