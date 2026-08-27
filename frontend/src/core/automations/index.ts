"use client";

export interface AutomationTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
}

export interface Automation {
  id: string;
  name: string;
  template_id: string;
  status: "active" | "inactive";
}

export function useAutomationTemplates() {
  // TODO: Replace with actual API call
  const templates: AutomationTemplate[] = [
    {
      id: "daily-report",
      name: "Daily Report",
      description: "Generate daily work reports",
      category: "reporting",
    },
    {
      id: "weekly-report",
      name: "Weekly Report",
      description: "Generate weekly work reports",
      category: "reporting",
    },
    {
      id: "meeting-minutes",
      name: "Meeting Minutes",
      description: "Summarize meeting discussions",
      category: "meetings",
    },
  ];

  return {
    templates,
    isLoading: false,
  };
}

export function useAutomations() {
  // TODO: Replace with actual API call
  const automations: Automation[] = [
    {
      id: "automation-1",
      name: "My Daily Report",
      template_id: "daily-report",
      status: "active",
    },
    {
      id: "automation-2",
      name: "Team Weekly",
      template_id: "weekly-report",
      status: "inactive",
    },
  ];

  return {
    automations,
    isLoading: false,
  };
}
