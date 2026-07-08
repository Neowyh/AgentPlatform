import { describe, expect, it } from "vitest";

import type { AuditLog, AuditLogListResponse } from "@/core/audit-logs/types";

describe("AuditLog", () => {
  it("can be constructed with all fields", () => {
    const log: AuditLog = {
      id: "log-1",
      actor_id: "u-1",
      action: "user.login",
      resource_type: "user",
      resource_id: "u-1",
      detail: "User logged in from 192.168.1.1",
      ip_address: "192.168.1.1",
      created_at: "2024-01-01T00:00:00Z",
    };
    expect(log.id).toBe("log-1");
    expect(log.action).toBe("user.login");
  });

  it("handles nullable fields", () => {
    const log: AuditLog = {
      id: "log-2",
      actor_id: null,
      action: "system.startup",
      resource_type: null,
      resource_id: null,
      detail: null,
      ip_address: null,
      created_at: "2024-01-01T00:00:00Z",
    };
    expect(log.actor_id).toBeNull();
    expect(log.resource_type).toBeNull();
    expect(log.detail).toBeNull();
    expect(log.ip_address).toBeNull();
  });
});

describe("AuditLogListResponse", () => {
  it("can be constructed with pagination fields", () => {
    const log: AuditLog = {
      id: "log-1",
      actor_id: null,
      action: "test",
      resource_type: null,
      resource_id: null,
      detail: null,
      ip_address: null,
      created_at: "2024-01-01T00:00:00Z",
    };
    const response: AuditLogListResponse = {
      items: [log],
      total: 1,
      page: 1,
      page_size: 20,
    };
    expect(response.items).toHaveLength(1);
    expect(response.total).toBe(1);
    expect(response.page).toBe(1);
    expect(response.page_size).toBe(20);
  });
});
