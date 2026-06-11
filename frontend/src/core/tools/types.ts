export interface Tool {
  name: string;
  description: string;
  group: string;
  requires_network: boolean;
  configurable: boolean;
  param_schema: Record<string, unknown>;
  config_schema?: Record<string, unknown>;
}

export interface ToolTestResult {
  success: boolean;
  result: unknown;
  error?: string;
}
