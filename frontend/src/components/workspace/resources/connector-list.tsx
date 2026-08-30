"use client";

import { useMCPConfig } from "@/core/mcp/hooks";

export function ConnectorList() {
  const { config, isLoading } = useMCPConfig();

  if (isLoading) {
    return <div className="text-muted-foreground">Loading...</div>;
  }

  if (!config?.mcp_servers) {
    return <div className="text-muted-foreground">No connectors found</div>;
  }

  const servers = Object.entries(config.mcp_servers);

  if (servers.length === 0) {
    return <div className="text-muted-foreground">No connectors found</div>;
  }

  return (
    <div className="workbench-resource-grid grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {servers.map(([name, server]) => (
        <div
          key={name}
          className="workbench-resource-card rounded-lg border p-4"
        >
          <h3 className="font-medium">{name}</h3>
          <p className="text-muted-foreground text-base">
            {server.description}
          </p>
          <span
            className={`mt-2 inline-block rounded-full px-2 py-1 text-base ${
              server.enabled
                ? "bg-green-100 text-green-800"
                : "bg-gray-100 text-gray-800"
            }`}
          >
            {server.enabled ? "Enabled" : "Disabled"}
          </span>
        </div>
      ))}
    </div>
  );
}
