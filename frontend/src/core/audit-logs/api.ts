import { extractError } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type { AuditLog, AuditLogListResponse } from "./types";

export async function listAuditLogs(params?: {
  actor_id?: string;
  action?: string;
  resource_type?: string;
  start_date?: string;
  end_date?: string;
  page?: number;
  page_size?: number;
}): Promise<AuditLogListResponse> {
  const baseURL = getBackendBaseURL();
  const searchParams = new URLSearchParams();
  if (params?.actor_id) searchParams.set("actor_id", params.actor_id);
  if (params?.action) searchParams.set("action", params.action);
  if (params?.resource_type)
    searchParams.set("resource_type", params.resource_type);
  if (params?.start_date) searchParams.set("start_date", params.start_date);
  if (params?.end_date) searchParams.set("end_date", params.end_date);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size)
    searchParams.set("page_size", String(params.page_size));

  const queryString = searchParams.toString();
  const url = `${baseURL}/api/admin/audit-logs${queryString ? `?${queryString}` : ""}`;

  const res = await fetch(url);
  if (!res.ok) {
    await extractError(res, "Failed to list audit logs");
  }
  return res.json() as Promise<AuditLogListResponse>;
}

export async function getAuditLogDetail(logId: string): Promise<AuditLog> {
  const baseURL = getBackendBaseURL();
  const url = `${baseURL}/api/admin/audit-logs/${encodeURIComponent(logId)}`;

  const res = await fetch(url);
  if (!res.ok) {
    await extractError(res, "Failed to get audit log detail");
  }
  return res.json() as Promise<AuditLog>;
}
