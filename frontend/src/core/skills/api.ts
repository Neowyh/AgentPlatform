import { extractError, formatErrorMessage } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type { Skill } from "./type";

const RESOURCE_UUID_PATTERN = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;

export async function loadSkills(): Promise<Skill[]> {
  const canonicalResponse = await fetch(
    `${getBackendBaseURL()}/api/resources?type=skill&limit=200`,
  );
  if (!canonicalResponse.ok) {
    await extractError(canonicalResponse, "Failed to load canonical skills");
  }
  const canonical = (await canonicalResponse.json()) as {
    items: Array<{
      id: string;
      slug: string;
      display_name: string;
      owner_id: string;
      visibility: string;
      scope_department_id: string | null;
      system_owned: boolean;
      can_modify: boolean;
    }>;
    mode?: "legacy" | "dual" | "canonical";
  };
  const canonicalSkills = canonical.items.map(
    (resource): Skill => ({
      resource_id: resource.id,
      slug: resource.slug,
      read_only: !resource.can_modify,
      name: resource.display_name,
      description: resource.display_name,
      category: resource.can_modify ? "custom" : "public",
      license: "",
      enabled: true,
      visibility: resource.visibility,
      owner_id: resource.owner_id,
      department_id: resource.scope_department_id,
    }),
  );
  if (canonical.mode === "canonical") return canonicalSkills;
  const response = await fetch(`${getBackendBaseURL()}/api/skills`);
  if (!response.ok) {
    await extractError(response, "Failed to load skills");
  }
  const json = (await response.json()) as { skills: Skill[] };
  if (canonical.mode === "legacy") return json.skills;
  const canonicalKeys = new Set(
    canonical.items.map((item) => `${item.slug}\u0000${item.owner_id}`),
  );
  const bundledSlugs = new Set(
    canonical.items
      .filter((item) => item.system_owned)
      .map((item) => item.slug),
  );
  const legacy = json.skills.filter((item) => {
    const slug = item.slug ?? item.name;
    return (
      !bundledSlugs.has(slug) &&
      !canonicalKeys.has(`${slug}\u0000${item.owner_id ?? ""}`)
    );
  });
  return [...legacy, ...canonicalSkills];
}

export async function enableSkill(
  skillName: string,
  enabled: boolean,
): Promise<void> {
  if (RESOURCE_UUID_PATTERN.test(skillName)) {
    throw new Error(
      "Skill enable/disable is managed by the resource lifecycle in canonical mode; use /api/resources/{id}/archive or /api/resources/{id}/suspend",
    );
  }
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

  if (response.status === 410) {
    return {
      success: false,
      skill_name: "",
      message:
        "Skill installation is not available in canonical mode; use resource workflows to create a Skill",
    };
  }

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
