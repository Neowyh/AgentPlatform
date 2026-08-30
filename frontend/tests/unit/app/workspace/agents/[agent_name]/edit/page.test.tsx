import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks -- declared BEFORE component import (module hoisting order)
// Uses vi.hoisted() for ALL values referenced inside vi.mock() factories.
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  mutateAsync: vi.fn().mockResolvedValue({}),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ agent_name: "test-agent" }),
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("sonner", () => ({
  toast: { success: mocks.toastSuccess, error: mocks.toastError },
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: {
      agents: { backToGallery: "Back to Gallery" },
      common: { loading: "Loading..." },
    },
    changeLocale: vi.fn(),
  }),
}));

// Agent mock state: mutable object referenced by the vi.mock factory.
const agentState = vi.hoisted(() => ({
  agent: {
    name: "test-agent",
    description: "A test agent",
    model: "gpt-4",
    tool_groups: ["bash", "web"],
    skills: ["web-search", "code-review"],
    soul: "Be helpful",
  } as any,
  isLoading: false as boolean,
}));

vi.mock("@/core/agents", () => ({
  useAgent: vi.fn(() => ({
    agent: agentState.agent,
    isLoading: agentState.isLoading,
    error: null,
  })),
  useUpdateAgent: vi.fn(() => ({
    mutateAsync: mocks.mutateAsync,
    isPending: false,
  })),
}));

vi.mock("@/core/models/hooks", () => ({
  useModels: vi.fn(() => ({
    models: [
      { id: "m1", model: "gpt-4", name: "GPT-4", display_name: "GPT-4" },
      {
        id: "m2",
        model: "claude-3",
        name: "Claude 3",
        display_name: "Claude 3 Opus",
      },
    ],
    tokenUsageEnabled: false,
    isLoading: false,
    error: null,
  })),
}));

vi.mock("@/core/skills/hooks", () => ({
  useSkills: vi.fn(() => ({
    skills: [
      {
        name: "web-search",
        description: "Search the web",
        category: "general",
        license: "MIT",
        enabled: true,
      },
      {
        name: "code-review",
        description: "Review code for issues",
        category: "dev",
        license: "MIT",
        enabled: true,
      },
      {
        name: "no-desc-skill",
        description: "",
        category: "misc",
        license: "MIT",
        enabled: true,
      },
    ],
    isLoading: false,
    error: null,
  })),
}));

vi.mock("@/components/workspace/workspace-breadcrumb", () => ({
  WorkspaceBreadcrumb: () => <div data-testid="breadcrumb" />,
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: any) => (
    <button {...props}>{children}</button>
  ),
}));

vi.mock("@/components/ui/input", () => ({
  Input: (props: any) => <input {...props} />,
}));

vi.mock("@/components/ui/label", () => ({
  Label: ({ children, ...props }: any) => <label {...props}>{children}</label>,
}));

vi.mock("@/components/ui/select", () => ({
  Select: ({
    children,
    defaultValue,
    disabled,
    onValueChange,
    value,
    ...props
  }: any) => (
    <div
      data-testid="select"
      data-default-value={defaultValue}
      data-disabled={disabled}
      {...props}
    >
      <select
        data-testid="select-input"
        aria-hidden="true"
        role="presentation"
        value={value ?? defaultValue ?? ""}
        disabled={disabled}
        onChange={(event) => onValueChange?.(event.target.value)}
      >
        <option value="private">Private</option>
        <option value="department">Department</option>
        <option value="public">Public</option>
      </select>
    </div>
  ),
  SelectContent: ({ children }: any) => <div>{children}</div>,
  SelectItem: ({ children, value }: any) => (
    <div data-value={value}>{children}</div>
  ),
  SelectTrigger: ({ children }: any) => <div>{children}</div>,
  SelectValue: ({ placeholder }: any) => <span>{placeholder}</span>,
}));

vi.mock("@/components/ui/textarea", () => ({
  Textarea: (props: any) => <textarea {...props} />,
}));

// ---------------------------------------------------------------------------
// Import the component under test AFTER all mocks are set up
// ---------------------------------------------------------------------------

