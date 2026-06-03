import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type { Tool, ToolTestResult } from "./types";

export async function listTools(params?: {
  group?: string;
  search?: string;
}): Promise<{ tools: Tool[]; total: number }> {
  const searchParams = new URLSearchParams();
  if (params?.group) searchParams.set("group", params.group);
  if (params?.search) searchParams.set("search", params.search);

  const query = searchParams.toString();
  const url = `${getBackendBaseURL()}/api/tools${query ? `?${query}` : ""}`;

  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load tools: ${res.statusText}`);
  return res.json() as Promise<{ tools: Tool[]; total: number }>;
}

export async function getToolDetail(name: string): Promise<Tool> {
  const res = await fetch(`${getBackendBaseURL()}/api/tools/${name}`);
  if (!res.ok) throw new Error(`Tool '${name}' not found`);
  return res.json() as Promise<Tool>;
}

export async function testTool(
  name: string,
  params: Record<string, unknown>,
): Promise<ToolTestResult> {
  const res = await fetch(`${getBackendBaseURL()}/api/tools/${name}/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ params }),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `Failed to test tool: ${res.statusText}`);
  }
  return res.json() as Promise<ToolTestResult>;
}
