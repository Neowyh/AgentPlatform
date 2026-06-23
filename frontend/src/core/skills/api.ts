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
