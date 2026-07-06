export interface Tool {
  name: string;
  description: string;
  group: string;
  requires_network: boolean;
  configurable: boolean;
  param_schema: Record<string, unknown>;
  config_schema?: Record<string, unknown>;
  config: Record<string, unknown>;
  visibility?: "private" | "department" | "public";
}

export interface ToolTestResult {
  success: boolean;
  result: unknown;
  error?: string;
}
