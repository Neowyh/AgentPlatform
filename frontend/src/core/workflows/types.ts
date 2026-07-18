export interface InputParam {
  type: string;
  required: boolean;
  default: unknown;
  description: string;
}

export interface RetryPolicy {
  max: number;
  backoff: number;
  on_errors: string[];
}

export interface WorkflowNode {
  id: string;
  type: string;
  expression?: string;
  action?: {
    kind: "agent" | "tool";
    name: string;
    params?: Record<string, unknown>;
  };
  branches?: string[];
  join?: string;
  fork?: string;
  roles?: string[];
  writes?: string[];
  retry?: { max_attempts: number; backoff_seconds: number };
}

export interface WorkflowSummary {
  name: string;
  description: string;
  version: string;
  steps_count: number;
  inputs: Record<string, InputParam>;
  visibility: string;
  owner_id: string | null;
  department_id: string | null;
  is_favorited?: boolean;
  error?: string;
}

export interface WorkflowDetail extends WorkflowSummary {
  yaml_content: string;
  schema_version: 2;
  state: Record<string, InputParam>;
  entrypoint: string;
  nodes: WorkflowNode[];
  steps: WorkflowNode[];
  edges: Array<{ from: string; to: string; max_iterations?: number }>;
}

export interface WorkflowRunResult {
  run_id: string;
  status: string;
  workflow: string;
}

export interface StepStatus {
  status: string;
  output: unknown;
  error: string | null;
  retries: number;
  started_at: string | null;
  finished_at: string | null;
}

export interface RunStatus {
  run_id: string;
  workflow: string;
  status: string;
  definition_version?: number;
  snapshot?: Record<string, unknown>;
  error: string | null;
  current_step?: string | null;
  steps?: Record<string, StepStatus>;
}
