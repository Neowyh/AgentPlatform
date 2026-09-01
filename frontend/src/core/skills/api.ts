import { extractError } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import { getResourceSummary } from "@/core/resources/summaries";

import type { Skill } from "./type";

type CanonicalSkill = {
  id: string;
  slug: string;
  display_name: string;
  description?: string | null;
  owner_id: string;
  visibility: string;
  scope_department_id: string | null;
  system_owned: boolean;
  can_modify: boolean;
  is_favorited?: boolean;
  latest_version?: number;
  draft_revision?: number;
};

export async function loadSkills(): Promise<Skill[]> {
  const items: CanonicalSkill[] = [];
  const limit = 200;
  for (let offset = 0; ; offset += limit) {
    const response = await fetch(
      `${getBackendBaseURL()}/api/resources?type=skill&limit=${limit}${offset ? `&offset=${offset}` : ""}`,
    );
    if (!response.ok)
      await extractError(response, "Failed to load canonical skills");
    const canonical = (await response.json()) as {
      items: CanonicalSkill[];
      total: number;
    };
    items.push(...canonical.items);
    if (items.length >= canonical.total || canonical.items.length === 0) break;
  }
  return items.map(
    (resource): Skill => ({
      resource_id: resource.id,
      slug: resource.slug,
      read_only: !resource.can_modify,
      name: resource.display_name,
      description: resource.description ?? resource.display_name,
      summary: getResourceSummary(
        resource.slug,
        resource.description ?? resource.display_name,
      ),
      category: resource.can_modify ? "custom" : "public",
      license: "",
      enabled: true,
      visibility: resource.visibility,
      owner_id: resource.owner_id,
      department_id: resource.scope_department_id,
      is_favorited: resource.is_favorited,
      latest_version: resource.latest_version,
      draft_revision: resource.draft_revision,
      can_modify: resource.can_modify,
      system_owned: resource.system_owned,
    }),
  );
}

export async function getSkill(resourceId: string): Promise<Skill> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resourceId)}/published`,
  );
  if (!response.ok) await extractError(response, "Failed to load Skill");
  const payload = (await response.json()) as {
    resource: CanonicalSkill;
    content: {
      name: string;
      description: string;
      license?: string | null;
      allowed_tools?: string[] | null;
      requires_internet?: boolean;
    };
    skill_md?: string;
    version: { version: number; published_at?: string | null };
  };
  const resource = payload.resource;
  return {
    resource_id: resource.id,
    slug: resource.slug,
    name: resource.display_name,
    description: payload.content.description,
    summary: payload.content.description,
    category: resource.can_modify ? "custom" : "public",
    license: payload.content.license ?? "",
    enabled: true,
    visibility: resource.visibility,
    owner_id: resource.owner_id,
    department_id: resource.scope_department_id,
    read_only: !resource.can_modify,
    is_favorited: resource.is_favorited,
    latest_version: resource.latest_version,
    draft_revision: resource.draft_revision,
    can_modify: resource.can_modify,
    system_owned: resource.system_owned,
    allowed_tools: payload.content.allowed_tools,
    requires_internet: payload.content.requires_internet,
    skill_md: payload.skill_md,
    published_at: payload.version.published_at,
  };
}

export async function updateSkill(
  resourceId: string,
  content: string,
  expectedRevision: number,
): Promise<void> {
  const draftResponse = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resourceId)}/skill-draft`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, expected_revision: expectedRevision }),
    },
  );
  if (!draftResponse.ok)
    await extractError(draftResponse, "Failed to save Skill draft");
  const draft = (await draftResponse.json()) as { revision: number };
  const publishResponse = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resourceId)}/publish`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        expected_draft_revision: draft.revision,
        scan_result: {},
      }),
    },
  );
  if (!publishResponse.ok)
    await extractError(publishResponse, "Failed to publish Skill");
}

export async function enableSkill(
  skillName: string,
  enabled: boolean,
): Promise<void> {
  void skillName;
  void enabled;
  throw new Error(
    "Skill enable/disable is managed by the resource lifecycle in canonical mode; use /api/resources/{id}/archive or /api/resources/{id}/suspend",
  );
}

export async function importSkill(archive: File): Promise<void> {
  const body = new FormData();
  body.append("archive", archive);
  const response = await fetch(
    `${getBackendBaseURL()}/api/resources/import/skill`,
    {
      method: "POST",
      body,
    },
  );
  if (!response.ok) await extractError(response, "Failed to import Skill");
}

export async function archiveSkill(resourceId: string): Promise<void> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resourceId)}/archive`,
    { method: "POST" },
  );
  if (!response.ok) await extractError(response, "Failed to archive Skill");
}

export async function exportSkill(resourceId: string): Promise<Blob> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resourceId)}/export`,
  );
  if (!response.ok) await extractError(response, "Failed to export Skill");
  return response.blob();
}

export async function toggleSkillFavorite(
  resourceId: string,
  isFavorited: boolean,
): Promise<void> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resourceId)}/favorite`,
    { method: isFavorited ? "DELETE" : "POST" },
  );
  if (!response.ok)
    await extractError(response, "Failed to update Skill favorite");
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
  void request;
  return {
    success: false,
    skill_name: "",
    message:
      "Skill installation is not available in canonical mode; use resource workflows to create a Skill",
  };
}
