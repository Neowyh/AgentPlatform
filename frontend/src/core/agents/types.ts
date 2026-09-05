export interface AgentModelSettings {
  temperature?: number | null;
  max_tokens?: number | null;
}

export type ReasoningEffort = "low" | "medium" | "high";

export interface Agent {
  resource_id?: string;
  slug?: string;
  read_only?: boolean;
  visibility?: string;
  owner_id?: string | null;
  department_id?: string | null;
  latest_version?: number;
  draft_revision?: number;
  can_modify?: boolean;
  system_owned?: boolean;
  is_favorited?: boolean;
  summary?: string;
  name: string;
  description: string;
  model: string | null;
  tool_groups: string[] | null;
  skills: string[] | null;
  allowed_subagents?: string[] | null;
  model_settings?: AgentModelSettings | null;
  thinking_enabled?: boolean | null;
  reasoning_effort?: ReasoningEffort | null;
  soul?: string | null;
}

export interface CreateAgentRequest {
  name: string;
  description?: string;
  model?: string | null;
  tool_groups?: string[] | null;
  skills?: string[] | null;
  allowed_subagents?: string[] | null;
  model_settings?: AgentModelSettings | null;
  thinking_enabled?: boolean | null;
  reasoning_effort?: ReasoningEffort | null;
  soul?: string;
  visibility?: string;
}

export interface UpdateAgentRequest {
  description?: string | null;
  model?: string | null;
  tool_groups?: string[] | null;
  skills?: string[] | null;
  allowed_subagents?: string[] | null;
  model_settings?: AgentModelSettings | null;
  thinking_enabled?: boolean | null;
  reasoning_effort?: ReasoningEffort | null;
  soul?: string | null;
  draft_revision?: number;
  visibility?: string | null;
}
