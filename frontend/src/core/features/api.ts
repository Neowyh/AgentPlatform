import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

export interface FeaturesResponse {
  /**
   * Legacy custom-agent flag. The backend still reports it, but no frontend
   * code consumes it: the `/api/agents` router it gated is no longer mounted
   * (agent management goes through the canonical `/api/resources` surface).
   */
  agents_api?: { enabled: boolean };
  browser_control?: { enabled: boolean };
  mcp_tasks?: { enabled: boolean };
  subagent_batches?: {
    enabled?: boolean;
    repository_available?: boolean;
    worker_running?: boolean;
    max_running?: number;
  };
  knowledge?: {
    enabled: boolean;
    provider_available: boolean;
    worker_running: boolean;
    max_file_size: number;
    supported_extensions: string[];
  };
  conversation_references?: {
    enabled?: boolean;
    max_references?: number;
  };
}

export interface KnowledgeCapability {
  enabled: boolean;
  providerAvailable: boolean;
  workerRunning: boolean;
  maxFileSize: number;
  supportedExtensions: string[];
}

export interface ConversationReferencesCapability {
  enabled: boolean;
  maxReferences: number;
}

export interface SubagentBatchesCapability {
  repositoryAvailable: boolean;
  workerRunning: boolean;
  maxRunning: number;
}

export async function fetchFeatures(): Promise<FeaturesResponse> {
  const res = await fetch(`${getBackendBaseURL()}/api/features`);
  if (!res.ok) {
    throw new Error(`Failed to load features: ${res.statusText}`);
  }
  return (await res.json()) as FeaturesResponse;
}

export async function fetchKnowledgeCapability(): Promise<KnowledgeCapability> {
  const feature = (await fetchFeatures()).knowledge;
  return {
    enabled: feature?.enabled ?? false,
    providerAvailable: feature?.provider_available ?? false,
    workerRunning: feature?.worker_running ?? false,
    maxFileSize: feature?.max_file_size ?? 0,
    supportedExtensions: feature?.supported_extensions ?? [],
  };
}

export async function fetchBrowserControlEnabled(): Promise<boolean> {
  return (await fetchFeatures()).browser_control?.enabled ?? false;
}

export async function fetchMcpTasksEnabled(): Promise<boolean> {
  return (await fetchFeatures()).mcp_tasks?.enabled ?? false;
}

export async function fetchSubagentBatchesCapability(): Promise<SubagentBatchesCapability> {
  const feature = (await fetchFeatures()).subagent_batches;
  const legacyEnabled = feature?.enabled ?? false;
  return {
    repositoryAvailable: feature?.repository_available ?? legacyEnabled,
    workerRunning: feature?.worker_running ?? legacyEnabled,
    maxRunning: feature?.max_running ?? 0,
  };
}

export async function fetchConversationReferencesCapability(): Promise<ConversationReferencesCapability> {
  const features = await fetchFeatures();
  const capability = features.conversation_references;
  const maxReferences = capability?.max_references;
  return {
    enabled: capability?.enabled === true,
    maxReferences:
      typeof maxReferences === "number" &&
      Number.isInteger(maxReferences) &&
      maxReferences > 0
        ? maxReferences
        : 0,
  };
}
