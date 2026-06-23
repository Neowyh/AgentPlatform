import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { AgentWelcome } from "@/components/workspace/agent-welcome";

describe("AgentWelcome", () => {
  const mockAgent = {
    name: "Test Agent",
    description: "A test agent description",
    model: null,
    tool_groups: null,
    skills: null,
    visibility: "public",
    owner_id: null,
    department_id: null,
  };

  test("renders the agent name", () => {
    render(<AgentWelcome agent={mockAgent} agentName="Fallback Name" />);
    expect(screen.getByText("Test Agent")).toBeInTheDocument();
  });

  test("renders agent description when provided", () => {
    render(<AgentWelcome agent={mockAgent} agentName="Fallback" />);
    expect(screen.getByText("A test agent description")).toBeInTheDocument();
  });

  test("does not render description when agent has no description", () => {
    render(
      <AgentWelcome
        agent={{
          name: "Agent",
          description: "",
          model: null,
          tool_groups: null,
          skills: null,
          visibility: "public",
          owner_id: null,
          department_id: null,
        }}
        agentName="Fallback"
      />,
    );
    expect(
      screen.queryByText("A test agent description"),
    ).not.toBeInTheDocument();
  });

  test("uses agentName as fallback when agent is null", () => {
    render(<AgentWelcome agent={null} agentName="Fallback Name" />);
    expect(screen.getByText("Fallback Name")).toBeInTheDocument();
  });

  test("uses agentName as fallback when agent is undefined", () => {
    render(<AgentWelcome agent={undefined} agentName="Fallback Name" />);
    expect(screen.getByText("Fallback Name")).toBeInTheDocument();
  });

  test("prefers agent.name over agentName", () => {
    render(<AgentWelcome agent={mockAgent} agentName="Should Not Show" />);
    expect(screen.getByText("Test Agent")).toBeInTheDocument();
    expect(screen.queryByText("Should Not Show")).not.toBeInTheDocument();
  });

  test("renders the bot icon", () => {
    render(<AgentWelcome agent={mockAgent} agentName="Test" />);
    // The BotIcon from lucide-react should be rendered
    const iconContainer = document.querySelector(".bg-primary\\/10");
    expect(iconContainer).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <AgentWelcome agent={mockAgent} agentName="Test" className="my-class" />,
    );
    const wrapper = document.querySelector(".my-class");
    expect(wrapper).toBeInTheDocument();
  });

  test("renders centered layout", () => {
    render(<AgentWelcome agent={mockAgent} agentName="Test" />);
    const wrapper = document.querySelector(".flex.flex-col.items-center");
    expect(wrapper).toBeInTheDocument();
  });

  test("renders agent with empty description", () => {
    render(
      <AgentWelcome
        agent={{
          name: "Agent",
          description: "",
          model: null,
          tool_groups: null,
          skills: null,
          visibility: "public",
          owner_id: null,
          department_id: null,
        }}
        agentName="Test"
      />,
    );
    // Empty string description should not render the <p> tag
    const paragraphs = document.querySelectorAll("p");
    expect(paragraphs.length).toBe(0);
  });
});
