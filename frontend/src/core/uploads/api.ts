/**
 * API functions for file uploads
 */

import { extractError } from "../api/errors";
import { fetch } from "../api/fetcher";
import { getBackendBaseURL } from "../config";

export interface UploadedFileInfo {
  filename: string;
  original_filename?: string;
  size: number;
  path: string;
  virtual_path: string;
  artifact_url: string;
  extension?: string;
  modified?: number;
  markdown_file?: string;
  markdown_path?: string;
  markdown_virtual_path?: string;
  markdown_artifact_url?: string;
}

export interface UploadResponse {
  success: boolean;
  files: UploadedFileInfo[];
  message: string;
  skipped_files?: string[];
}

export interface ListFilesResponse {
  files: UploadedFileInfo[];
  count: number;
}

export type EvidenceMode = "document" | "code" | "hybrid";

export interface CodeEvidencePackage {
  package_id: string;
  original_filename: string;
  accepted: string[];
  excluded: string[];
  rejected: Array<{ path: string; reason: string }>;
  compressed_size: number;
  expanded_size: number;
  source_virtual_path: string;
}

export async function uploadCodeEvidencePackage(
  threadId: string,
  file: File,
): Promise<CodeEvidencePackage> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${threadId}/uploads/code-evidence-package`,
    { method: "POST", body: formData },
  );
  if (!response.ok) await extractError(response, "Code package upload failed");
  return response.json();
}

export async function listCodeEvidencePackages(
  threadId: string,
): Promise<CodeEvidencePackage[]> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${threadId}/uploads/code-evidence-package`,
  );
  if (!response.ok)
    await extractError(response, "Failed to list code packages");
  return response.json();
}

export async function deleteCodeEvidencePackage(
  threadId: string,
  packageId: string,
): Promise<{ success: boolean }> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${threadId}/uploads/code-evidence-package/${encodeURIComponent(packageId)}`,
    { method: "DELETE" },
  );
  if (!response.ok)
    await extractError(response, "Failed to delete code package");
  return response.json();
}

/**
 * Upload files to a thread
 */
export async function uploadFiles(
  threadId: string,
  files: File[],
): Promise<UploadResponse> {
  const formData = new FormData();

  files.forEach((file) => {
    formData.append("files", file);
  });

  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${threadId}/uploads`,
    {
      method: "POST",
      body: formData,
    },
  );

  if (!response.ok) {
    await extractError(response, "Upload failed");
  }

  return response.json();
}

/**
 * List all uploaded files for a thread
 */
export async function listUploadedFiles(
  threadId: string,
): Promise<ListFilesResponse> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${threadId}/uploads/list`,
  );

  if (!response.ok) {
    await extractError(response, "Failed to list uploaded files");
  }

  return response.json();
}

/**
 * Delete an uploaded file
 */
export async function deleteUploadedFile(
  threadId: string,
  filename: string,
): Promise<{ success: boolean; message: string }> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${threadId}/uploads/${filename}`,
    {
      method: "DELETE",
    },
  );

  if (!response.ok) {
    await extractError(response, "Failed to delete file");
  }

  return response.json();
}
