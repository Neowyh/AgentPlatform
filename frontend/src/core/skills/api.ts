import { extractError, formatErrorMessage } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type { Skill } from "./type";

export async function loadSkills(): Promise<Skill[]> {
  const response = await fetch(`${getBackendBaseURL()}/api/skills`);
  if (!response.ok) {
    await extractError(response, "Failed to load skills");
  }
  const json = await response.json();
  return json.skills as Skill[];
}

export async function enableSkill(
  skillName: string,
  enabled: boolean,
): Promise<void> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/skills/${skillName}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        enabled,
      }),
    },
  );
  if (!response.ok) {
    await extractError(
      response,
      `Failed to ${enabled ? "enable" : "disable"} skill`,
    );
  }
}

export interface SubmitApplicationRequest {
  request_level: "department" | "public";
  reason: string;
}

export interface SkillApplicationResponse {
  id: string;
  skill_id: string;
  skill_name: string;
  applicant_id: string;
  request_level: string;
  department_id: string | null;
  reason: string;
  status: string;
  submitted_at: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_comment: string | null;
}

export async function submitSkillApplication(
  skillName: string,
  request: SubmitApplicationRequest,
): Promise<SkillApplicationResponse> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/skills/${encodeURIComponent(skillName)}/apply`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );
  if (!response.ok) {
    await extractError(response, "Failed to submit skill application");
  }
  return response.json();
}

export async function listSkillApplications(
  status?: string,
): Promise<{ applications: SkillApplicationResponse[] }> {
  const params = status
    ? `?status=${encodeURIComponent(status)}&resource_type=skill`
    : "?resource_type=skill";
  const response = await fetch(
    `${getBackendBaseURL()}/api/visibility-applications${params}`,
  );
  if (!response.ok) {
    await extractError(response, "Failed to list skill applications");
  }
  return response.json();
}

export async function reviewSkillApplication(
  applicationId: string,
  action: "approved" | "rejected",
  comment = "",
): Promise<{ message: string }> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/visibility-applications/${encodeURIComponent(applicationId)}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ action, comment, version: 1 }),
    },
  );
  if (!response.ok) {
    await extractError(response, "Failed to review skill application");
  }
  return response.json();
}

export interface InstallSkillRequest {
  thread_id: string;
  path: string;
}

export interface InstallSkillResponse {
  success: boolean;
  skill_name: string;
  message: string;
}

export async function installSkill(
  request: InstallSkillRequest,
): Promise<InstallSkillResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/skills/install`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errorMessage = await formatErrorMessage(
      response,
      "Failed to install skill",
    );
    return {
      success: false,
      skill_name: "",
      message: errorMessage,
    };
  }

  return response.json();
}
