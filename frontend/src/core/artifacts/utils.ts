import { getBackendBaseURL } from "../config";
import { isStaticWebsiteOnly } from "../static-mode";
import type { AgentThread } from "../threads";

function normalizeArtifactPath(filepath: string) {
  return filepath.startsWith("/") ? filepath : `/${filepath}`;
}

export function urlOfArtifact({
  filepath,
  threadId,
  download = false,
  isMock = false,
}: {
  filepath: string;
  threadId: string;
  download?: boolean;
  isMock?: boolean;
}) {
  if (isStaticWebsiteOnly()) {
    return staticDemoArtifactURL({ filepath, threadId, download });
  }
  const artifactPath = normalizeArtifactPath(filepath);
  if (isMock) {
    return `${getBackendBaseURL()}/mock/api/threads/${threadId}/artifacts${artifactPath}${download ? "?download=true" : ""}`;
  }
  return `${getBackendBaseURL()}/api/threads/${threadId}/artifacts${artifactPath}${download ? "?download=true" : ""}`;
}

export function extractArtifactsFromThread(thread: AgentThread) {
  return thread.values.artifacts ?? [];
}

export function resolveArtifactURL(absolutePath: string, threadId: string) {
  if (isStaticWebsiteOnly()) {
    return staticDemoArtifactURL({ filepath: absolutePath, threadId });
  }
  return `${getBackendBaseURL()}/api/threads/${threadId}/artifacts${normalizeArtifactPath(absolutePath)}`;
}

function staticDemoArtifactURL({
  filepath,
  threadId,
  download = false,
}: {
  filepath: string;
  threadId: string;
  download?: boolean;
}) {
  const demoPath = filepath.replace(/^\/mnt\//, "/");
  return `${getBackendBaseURL()}/demo/threads/${threadId}${demoPath}${download ? "?download=true" : ""}`;
}
