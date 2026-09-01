export interface Agent {
  resource_id?: string;
  slug?: string;
  draft_revision?: number;
  name: string;
  description: string;
  summary?: string;
  model: string | null;
  tool_groups: string[] | null;
  skills: string[] | null;
  soul?: string | null;
  read_only?: boolean;
  visibility: string;
  owner_id: string | null;
  department_id: string | null;
  is_favorited?: boolean;
}

export interface CreateAgentRequest {
  name: string;
  description?: string;
  model?: string | null;
  tool_groups?: string[] | null;
  skills?: string[] | null;
  soul?: string;
  visibility?: string;
}

export interface UpdateAgentRequest {
  draft_revision?: number;
  description?: string | null;
  model?: string | null;
  tool_groups?: string[] | null;
  skills?: string[] | null;
  soul?: string | null;
  visibility?: string;
}
