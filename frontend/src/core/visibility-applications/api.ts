import { extractError } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type { ApplicationsResponse, VisibilityApplication } from "./types";

export async function listVisibilityApplications(params?: {
  status?: string;
  resource_type?: string;
  target_visibility?: string;
  applicant_id?: string;
  page?: number;
  page_size?: number;
}): Promise<ApplicationsResponse> {
  const baseURL = getBackendBaseURL();
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);
  if (params?.resource_type)
    searchParams.set("resource_type", params.resource_type);
  if (params?.target_visibility)
    searchParams.set("target_visibility", params.target_visibility);
  if (params?.applicant_id)
    searchParams.set("applicant_id", params.applicant_id);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size)
    searchParams.set("page_size", String(params.page_size));

  const queryString = searchParams.toString();
  const url = `${baseURL}/api/visibility-applications${queryString ? `?${queryString}` : ""}`;

  const res = await fetch(url);
  if (!res.ok) {
    await extractError(res, "Failed to list visibility applications");
  }
  return res.json() as Promise<ApplicationsResponse>;
}

export interface CreateVisibilityApplicationRequest {
  resource_type: string;
  resource_id: string;
  target_visibility: string;
  reason: string;
}

export async function createVisibilityApplication(
  request: CreateVisibilityApplicationRequest,
): Promise<VisibilityApplication> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(
    `${baseURL}/api/resources/${encodeURIComponent(request.resource_id)}/visibility-applications`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target_visibility: request.target_visibility,
        reason: request.reason,
      }),
    },
  );
  if (!res.ok) {
    await extractError(res, "Failed to submit visibility application");
  }
  return res.json() as Promise<VisibilityApplication>;
}

export async function reviewVisibilityApplication(
  applicationId: string,
  action: "approved" | "rejected",
  comment: string,
  version: number,
): Promise<VisibilityApplication> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(
    `${baseURL}/api/visibility-applications/${encodeURIComponent(applicationId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, comment, version }),
    },
  );
  if (!res.ok) {
    await extractError(res, "Failed to review visibility application");
  }
  return res.json() as Promise<VisibilityApplication>;
}

export async function withdrawVisibilityApplication(
  applicationId: string,
  version: number,
): Promise<{ success: boolean }> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(
    `${baseURL}/api/visibility-applications/${encodeURIComponent(applicationId)}/withdraw`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version }),
    },
  );
  if (!res.ok) {
    await extractError(res, "Failed to withdraw visibility application");
  }
  return res.json() as Promise<{ success: boolean }>;
}
