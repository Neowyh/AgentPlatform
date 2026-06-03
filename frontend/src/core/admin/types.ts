export type UserRole = "user" | "department_admin" | "super_admin";

export interface User {
  id: string;
  username: string;
  role: UserRole;
  department_id: string | null;
  department_name?: string;
  created_at: string;
  last_login: string | null;
}

export interface Department {
  id: string;
  name: string;
  description: string;
  member_count: number;
  agent_count: number;
  skill_count: number;
  created_at: string;
}
