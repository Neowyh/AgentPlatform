"use client";

import { useAutomations } from "@/core/automations";

export function AutomationList() {
  const { automations, isLoading } = useAutomations();

  if (isLoading) {
    return <div className="text-muted-foreground">Loading...</div>;
  }

  if (!automations || automations.length === 0) {
    return <div className="text-muted-foreground">No automations found</div>;
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {automations.map((automation) => (
        <div key={automation.id} className="rounded-lg border p-4">
          <h3 className="font-medium">{automation.name}</h3>
          <p className="text-muted-foreground text-sm">{automation.id}</p>
          <span
            className={`mt-2 inline-block rounded-full px-2 py-1 text-xs ${
              automation.status === "active"
                ? "bg-green-100 text-green-800"
                : "bg-gray-100 text-gray-800"
            }`}
          >
            {automation.status}
          </span>
        </div>
      ))}
    </div>
  );
}
