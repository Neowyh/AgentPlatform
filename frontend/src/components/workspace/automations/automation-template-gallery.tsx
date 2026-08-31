"use client";

import { useAutomationTemplates } from "@/core/automations";

export function AutomationTemplateGallery() {
  const { templates, isLoading } = useAutomationTemplates();

  if (isLoading) {
    return <div className="text-muted-foreground">Loading...</div>;
  }

  if (!templates || templates.length === 0) {
    return <div className="text-muted-foreground">No templates found</div>;
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {templates.map((template) => (
        <div key={template.id} className="rounded-lg border p-4">
          <h3 className="type-section-title font-medium">{template.name}</h3>
          <p className="text-muted-foreground type-body">
            {template.description}
          </p>
          <span className="bg-secondary text-secondary-foreground type-body mt-2 inline-block rounded-full px-2 py-1">
            {template.category}
          </span>
        </div>
      ))}
    </div>
  );
}
