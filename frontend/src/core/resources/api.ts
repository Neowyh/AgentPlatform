import { extractError } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

export interface VisibilityImpactItem {
  resource_id: string;
  slug: string;
  display_name: string;
  type: string;
  owner_id: string;
  current_visibility: string;
  proposed_visibility: string;
  system_owned: boolean;
  blocked: boolean;
  owned_by_actor: boolean;
}

export interface VisibilityImpact {
  direct: VisibilityImpactItem[];
  transitive: VisibilityImpactItem[];
  impacted: VisibilityImpactItem[];
  total: number;
  blocked_count: number;
}

export async function getVisibilityImpact(params: {
  resource_id: string;
  target_visibility: string;
  scope_department_id?: string | null;
}): Promise<VisibilityImpact> {
  const baseURL = getBackendBaseURL();
  const searchParams = new URLSearchParams({
    target_visibility: params.target_visibility,
  });
  if (params.scope_department_id) {
    searchParams.set("scope_department_id", params.scope_department_id);
  }
  const res = await fetch(
    `${baseURL}/api/resources/${encodeURIComponent(params.resource_id)}/visibility-impact?${searchParams.toString()}`,
  );
  if (!res.ok) {
    await extractError(res, "Failed to load visibility impact");
  }
  return res.json() as Promise<VisibilityImpact>;
}

export interface ResourceNotification {
  id: string;
  resource_id: string;
  event: string;
  detail: Record<string, unknown>;
  read_at: string | null;
  created_at: string | null;
}

export interface ResourceNotificationsResponse {
  items: ResourceNotification[];
  total: number;
  offset: number;
  limit: number;
  unread_count: number;
}

export async function listResourceNotifications(params?: {
  offset?: number;
  limit?: number;
}): Promise<ResourceNotificationsResponse> {
  const baseURL = getBackendBaseURL();
  const searchParams = new URLSearchParams();
  if (params?.offset) searchParams.set("offset", String(params.offset));
  if (params?.limit) searchParams.set("limit", String(params.limit));
  const queryString = searchParams.toString();
  const res = await fetch(
    `${baseURL}/api/resources/notifications${queryString ? `?${queryString}` : ""}`,
  );
  if (!res.ok) {
    await extractError(res, "Failed to load resource notifications");
  }
  return res.json() as Promise<ResourceNotificationsResponse>;
}

export async function markResourceNotificationRead(
  notificationId: string,
): Promise<void> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(
    `${baseURL}/api/resources/notifications/${encodeURIComponent(notificationId)}/read`,
    { method: "PUT" },
  );
  if (!res.ok) {
    await extractError(res, "Failed to mark notification as read");
  }
}

export async function markAllResourceNotificationsRead(): Promise<void> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(`${baseURL}/api/resources/notifications/read-all`, {
    method: "PUT",
  });
  if (!res.ok) {
    await extractError(res, "Failed to mark all notifications as read");
  }
}
