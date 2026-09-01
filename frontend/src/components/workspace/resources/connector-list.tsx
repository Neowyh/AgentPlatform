"use client";

import Link from "next/link";

import { useAuth } from "@/core/auth/AuthProvider";
import { useMCPConfig } from "@/core/mcp/hooks";

import { ToolSettingsPage } from "../settings/tool-settings-page";

export function ConnectorList() {
  const { config, isLoading } = useMCPConfig();
  const { user } = useAuth();
  const isAdmin =
    user?.system_role === "super_admin" ||
    user?.system_role === "department_admin";

  if (isLoading) {
    return <div className="text-muted-foreground">Loading...</div>;
  }

  const servers = Object.entries(config?.mcp_servers ?? {});

  return (
    <div className="space-y-6">
      {isAdmin && <ToolSettingsPage />}
      {servers.length === 0 ? (
        <div className="text-muted-foreground">No connectors found</div>
      ) : (
        <div className="workbench-resource-grid grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {servers.map(([name, server]) => (
            <div
              key={name}
              className="workbench-resource-card rounded-lg border p-4"
            >
              <h3 className="type-section-title font-medium">{name}</h3>
              <p className="text-muted-foreground type-body">
                {server.description}
              </p>
              <span
                className={`type-body mt-2 inline-block rounded-full px-2 py-1 ${
                  server.enabled
                    ? "bg-green-100 text-green-800"
                    : "bg-gray-100 text-gray-800"
                }`}
              >
                {server.enabled ? "Enabled" : "Disabled"}
              </span>
              {server.enabled && (
                <Link
                  className="text-primary type-body mt-2 block hover:underline"
                  href={`/workspace/chats/new?connector=${encodeURIComponent(name)}`}
                >
                  Use in new conversation
                </Link>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
