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

export interface StepDef {
  id: string;
  type: string;

  // agent step
  agent?: string;
  prompt?: string;

  // tool step
  tool?: string;
  params?: Record<string, unknown>;

  // human_review step
  message?: string;
  input_schema?: Record<string, unknown>;
  approvers?: string[];

  // condition step
  expression?: string;
  then?: string | StepDef;
  else?: string | StepDef;

  // parallel / loop
  steps?: StepDef[];
  items?: string;
  max_iterations?: number;

  // common
  condition?: string;
  timeout?: number;
  retry?: RetryPolicy;
  on_error?: string;
}

export interface WorkflowSummary {
  name: string;
  description: string;
  version: string;
  steps_count: number;
  inputs: Record<string, InputParam>;
  error?: string;
}

export interface WorkflowDetail extends WorkflowSummary {
  yaml_content: string;
  steps: StepDef[];
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
  current_step: string | null;
  error: string | null;
  steps: Record<string, StepStatus>;
}

export interface ReviewData {
  approved: boolean;
  comment?: string;
}