import AgentEditPage from "@/app/workspace/agents/[agent_name]/edit/page";
import { useAgent, useUpdateAgent } from "@/core/agents";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DEFAULT_AGENT = {
  name: "test-agent",
  description: "A test agent",
  model: "gpt-4",
  tool_groups: ["bash", "web"],
  skills: ["web-search", "code-review"],
  soul: "Be helpful",
};

/** Find a checkbox by its associated label text (accessible name). */
function getCheckboxByLabel(name: string): HTMLInputElement {
  return screen.getByRole("checkbox", { name });
}

/**
 * Skill checkboxes have accessible names that combine the skill name and
 * description (e.g. "web-search Search the web"). This helper finds them
 * by a partial match on the accessible name.
 */
function getSkillCheckbox(skillName: string): HTMLInputElement {
  const checkboxes = screen.getAllByRole("checkbox");
  const match = checkboxes.find((cb) => {
    const label = cb.closest("label");
    if (!label) return false;
    const nameDiv = label.querySelector(".truncate.text-base.font-medium");
    return nameDiv?.textContent === skillName;
  });
  if (!match) throw new Error(`No checkbox found for skill "${skillName}"`);
  return match as HTMLInputElement;
}

/** Get the model select element. */
function getModelSelect(): HTMLSelectElement {
  return screen.getByRole("combobox");
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  mocks.push.mockClear();
  mocks.toastSuccess.mockClear();
  mocks.toastError.mockClear();

  // Reset agent state to defaults
  agentState.agent = { ...DEFAULT_AGENT };
  agentState.isLoading = false;

  // Reset mockImplementation so the vi.fn reads from agentState at call time
  vi.mocked(useAgent).mockImplementation(() => ({
    agent: agentState.agent,
    isLoading: agentState.isLoading,
    error: null,
  }));

  mocks.mutateAsync = vi.fn().mockResolvedValue({});
  vi.mocked(useUpdateAgent).mockImplementation(
    () =>
      ({
        mutateAsync: mocks.mutateAsync,
        isPending: false,
      }) as unknown as ReturnType<typeof useUpdateAgent>,
  );
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AgentEditPage", () => {
  // =========================================================================
  // Loading state
  // =========================================================================
  describe("loading state", () => {
    test("renders loading indicator when agent is loading", () => {
      agentState.agent = null;
      agentState.isLoading = true;

      render(<AgentEditPage />);
      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });

    test("does not render form when loading", () => {
      agentState.agent = null;
      agentState.isLoading = true;

      render(<AgentEditPage />);
      expect(screen.queryByText("Edit Agent")).not.toBeInTheDocument();
      expect(screen.queryByText("Save Changes")).not.toBeInTheDocument();
    });
  });

  // =========================================================================
  // Not found state
  // =========================================================================
  describe("not found state", () => {
    test("renders agent not found message", () => {
      agentState.agent = null;

      render(<AgentEditPage />);
      expect(screen.getByText("Agent not found")).toBeInTheDocument();
    });

    test("renders back to gallery button in not found state", () => {
      agentState.agent = null;

      render(<AgentEditPage />);
      expect(screen.getByText("Back to Gallery")).toBeInTheDocument();
    });

    test("navigates to agents gallery when back button clicked in not found state", async () => {
      agentState.agent = null;
      const user = userEvent.setup();

      render(<AgentEditPage />);
      await user.click(screen.getByText("Back to Gallery"));
      expect(mocks.push).toHaveBeenCalledWith("/workspace/agents");
    });

    test("does not render form in not found state", () => {
      agentState.agent = null;

      render(<AgentEditPage />);
      expect(screen.queryByText("Edit Agent")).not.toBeInTheDocument();
    });
  });

  // =========================================================================
  // Page header
  // =========================================================================
  describe("page header", () => {
    test("renders page title", () => {
      render(<AgentEditPage />);
      expect(screen.getByText("Edit Agent")).toBeInTheDocument();
    });

    test("renders agent name below the title", () => {
      render(<AgentEditPage />);
      // Agent name appears in the header paragraph and in the disabled input
      const elements = screen.getAllByText("test-agent");
      expect(elements.length).toBeGreaterThanOrEqual(1);
    });

    test("renders breadcrumb component", () => {
      render(<AgentEditPage />);
      expect(screen.getByTestId("breadcrumb")).toBeInTheDocument();
    });

    test("back button navigates to agent detail page", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      // The back button has variant="ghost" -- it is the only ghost button
      const buttons = screen.getAllByRole("button");
      const backButton = buttons.find(
        (b) => b.getAttribute("variant") === "ghost",
      );
      expect(backButton).toBeTruthy();
      await user.click(backButton!);
      expect(mocks.push).toHaveBeenCalledWith("/workspace/agents/test-agent");
    });

    test("cancel button navigates to agent detail page", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      await user.click(screen.getByText("Cancel"));
      expect(mocks.push).toHaveBeenCalledWith("/workspace/agents/test-agent");
    });
  });

  // =========================================================================
  // Save button states
  // =========================================================================
  describe("save button", () => {
    test("renders save button with default text", () => {
      render(<AgentEditPage />);
      expect(screen.getByText("Save Changes")).toBeInTheDocument();
    });

    test("shows saving text when pending", () => {
      vi.mocked(useUpdateAgent).mockImplementation(
        () =>
          ({
            mutateAsync: mocks.mutateAsync,
            isPending: true,
          }) as unknown as ReturnType<typeof useUpdateAgent>,
      );

      render(<AgentEditPage />);
      expect(screen.getByText("Saving...")).toBeInTheDocument();
      expect(screen.queryByText("Save Changes")).not.toBeInTheDocument();
    });

    test("save button is disabled when pending", () => {
      vi.mocked(useUpdateAgent).mockImplementation(
        () =>
          ({
            mutateAsync: mocks.mutateAsync,
            isPending: true,
          }) as unknown as ReturnType<typeof useUpdateAgent>,
      );

      render(<AgentEditPage />);
      const savingBtn = screen.getByText("Saving...").closest("button");
      expect(savingBtn).toBeDisabled();
    });

    test("save button is enabled when not pending", () => {
      render(<AgentEditPage />);
      const saveBtn = screen.getByText("Save Changes").closest("button");
      expect(saveBtn).not.toBeDisabled();
    });
  });

  // =========================================================================
  // Form fields - Name (readonly)
  // =========================================================================
  describe("name field", () => {
    test("renders name input with agent name", () => {
      render(<AgentEditPage />);
      const input = screen.getByDisplayValue("test-agent");
      expect(input).toBeInTheDocument();
    });

    test("name input is disabled", () => {
      render(<AgentEditPage />);
      const input = screen.getByDisplayValue("test-agent");
      expect(input).toBeDisabled();
    });

    test("renders name label", () => {
      render(<AgentEditPage />);
      expect(screen.getByText("Name")).toBeInTheDocument();
    });

    test("renders name cannot be changed hint", () => {
      render(<AgentEditPage />);
      expect(
        screen.getByText("Agent name cannot be changed after creation"),
      ).toBeInTheDocument();
    });
  });

  // =========================================================================
  // Form fields - Description
  // =========================================================================
  describe("description field", () => {
    test("renders description label", () => {
      render(<AgentEditPage />);
      expect(screen.getByText("Description")).toBeInTheDocument();
    });

    test("renders description textarea with agent description", () => {
      render(<AgentEditPage />);
      const textarea = screen.getByPlaceholderText(
        /Describe what this agent does/,
      );
      expect(textarea).toHaveValue("A test agent");
    });

    test("updates description on change", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      const textarea = screen.getByPlaceholderText(
        /Describe what this agent does/,
      );
      await user.clear(textarea);
      await user.type(textarea, "New description");
      expect(textarea).toHaveValue("New description");
    });
  });

  // =========================================================================
  // Form fields - Model
  // =========================================================================
  describe("model field", () => {
    test("renders model label", () => {
      render(<AgentEditPage />);
      expect(screen.getByText("Model")).toBeInTheDocument();
    });

    test("renders model select with current model value", async () => {
      render(<AgentEditPage />);
      const select = getModelSelect();
      await waitFor(() => {
        expect(select.value).toBe("gpt-4");
      });
    });

    test("renders default model option", () => {
      render(<AgentEditPage />);
      expect(screen.getByText("Default model")).toBeInTheDocument();
    });

    test("renders all model options from useModels", () => {
      render(<AgentEditPage />);
      expect(screen.getByText("GPT-4")).toBeInTheDocument();
      expect(screen.getByText("Claude 3 Opus")).toBeInTheDocument();
    });

    test("updates model on change", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      const select = getModelSelect();
      await user.selectOptions(select, "claude-3");
      expect(select.value).toBe("claude-3");
    });

    test("sets model to empty string when default option selected", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      const select = getModelSelect();
      await user.selectOptions(select, "");
      expect(select.value).toBe("");
    });
  });

  // =========================================================================
  // Form fields - Visibility
  // =========================================================================
  describe("visibility field", () => {
    test("renders visibility label", () => {
      render(<AgentEditPage />);
      expect(screen.getByText("Visibility")).toBeInTheDocument();
    });

    test("renders visibility select as enabled", () => {
      render(<AgentEditPage />);
      const select = screen.getByTestId("select");
      expect(select).not.toHaveAttribute("data-disabled");
    });

    test("shows agent visibility from mock data", () => {
      render(<AgentEditPage />);
      const select = screen.getByTestId("select");
      expect(select).toBeInTheDocument();
    });

    test("renders visibility options", () => {
      render(<AgentEditPage />);
      expect(screen.getByText("Private")).toBeInTheDocument();
      expect(screen.getByText("Department")).toBeInTheDocument();
      expect(screen.getByText("Public")).toBeInTheDocument();
    });

    test("renders visibility application hint", () => {
      render(<AgentEditPage />);
      expect(
        screen.getByText(
          "Visibility changes require an application submission",
        ),
      ).toBeInTheDocument();
    });

    test("keeps the edit page open when the application prompt is dismissed", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      fireEvent.change(screen.getByTestId("select-input"), {
        target: { value: "public" },
      });
      await user.click(screen.getByText("Save Changes"));
      expect(
        screen.getByText("Visibility Change Requires Application"),
      ).toBeInTheDocument();

      await user.click(screen.getByText("Stay on Edit Page"));
      expect(
        screen.queryByText("Visibility Change Requires Application"),
      ).not.toBeInTheDocument();
      expect(mocks.mutateAsync).not.toHaveBeenCalled();
    });

    test("navigates to the detail page from the application prompt", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      fireEvent.change(screen.getByTestId("select-input"), {
        target: { value: "department" },
      });
      await user.click(screen.getByText("Save Changes"));
      await user.click(screen.getByText("Go to Detail Page"));

      expect(mocks.push).toHaveBeenCalledWith("/workspace/agents/test-agent");
    });
  });

  // =========================================================================
  // Form fields - Tool Groups
  // =========================================================================
  describe("tool groups", () => {
    test("renders tool groups label", () => {
      render(<AgentEditPage />);
      expect(screen.getByText("Tool Groups")).toBeInTheDocument();
    });

    test("renders all five tool groups", () => {
      render(<AgentEditPage />);
      expect(screen.getByText("File Read")).toBeInTheDocument();
      expect(screen.getByText("File Write")).toBeInTheDocument();
      expect(screen.getByText("Bash")).toBeInTheDocument();
      expect(screen.getByText("Web")).toBeInTheDocument();
      expect(screen.getByText("Enterprise")).toBeInTheDocument();
    });

    test("pre-checks tool groups from agent data", () => {
      render(<AgentEditPage />);
      const bashCheckbox = getCheckboxByLabel("Bash");
      const webCheckbox = getCheckboxByLabel("Web");
      expect(bashCheckbox.checked).toBe(true);
      expect(webCheckbox.checked).toBe(true);
    });

    test("unchecks tool groups not in agent data", () => {
      render(<AgentEditPage />);
      const fileReadCheckbox = getCheckboxByLabel("File Read");
      const fileWriteCheckbox = getCheckboxByLabel("File Write");
      const enterpriseCheckbox = getCheckboxByLabel("Enterprise");
      expect(fileReadCheckbox.checked).toBe(false);
      expect(fileWriteCheckbox.checked).toBe(false);
      expect(enterpriseCheckbox.checked).toBe(false);
    });

    test("toggles a tool group on when unchecked", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      const fileReadCheckbox = getCheckboxByLabel("File Read");
      expect(fileReadCheckbox.checked).toBe(false);
      await user.click(fileReadCheckbox);
      expect(fileReadCheckbox.checked).toBe(true);
    });

    test("toggles a tool group off when checked", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      const bashCheckbox = getCheckboxByLabel("Bash");
      expect(bashCheckbox.checked).toBe(true);
      await user.click(bashCheckbox);
      expect(bashCheckbox.checked).toBe(false);
    });

    test("toggling tool group preserves other selections", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      const bashCheckbox = getCheckboxByLabel("Bash");
      const webCheckbox = getCheckboxByLabel("Web");
      const fileReadCheckbox = getCheckboxByLabel("File Read");

      // Add file:read
      await user.click(fileReadCheckbox);
      expect(fileReadCheckbox.checked).toBe(true);
      expect(bashCheckbox.checked).toBe(true);
      expect(webCheckbox.checked).toBe(true);

      // Remove bash
      await user.click(bashCheckbox);
      expect(bashCheckbox.checked).toBe(false);
      expect(webCheckbox.checked).toBe(true);
      expect(fileReadCheckbox.checked).toBe(true);
    });
  });

  // =========================================================================
  // Form fields - Skills
  // =========================================================================
  describe("skills", () => {
    test("renders skills label", () => {
      render(<AgentEditPage />);
      expect(screen.getByText("Skills")).toBeInTheDocument();
    });

    test("renders all skills", () => {
      render(<AgentEditPage />);
      expect(screen.getByText("web-search")).toBeInTheDocument();
      expect(screen.getByText("code-review")).toBeInTheDocument();
      expect(screen.getByText("no-desc-skill")).toBeInTheDocument();
    });

    test("renders skill descriptions when present", () => {
      render(<AgentEditPage />);
      expect(screen.getByText("Search the web")).toBeInTheDocument();
      expect(screen.getByText("Review code for issues")).toBeInTheDocument();
    });

    test("does not render description div for skill with empty description", () => {
      render(<AgentEditPage />);
      const noDescSkillSection = screen
        .getByText("no-desc-skill")
        .closest("label");
      expect(noDescSkillSection).toBeTruthy();
      // skill.description is "" which is falsy, so the description div is not rendered
      const descDiv = noDescSkillSection!.querySelector(
        ".text-muted-foreground",
      );
      expect(descDiv).toBeNull();
    });

    test("pre-checks skills from agent data", () => {
      render(<AgentEditPage />);
      const webSearchCheckbox = getSkillCheckbox("web-search");
      const codeReviewCheckbox = getSkillCheckbox("code-review");
      expect(webSearchCheckbox.checked).toBe(true);
      expect(codeReviewCheckbox.checked).toBe(true);
    });

    test("unchecks skills not in agent data", () => {
      render(<AgentEditPage />);
      const noDescCheckbox = getSkillCheckbox("no-desc-skill");
      expect(noDescCheckbox.checked).toBe(false);
    });

    test("toggles a skill on when unchecked", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      const noDescCheckbox = getSkillCheckbox("no-desc-skill");
      expect(noDescCheckbox.checked).toBe(false);
      await user.click(noDescCheckbox);
      expect(noDescCheckbox.checked).toBe(true);
    });

    test("toggles a skill off when checked", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      const webSearchCheckbox = getSkillCheckbox("web-search");
      expect(webSearchCheckbox.checked).toBe(true);
      await user.click(webSearchCheckbox);
      expect(webSearchCheckbox.checked).toBe(false);
    });

    test("toggling skill preserves other skill selections", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      const webSearchCheckbox = getSkillCheckbox("web-search");
      const codeReviewCheckbox = getSkillCheckbox("code-review");
      const noDescCheckbox = getSkillCheckbox("no-desc-skill");

      await user.click(noDescCheckbox);
      expect(noDescCheckbox.checked).toBe(true);
      expect(webSearchCheckbox.checked).toBe(true);
      expect(codeReviewCheckbox.checked).toBe(true);

      await user.click(webSearchCheckbox);
      expect(webSearchCheckbox.checked).toBe(false);
      expect(codeReviewCheckbox.checked).toBe(true);
      expect(noDescCheckbox.checked).toBe(true);
    });
  });

  // =========================================================================
  // Form fields - SOUL.md
  // =========================================================================
  describe("SOUL.md field", () => {
    test("renders soul label", () => {
      render(<AgentEditPage />);
      expect(screen.getByText("SOUL.md")).toBeInTheDocument();
    });

    test("renders soul textarea with agent soul data", () => {
      render(<AgentEditPage />);
      const textarea = screen.getByPlaceholderText(/Agent Soul/);
      expect(textarea).toHaveValue("Be helpful");
    });

    test("renders soul hint text", () => {
      render(<AgentEditPage />);
      expect(
        screen.getByText(
          /The soul defines the agent.*personality and behavior/,
        ),
      ).toBeInTheDocument();
    });

    test("updates soul on change", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      const textarea = screen.getByPlaceholderText(/Agent Soul/);
      await user.clear(textarea);
      await user.type(textarea, "You are a coding assistant");
      expect(textarea).toHaveValue("You are a coding assistant");
    });
  });

  // =========================================================================
  // Save handler - success path
  // =========================================================================
  describe("save handler - success", () => {
    test("calls mutateAsync with correct payload on save", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      await user.click(screen.getByText("Save Changes"));
      expect(mocks.mutateAsync).toHaveBeenCalledTimes(1);
      expect(mocks.mutateAsync).toHaveBeenCalledWith({
        name: "test-agent",
        request: {
          description: "A test agent",
          model: "gpt-4",
          tool_groups: ["bash", "web"],
          skills: ["web-search", "code-review"],
          soul: "Be helpful",
        },
      });
    });

    test("shows success toast on successful save", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      await user.click(screen.getByText("Save Changes"));
      await waitFor(() => {
        expect(mocks.toastSuccess).toHaveBeenCalledWith(
          "Agent updated successfully",
        );
      });
    });

    test("navigates to agent detail page after successful save", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      await user.click(screen.getByText("Save Changes"));
      await waitFor(() => {
        expect(mocks.push).toHaveBeenCalledWith("/workspace/agents/test-agent");
      });
    });
  });

  // =========================================================================
  // Save handler - error path
  // =========================================================================
  describe("save handler - error", () => {
    test("shows error toast when mutateAsync throws an Error", async () => {
      mocks.mutateAsync.mockRejectedValue(new Error("Network failure"));
      vi.mocked(useUpdateAgent).mockImplementation(
        () =>
          ({
            mutateAsync: mocks.mutateAsync,
            isPending: false,
          }) as unknown as ReturnType<typeof useUpdateAgent>,
      );

      const user = userEvent.setup();
      render(<AgentEditPage />);

      await user.click(screen.getByText("Save Changes"));
      await waitFor(() => {
        expect(mocks.toastError).toHaveBeenCalledWith("Network failure");
      });
    });

    test("shows error toast for non-Error thrown values", async () => {
      mocks.mutateAsync.mockRejectedValue("string error");
      vi.mocked(useUpdateAgent).mockImplementation(
        () =>
          ({
            mutateAsync: mocks.mutateAsync,
            isPending: false,
          }) as unknown as ReturnType<typeof useUpdateAgent>,
      );

      const user = userEvent.setup();
      render(<AgentEditPage />);

      await user.click(screen.getByText("Save Changes"));
      await waitFor(() => {
        expect(mocks.toastError).toHaveBeenCalledWith("string error");
      });
    });

    test("does not navigate after error", async () => {
      mocks.mutateAsync.mockRejectedValue(new Error("fail"));
      vi.mocked(useUpdateAgent).mockImplementation(
        () =>
          ({
            mutateAsync: mocks.mutateAsync,
            isPending: false,
          }) as unknown as ReturnType<typeof useUpdateAgent>,
      );

      const user = userEvent.setup();
      render(<AgentEditPage />);

      await user.click(screen.getByText("Save Changes"));
      await waitFor(() => {
        expect(mocks.toastError).toHaveBeenCalled();
      });
      expect(mocks.push).not.toHaveBeenCalled();
    });

    test("shows error toast for object thrown values", async () => {
      mocks.mutateAsync.mockRejectedValue({
        code: 500,
        message: "server error",
      });
      vi.mocked(useUpdateAgent).mockImplementation(
        () =>
          ({
            mutateAsync: mocks.mutateAsync,
            isPending: false,
          }) as unknown as ReturnType<typeof useUpdateAgent>,
      );

      const user = userEvent.setup();
      render(<AgentEditPage />);

      await user.click(screen.getByText("Save Changes"));
      await waitFor(() => {
        expect(mocks.toastError).toHaveBeenCalledWith("[object Object]");
      });
    });
  });

  // =========================================================================
  // useEffect - form data initialization from agent
  // =========================================================================
  describe("form data initialization", () => {
    test("initializes form with agent data fields", async () => {
      render(<AgentEditPage />);
      expect(
        screen.getByPlaceholderText(/Describe what this agent does/),
      ).toHaveValue("A test agent");
      await waitFor(() => {
        expect(getModelSelect().value).toBe("gpt-4");
      });
      expect(screen.getByPlaceholderText(/Agent Soul/)).toHaveValue(
        "Be helpful",
      );
    });

    test("handles agent with null description", () => {
      agentState.agent = { ...DEFAULT_AGENT, description: null };

      render(<AgentEditPage />);
      expect(
        screen.getByPlaceholderText(/Describe what this agent does/),
      ).toHaveValue("");
    });

    test("handles agent with null model", async () => {
      agentState.agent = { ...DEFAULT_AGENT, model: null };

      render(<AgentEditPage />);
      const select = getModelSelect();
      await waitFor(() => {
        expect(select.value).toBe("");
      });
    });

    test("handles agent with null tool_groups", () => {
      agentState.agent = { ...DEFAULT_AGENT, tool_groups: null };

      render(<AgentEditPage />);
      const bashCheckbox = getCheckboxByLabel("Bash");
      expect(bashCheckbox.checked).toBe(false);
    });

    test("handles agent with null skills", () => {
      agentState.agent = { ...DEFAULT_AGENT, skills: null };

      render(<AgentEditPage />);
      const webSearchCheckbox = getSkillCheckbox("web-search");
      expect(webSearchCheckbox.checked).toBe(false);
    });

    test("handles agent with null soul", () => {
      agentState.agent = { ...DEFAULT_AGENT, soul: null };

      render(<AgentEditPage />);
      expect(screen.getByPlaceholderText(/Agent Soul/)).toHaveValue("");
    });

    test("handles agent with empty tool_groups array", () => {
      agentState.agent = { ...DEFAULT_AGENT, tool_groups: [] };

      render(<AgentEditPage />);
      const bashCheckbox = getCheckboxByLabel("Bash");
      expect(bashCheckbox.checked).toBe(false);
    });

    test("handles agent with empty skills array", () => {
      agentState.agent = { ...DEFAULT_AGENT, skills: [] };

      render(<AgentEditPage />);
      const webSearchCheckbox = getSkillCheckbox("web-search");
      expect(webSearchCheckbox.checked).toBe(false);
    });

    test("handles agent with all tool groups selected", () => {
      agentState.agent = {
        ...DEFAULT_AGENT,
        tool_groups: ["file:read", "file:write", "bash", "web", "enterprise"],
      };

      render(<AgentEditPage />);
      expect(getCheckboxByLabel("File Read").checked).toBe(true);
      expect(getCheckboxByLabel("File Write").checked).toBe(true);
      expect(getCheckboxByLabel("Bash").checked).toBe(true);
      expect(getCheckboxByLabel("Web").checked).toBe(true);
      expect(getCheckboxByLabel("Enterprise").checked).toBe(true);
    });
  });

  // =========================================================================
  // Save handler - sends updated form data after edits
  // =========================================================================
  describe("save with modified form data", () => {
    test("sends updated description after editing", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      const textarea = screen.getByPlaceholderText(
        /Describe what this agent does/,
      );
      await user.clear(textarea);
      await user.type(textarea, "Updated description");

      await user.click(screen.getByText("Save Changes"));
      await waitFor(() => {
        expect(mocks.mutateAsync).toHaveBeenCalledWith(
          expect.objectContaining({
            request: expect.objectContaining({
              description: "Updated description",
            }),
          }),
        );
      });
    });

    test("sends updated soul after editing", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      const textarea = screen.getByPlaceholderText(/Agent Soul/);
      await user.clear(textarea);
      await user.type(textarea, "New soul content");

      await user.click(screen.getByText("Save Changes"));
      await waitFor(() => {
        expect(mocks.mutateAsync).toHaveBeenCalledWith(
          expect.objectContaining({
            request: expect.objectContaining({
              soul: "New soul content",
            }),
          }),
        );
      });
    });

    test("sends updated model after changing select", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      const select = getModelSelect();
      await user.selectOptions(select, "claude-3");

      await user.click(screen.getByText("Save Changes"));
      await waitFor(() => {
        expect(mocks.mutateAsync).toHaveBeenCalledWith(
          expect.objectContaining({
            request: expect.objectContaining({
              model: "claude-3",
            }),
          }),
        );
      });
    });

    test("sends updated tool_groups after toggling", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      // Uncheck bash, check file:read
      await user.click(getCheckboxByLabel("Bash"));
      await user.click(getCheckboxByLabel("File Read"));

      await user.click(screen.getByText("Save Changes"));
      await waitFor(() => {
        expect(mocks.mutateAsync).toHaveBeenCalledWith(
          expect.objectContaining({
            request: expect.objectContaining({
              tool_groups: expect.arrayContaining(["web", "file:read"]),
            }),
          }),
        );
      });
    });

    test("sends updated skills after toggling", async () => {
      const user = userEvent.setup();
      render(<AgentEditPage />);

      // Uncheck web-search, check no-desc-skill
      await user.click(getSkillCheckbox("web-search"));
      await user.click(getSkillCheckbox("no-desc-skill"));

      await user.click(screen.getByText("Save Changes"));
      await waitFor(() => {
        expect(mocks.mutateAsync).toHaveBeenCalledWith(
          expect.objectContaining({
            request: expect.objectContaining({
              skills: expect.arrayContaining(["code-review", "no-desc-skill"]),
            }),
          }),
        );
      });
    });
  });

  // =========================================================================
  // Edge cases - empty agent data
  // =========================================================================
  describe("edge cases", () => {
    test("renders correctly with agent that has undefined optional fields", () => {
      agentState.agent = {
        name: "test-agent",
        description: "",
        model: null,
        tool_groups: null,
        skills: null,
      };

      render(<AgentEditPage />);
      expect(screen.getByText("Edit Agent")).toBeInTheDocument();
      expect(screen.getByDisplayValue("test-agent")).toBeInTheDocument();
      expect(
        screen.getByPlaceholderText(/Describe what this agent does/),
      ).toHaveValue("");
      expect(screen.getByPlaceholderText(/Agent Soul/)).toHaveValue("");
    });

    test("save button sends correct payload for minimal agent", async () => {
      agentState.agent = {
        name: "test-agent",
        description: "",
        model: null,
        tool_groups: null,
        skills: null,
      };

      const user = userEvent.setup();
      render(<AgentEditPage />);

      await user.click(screen.getByText("Save Changes"));
      await waitFor(() => {
        expect(mocks.mutateAsync).toHaveBeenCalledWith({
          name: "test-agent",
          request: {
            description: "",
            model: null,
            tool_groups: [],
            skills: [],
            soul: "",
          },
        });
      });
    });
  });
});
