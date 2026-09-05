/**
 * API functions for file uploads
 */

import { extractError } from "../api/errors";
import { fetch } from "../api/fetcher";
import { getBackendBaseURL } from "../config";

export interface UploadedFileInfo {
  filename: string;
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
  skipped_files: string[];
}

export interface ListFilesResponse {
  files: UploadedFileInfo[];
  count: number;
}

export interface UploadLimits {
  max_files: number;
  max_file_size: number;
  max_total_size: number;
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
 * Load the upload limits enforced by the gateway for a thread
 */
export async function getUploadLimits(threadId: string): Promise<UploadLimits> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${threadId}/uploads/limits`,
  );

  if (!response.ok) {
    await extractError(response, "Failed to load upload limits");
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
  const encodedFilename = encodeURIComponent(filename);
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${threadId}/uploads/${encodedFilename}`,
    {
      method: "DELETE",
    },
  );

  if (!response.ok) {
    await extractError(response, "Failed to delete file");
  }

  return response.json();
}
