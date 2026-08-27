import { describe, expect, it } from "vitest";

import { enUS } from "@/core/i18n/locales/en-US";
import type { Translations } from "@/core/i18n/locales/types";

// ---------------------------------------------------------------------------
// Helper: recursively collect every leaf value and its dotted key path
// ---------------------------------------------------------------------------
function collectLeafPaths(
  obj: Record<string, unknown>,
  prefix = "",
): Array<[string, unknown]> {
  const entries: Array<[string, unknown]> = [];
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      entries.push(...collectLeafPaths(value as Record<string, unknown>, path));
    } else {
      entries.push([path, value]);
    }
  }
  return entries;
}

// ---------------------------------------------------------------------------
// enUS locale -- comprehensive value verification
// ---------------------------------------------------------------------------
describe("enUS locale comprehensive", () => {
  // =======================================================================
  // Type conformance
  // =======================================================================
  describe("type conformance", () => {
    it("enUS conforms to the Translations interface shape", () => {
      // The import itself would fail if enUS didn't match Translations,
      // but we verify it is a non-null object.
      const t: Translations = enUS;
      expect(t).toBeDefined();
      expect(typeof t).toBe("object");
    });

    it("has all expected top-level sections", () => {
      const expectedSections = [
        "locale",
        "common",
        "home",
        "welcome",
        "clipboard",
        "inputBox",
        "sidebar",
        "agents",
        "workflows",
        "breadcrumb",
        "workspace",
        "conversation",
        "chats",
        "pages",
        "toolCalls",
        "uploads",
        "subtasks",
        "tokenUsage",
        "shortcuts",
        "settings",
      ];
      for (const section of expectedSections) {
        expect(enUS).toHaveProperty(section);
        expect(
          Object.keys(
            (enUS as unknown as Record<string, unknown>)[section] as object,
          ).length,
        ).toBeGreaterThan(0);
      }
    });
  });

  // =======================================================================
  // locale
  // =======================================================================
  describe("locale", () => {
    it("locale.localName is 'English'", () => {
      expect(enUS.locale.localName).toBe("English");
    });
  });

  // =======================================================================
  // common
  // =======================================================================
  describe("common", () => {
    const expected: Record<string, string> = {
      home: "Home",
      settings: "Settings",
      delete: "Delete",
      edit: "Edit",
      rename: "Rename",
      share: "Share",
      openInNewWindow: "Open in new window",
      close: "Close",
      more: "More",
      search: "Search",
      loadMore: "Load more",
      download: "Download",
      thinking: "Thinking",
      artifacts: "Artifacts",
      public: "Public",
      custom: "Custom",
      notAvailableInDemoMode: "Not available in demo mode",
      loading: "Loading...",
      version: "Version",
      lastUpdated: "Last updated",
      code: "Code",
      preview: "Preview",
      cancel: "Cancel",
      save: "Save",
      install: "Install",
      create: "Create",
      import: "Import",
      export: "Export",
      exportAsMarkdown: "Export as Markdown",
      exportAsJSON: "Export as JSON",
      exportSuccess: "Conversation exported",
      showAll: "Show all",
      favoritesOnly: "Favorites only",
    };

    for (const [key, value] of Object.entries(expected)) {
      it(`common.${key} is "${value}"`, () => {
        expect(enUS.common).toHaveProperty(key, value);
      });
    }

    it("has the correct number of keys", () => {
      expect(Object.keys(enUS.common)).toHaveLength(
        Object.keys(expected).length,
      );
    });
  });

  // =======================================================================
  // home
  // =======================================================================
  describe("home", () => {
    it("home.docs", () => {
      expect(enUS.home.docs).toBe("Docs");
    });

    it("home.blog", () => {
      expect(enUS.home.blog).toBe("Blog");
    });

    it("has 2 keys", () => {
      expect(Object.keys(enUS.home)).toHaveLength(2);
    });
  });

  // =======================================================================
  // welcome
  // =======================================================================
  describe("welcome", () => {
    it("welcome.greeting", () => {
      expect(enUS.welcome.greeting).toBe("Hello, again!");
    });

    it("welcome.description contains iDeer brand", () => {
      expect(enUS.welcome.description).toContain("iDeer");
    });

    it("welcome.createYourOwnSkill", () => {
      expect(enUS.welcome.createYourOwnSkill).toBe("Create Your Own Skill");
    });

    it("welcome.createYourOwnSkillDescription contains iDeer", () => {
      expect(enUS.welcome.createYourOwnSkillDescription).toContain("iDeer");
    });

    it("has 4 keys", () => {
      expect(Object.keys(enUS.welcome)).toHaveLength(4);
    });
  });

  // =======================================================================
  // clipboard
  // =======================================================================
  describe("clipboard", () => {
    const expected: Record<string, string> = {
      copyToClipboard: "Copy to clipboard",
      copiedToClipboard: "Copied to clipboard",
      failedToCopyToClipboard: "Failed to copy to clipboard",
      linkCopied: "Link copied to clipboard",
    };

    for (const [key, value] of Object.entries(expected)) {
      it(`clipboard.${key}`, () => {
        expect(enUS.clipboard).toHaveProperty(key, value);
      });
    }

    it("has 4 keys", () => {
      expect(Object.keys(enUS.clipboard)).toHaveLength(4);
    });
  });

  // =======================================================================
  // inputBox
  // =======================================================================
  describe("inputBox", () => {
    const stringKeys: Record<string, string> = {
      placeholder: "How can I assist you today?",
      createSkillPrompt:
        "We're going to build a new skill step by step with `skill-creator`. To start, what do you want this skill to do?",
      addAttachments: "Add attachments",
      mode: "Mode",
      flashMode: "Flash",
      flashModeDescription: "Fast and efficient, but may not be accurate",
      reasoningMode: "Reasoning",
      reasoningModeDescription:
        "Reasoning before action, balance between time and accuracy",
      proMode: "Pro",
      proModeDescription:
        "Reasoning, planning and executing, get more accurate results, may take more time",
      ultraMode: "Ultra",
      ultraModeDescription:
        "Pro mode with subagents to divide work; best for complex multi-step tasks",
      reasoningEffort: "Reasoning Effort",
      reasoningEffortMinimal: "Minimal",
      reasoningEffortMinimalDescription: "Retrieval + Direct Output",
      reasoningEffortLow: "Low",
      reasoningEffortLowDescription: "Simple Logic Check + Shallow Deduction",
      reasoningEffortMedium: "Medium",
      reasoningEffortMediumDescription:
        "Multi-layer Logic Analysis + Basic Verification",
      reasoningEffortHigh: "High",
      reasoningEffortHighDescription:
        "Full-dimensional Logic Deduction + Multi-path Verification + Backward Check",
      searchModels: "Search models...",
      surpriseMe: "Surprise",
      surpriseMePrompt: "Surprise me",
      followupLoading: "Generating follow-up questions...",
      followupConfirmTitle: "Send suggestion?",
      followupConfirmDescription:
        "You already have text in the input. Choose how to send it.",
      followupConfirmAppend: "Append & send",
      followupConfirmReplace: "Replace & send",
    };

    for (const [key, value] of Object.entries(stringKeys)) {
      it(`inputBox.${key}`, () => {
        expect(enUS.inputBox).toHaveProperty(key, value);
      });
    }

    describe("suggestions", () => {
      it("is an array with 4 items", () => {
        expect(enUS.inputBox.suggestions).toHaveLength(4);
      });

      it("each item has suggestion, prompt, and icon", () => {
        for (const item of enUS.inputBox.suggestions) {
          expect(item).toHaveProperty("suggestion");
          expect(item).toHaveProperty("prompt");
          expect(item).toHaveProperty("icon");
          expect(typeof item.suggestion).toBe("string");
          expect(typeof item.prompt).toBe("string");
        }
      });

      it("has correct suggestion labels", () => {
        const labels = enUS.inputBox.suggestions.map((s) => s.suggestion);
        expect(labels).toEqual(["Write", "Research", "Collect", "Learn"]);
      });

      it("each prompt is non-empty", () => {
        for (const item of enUS.inputBox.suggestions) {
          expect(item.prompt.trim().length).toBeGreaterThan(0);
        }
      });
    });

    describe("suggestionsCreate", () => {
      it("is an array with 5 items (including separator)", () => {
        expect(enUS.inputBox.suggestionsCreate).toHaveLength(5);
      });

      it("has a separator at index 3", () => {
        const sep = enUS.inputBox.suggestionsCreate[3];
        expect(sep).toEqual({ type: "separator" });
      });

      it("has correct suggestion labels", () => {
        const labels = enUS.inputBox.suggestionsCreate
          .filter((s) => !("type" in s))
          .map((s) => (s as { suggestion: string }).suggestion);
        expect(labels).toEqual(["Webpage", "Image", "Video", "Skill"]);
      });

      it("non-separator items have icon and prompt", () => {
        for (const item of enUS.inputBox.suggestionsCreate) {
          if (!("type" in item)) {
            expect(item).toHaveProperty("icon");
            expect(item).toHaveProperty("prompt");
            expect(typeof (item as { prompt: string }).prompt).toBe("string");
          }
        }
      });
    });
  });

  // =======================================================================
  // sidebar
  // =======================================================================
  describe("sidebar", () => {
    const expected: Record<string, string> = {
      newChat: "New chat",
      chats: "Chats",
      recentChats: "Recent chats",
      demoChats: "Demo chats",
      agents: "Agents",
      workflows: "Workflows",
    };

    for (const [key, value] of Object.entries(expected)) {
      it(`sidebar.${key}`, () => {
        expect(enUS.sidebar).toHaveProperty(key, value);
      });
    }

    it("has 9 keys", () => {
      expect(Object.keys(enUS.sidebar)).toHaveLength(9);
    });
  });

  // =======================================================================
  // agents
  // =======================================================================
  describe("agents", () => {
    const expected: Record<string, string> = {
      title: "Agents",
      description:
        "Create and manage your own agents with dedicated responsibilities and capabilities.",
      newAgent: "New Agent",
      emptyTitle: "No custom agents yet",
      emptyDescription:
        "Create your first custom agent with a specialized system prompt.",
      chat: "Chat",
      delete: "Delete",
      deleteConfirm:
        "Are you sure you want to delete this agent? This action cannot be undone.",
      deleteSuccess: "Agent deleted",
      template: "Template",
      newChat: "New chat",
      createPageTitle: "Design your Agent",
      createPageSubtitle:
        "Describe the agent you want — I'll help you create it through conversation.",
      nameStepTitle: "Name your new Agent",
      nameStepHint:
        "Letters, digits, and hyphens only — stored lowercase (e.g. code-reviewer)",
      nameStepPlaceholder: "e.g. code-reviewer",
      nameStepContinue: "Continue",
      nameStepInvalidError:
        "Invalid name — use only letters, digits, and hyphens",
      nameStepAlreadyExistsError: "An agent with this name already exists",
      nameStepNetworkError:
        "Network request failed — check your network or backend connection",
      nameStepCheckError:
        "Could not verify name availability — please try again",
      nameStepBootstrapMessage:
        "The new custom agent name is {name}. Help me design its purpose, behavior, and SOUL.md before saving it.",
      save: "Save agent",
      saving: "Saving agent...",
      saveRequested:
        "Save requested. iDeer is generating and saving an initial version now.",
      saveHint:
        "You can save this agent at any time from the top-right menu, even if this is only a first draft.",
      saveCommandMessage:
        "Please save this custom agent now based on everything we have discussed so far. Treat this as my explicit confirmation to save. If some details are still missing, make reasonable assumptions, generate a concise first SOUL.md in English, and call setup_agent immediately without asking me for more confirmation.",
      agentCreatedPendingRefresh:
        "The agent was created, but iDeer could not load it yet. Please refresh this page in a moment.",
      more: "More actions",
      agentCreated: "Agent created!",
      startChatting: "Start chatting",
      backToGallery: "Back to Gallery",
      visibility: "Visibility",
      visibilityPrivate: "Private",
      visibilityDepartment: "Department",
      visibilityPublic: "Public",
      visibilityAdminOnly:
        "Department and Public options are only available to admins",
      favoriteAdded: "Added to favorites",
      favoriteRemoved: "Removed from favorites",
      exportSuccess: "Agent exported",
      importSuccess: "Agent imported",
      applyVisibility: "Apply Visibility Change",
      applyVisibilityDescription:
        "Submit an application to change the visibility level of this agent",
      currentVisibility: "Current Visibility",
      targetVisibility: "Target Visibility",
      reason: "Reason",
      reasonPlaceholder: "Enter your reason...",
      visibilityReasonRequired: "Please provide a reason",
      submitting: "Submitting...",
      submit: "Submit Application",
      applicationSubmitted: "Application submitted",
      visibilityUpgradeHint:
        "Upgrading visibility requires admin approval and takes effect after review.",
      visibilityDowngradeHint:
        "Downgrading visibility takes effect immediately without approval.",
      visibilityUpdated: "Visibility updated",
      downgradeConfirmTitle: "Confirm visibility downgrade",
      downgradeConfirmDescription:
        "The downgrade takes effect immediately without approval. Continue?",
      confirm: "Confirm",
    };

    for (const [key, value] of Object.entries(expected)) {
      it(`agents.${key}`, () => {
        expect(enUS.agents).toHaveProperty(key, value);
      });
    }

    it("has the correct number of keys", () => {
      expect(Object.keys(enUS.agents)).toHaveLength(
        Object.keys(expected).length,
      );
    });

    it("nameStepBootstrapMessage contains {name} placeholder", () => {
      expect(enUS.agents.nameStepBootstrapMessage).toContain("{name}");
    });
  });

  // =======================================================================
  // workflows
  // =======================================================================
  describe("workflows", () => {
    describe("string properties", () => {
      const expected: Record<string, string> = {
        title: "Workflows",
        description: "Automate repeatable, step-by-step tasks with iDeer.",
        newWorkflow: "New Workflow",
        emptyTitle: "No workflows yet",
        emptyDescription:
          "Create your first workflow to automate a routine task",
        view: "View",
        deleteTitle: "Delete Workflow",
        deleteSuccess: "Workflow deleted",
        deleting: "Deleting...",
        unknown: "unknown",
        notFound: "Workflow not found",
        backToWorkflows: "Back to Workflows",
        edit: "Edit",
        run: "Run",
        stepsDescription: "Workflow execution steps",
        noSteps: "No steps defined",
        inputsTitle: "Inputs",
        inputsDescription: "Required and optional input parameters",
        required: "required",
        runStatus: "Run Status",
        runId: "Run ID: ",
        yamlDefinition: "YAML Definition",
        runDialog: "Run Workflow",
        runDialogDescription:
          "Provide input values for the workflow execution.",
        defaultPrefix: "Default: ",
        noInputs: "This workflow has no input parameters.",
        starting: "Starting...",
        createSubtitle: "Define a new workflow in YAML",
        yamlEditor: "YAML Editor",
        creating: "Creating...",
        saving: "Saving...",
        created: "Workflow created",
        updated: "Workflow updated",
        started: "Workflow started",
        saveChanges: "Save Changes",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`workflows.${key}`, () => {
          expect(enUS.workflows).toHaveProperty(key, value);
        });
      }
    });

    describe("function properties", () => {
      it("deleteConfirm interpolates name", () => {
        const result = enUS.workflows.deleteConfirm("test-workflow");
        expect(result).toContain("test-workflow");
      });

      it("steps returns singular for count 1", () => {
        expect(enUS.workflows.steps(1)).toBe("1 step");
      });

      it("steps returns plural for count > 1", () => {
        expect(enUS.workflows.steps(5)).toBe("5 steps");
      });

      it("steps handles zero", () => {
        expect(enUS.workflows.steps(0)).toBe("0 steps");
      });

      it("inputs returns singular for count 1", () => {
        expect(enUS.workflows.inputs(1)).toBe("1 input");
      });

      it("inputs returns plural for count > 1", () => {
        expect(enUS.workflows.inputs(3)).toBe("3 inputs");
      });

      it("stepsTitle returns formatted string with count", () => {
        expect(enUS.workflows.stepsTitle(4)).toBe("Steps (4)");
      });

      it("stepsTitle works with zero", () => {
        expect(enUS.workflows.stepsTitle(0)).toBe("Steps (0)");
      });

      it("enterInput interpolates key", () => {
        expect(enUS.workflows.enterInput("username")).toBe("Enter username...");
      });

      it("requiredMissing interpolates key", () => {
        const result = enUS.workflows.requiredMissing("apiKey");
        expect(result).toContain("apiKey");
        expect(result).toContain("Required input");
      });
    });
  });

  // =======================================================================
  // breadcrumb
  // =======================================================================
  describe("breadcrumb", () => {
    const expected: Record<string, string> = {
      workspace: "Workspace",
      chats: "Chats",
      workflows: "Workflows",
      edit: "Edit",
      runs: "Runs",
    };

    for (const [key, value] of Object.entries(expected)) {
      it(`breadcrumb.${key}`, () => {
        expect(enUS.breadcrumb).toHaveProperty(key, value);
      });
    }

    it("has 5 keys", () => {
      expect(Object.keys(enUS.breadcrumb)).toHaveLength(5);
    });
  });

  // =======================================================================
  // workspace
  // =======================================================================
  describe("workspace", () => {
    const expected: Record<string, string> = {
      officialWebsite: "Official Website",
      githubTooltip: "GitHub",
      settingsAndMore: "Settings & More",
      visitGithub: "Visit GitHub",
      reportIssue: "Report Issue",
      contactUs: "Contact Us",
      about: "About",
      logout: "Logout",
      adminPanel: "Admin Panel",
      userManagement: "User Management",
      departmentManagement: "Department Management",
      toolManagement: "Tool Management",
      resourceManagement: "Resource Management",
      applicationManagement: "Application Management",
      auditLogManagement: "Audit Log",
    };

    for (const [key, value] of Object.entries(expected)) {
      it(`workspace.${key}`, () => {
        expect(enUS.workspace).toHaveProperty(key, value);
      });
    }

    it("has 15 keys", () => {
      expect(Object.keys(enUS.workspace)).toHaveLength(15);
    });
  });

  // =======================================================================
  // conversation
  // =======================================================================
  describe("conversation", () => {
    it("conversation.noMessages", () => {
      expect(enUS.conversation.noMessages).toBe("No messages yet");
    });

    it("conversation.startConversation", () => {
      expect(enUS.conversation.startConversation).toBe(
        "Start a conversation to see messages here",
      );
    });

    it("has 2 keys", () => {
      expect(Object.keys(enUS.conversation)).toHaveLength(2);
    });
  });

  // =======================================================================
  // chats
  // =======================================================================
  describe("chats", () => {
    it("chats.searchChats", () => {
      expect(enUS.chats.searchChats).toBe("Search chats");
    });

    it("has 1 key", () => {
      expect(Object.keys(enUS.chats)).toHaveLength(1);
    });
  });

  // =======================================================================
  // pages
  // =======================================================================
  describe("pages", () => {
    const expected: Record<string, string> = {
      appName: "iDeer",
      chats: "Chats",
      newChat: "New chat",
      untitled: "Untitled",
    };

    for (const [key, value] of Object.entries(expected)) {
      it(`pages.${key}`, () => {
        expect(enUS.pages).toHaveProperty(key, value);
      });
    }

    it("has 4 keys", () => {
      expect(Object.keys(enUS.pages)).toHaveLength(4);
    });
  });

  // =======================================================================
  // toolCalls
  // =======================================================================
  describe("toolCalls", () => {
    const stringKeys: Record<string, string> = {
      lessSteps: "Less steps",
      executeCommand: "Execute command",
      presentFiles: "Present files",
      needYourHelp: "Need your help",
      searchForRelatedInfo: "Search for related information",
      searchForRelatedImages: "Search for related images",
      viewWebPage: "View web page",
      listFolder: "List folder",
      readFile: "Read file",
      writeFile: "Write file",
      clickToViewContent: "Click to view file content",
      writeTodos: "Update to-do list",
      skillInstallTooltip: "Install skill and make it available to iDeer",
    };

    for (const [key, value] of Object.entries(stringKeys)) {
      it(`toolCalls.${key}`, () => {
        expect(enUS.toolCalls).toHaveProperty(key, value);
      });
    }

    describe("function properties", () => {
      it("moreSteps interpolates count (singular)", () => {
        expect(enUS.toolCalls.moreSteps(1)).toBe("1 more step");
      });

      it("moreSteps interpolates count (plural)", () => {
        expect(enUS.toolCalls.moreSteps(5)).toBe("5 more steps");
      });

      it("useTool interpolates toolName", () => {
        expect(enUS.toolCalls.useTool("web_search")).toContain("web_search");
      });

      it("searchFor interpolates query", () => {
        expect(enUS.toolCalls.searchFor("AI news")).toContain("AI news");
      });

      it("searchForRelatedImagesFor interpolates query", () => {
        expect(enUS.toolCalls.searchForRelatedImagesFor("cats")).toContain(
          "cats",
        );
      });

      it("searchOnWebFor interpolates query", () => {
        expect(enUS.toolCalls.searchOnWebFor("news")).toContain("news");
      });
    });
  });

  // =======================================================================
  // uploads
  // =======================================================================
  describe("uploads", () => {
    it("uploads.uploading", () => {
      expect(enUS.uploads.uploading).toBe("Uploading...");
    });

    it("uploads.uploadingFiles", () => {
      expect(enUS.uploads.uploadingFiles).toBe(
        "Uploading files, please wait...",
      );
    });

    it("has 2 keys", () => {
      expect(Object.keys(enUS.uploads)).toHaveLength(2);
    });
  });

  // =======================================================================
  // subtasks
  // =======================================================================
  describe("subtasks", () => {
    it("subtasks.subtask", () => {
      expect(enUS.subtasks.subtask).toBe("Subtask");
    });

    it("subtasks.in_progress", () => {
      expect(enUS.subtasks.in_progress).toBe("Running subtask");
    });

    it("subtasks.completed", () => {
      expect(enUS.subtasks.completed).toBe("Subtask completed");
    });

    it("subtasks.failed", () => {
      expect(enUS.subtasks.failed).toBe("Subtask failed");
    });

    describe("executing function", () => {
      it("returns singular form for count 1", () => {
        expect(enUS.subtasks.executing(1)).toBe("Executing subtask");
      });

      it("returns parallel form for count > 1", () => {
        const result = enUS.subtasks.executing(3);
        expect(result).toContain("3");
        expect(result).toContain("subtasks");
        expect(result).toContain("parallel");
      });

      it("returns parallel form for count 2", () => {
        const result = enUS.subtasks.executing(2);
        expect(result).toContain("2");
        expect(result).toContain("subtasks in parallel");
      });

      it("handles count 0", () => {
        const result = enUS.subtasks.executing(0);
        expect(result).toContain("0");
        expect(result).toContain("subtasks");
      });
    });

    it("has 5 keys", () => {
      expect(Object.keys(enUS.subtasks)).toHaveLength(5);
    });
  });

  // =======================================================================
  // tokenUsage
  // =======================================================================
  describe("tokenUsage", () => {
    const stringKeys: Record<string, string> = {
      title: "Token Usage",
      label: "Tokens",
      input: "Input",
      output: "Output",
      total: "Total",
      view: "Display",
      finalAnswer: "Final answer",
      stepTotal: "Step total",
      sharedAttribution: "Shared across multiple actions in this step",
    };

    for (const [key, value] of Object.entries(stringKeys)) {
      it(`tokenUsage.${key}`, () => {
        expect(enUS.tokenUsage).toHaveProperty(key, value);
      });
    }

    it("tokenUsage.unavailable contains usage_metadata", () => {
      expect(enUS.tokenUsage.unavailable).toContain("No usage data yet");
    });

    it("tokenUsage.unavailableShort", () => {
      expect(enUS.tokenUsage.unavailableShort).toBe("No usage returned");
    });

    describe("presets", () => {
      const expected: Record<string, string> = {
        off: "Off",
        summary: "Summary",
        perTurn: "Per turn",
        debug: "Debug",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`tokenUsage.presets.${key}`, () => {
          expect(enUS.tokenUsage.presets).toHaveProperty(key, value);
        });
      }

      it("has 4 keys", () => {
        expect(Object.keys(enUS.tokenUsage.presets)).toHaveLength(4);
      });
    });

    describe("presetDescriptions", () => {
      const expected: Record<string, string> = {
        off: "Hide token usage in the header and conversation.",
        summary: "Show only the current conversation total in the header.",
        perTurn:
          "Show the header total and one token summary per assistant turn.",
        debug: "Show the header total and step-level token debugging details.",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`tokenUsage.presetDescriptions.${key}`, () => {
          expect(enUS.tokenUsage.presetDescriptions).toHaveProperty(key, value);
        });
      }

      it("has 4 keys", () => {
        expect(Object.keys(enUS.tokenUsage.presetDescriptions)).toHaveLength(4);
      });
    });

    describe("function properties", () => {
      it("subagent interpolates description", () => {
        expect(enUS.tokenUsage.subagent("planning")).toContain("planning");
      });

      it("startTodo interpolates content", () => {
        expect(enUS.tokenUsage.startTodo("task A")).toContain("task A");
      });

      it("completeTodo interpolates content", () => {
        expect(enUS.tokenUsage.completeTodo("task B")).toContain("task B");
      });

      it("updateTodo interpolates content", () => {
        expect(enUS.tokenUsage.updateTodo("task C")).toContain("task C");
      });

      it("removeTodo interpolates content", () => {
        expect(enUS.tokenUsage.removeTodo("task D")).toContain("task D");
      });
    });
  });

  // =======================================================================
  // shortcuts
  // =======================================================================
  describe("shortcuts", () => {
    const expected: Record<string, string> = {
      searchActions: "Search actions...",
      noResults: "No results found.",
      actions: "Actions",
      keyboardShortcuts: "Keyboard Shortcuts",
      keyboardShortcutsDescription:
        "Navigate iDeer faster with keyboard shortcuts.",
      openCommandPalette: "Open Command Palette",
      toggleSidebar: "Toggle Sidebar",
    };

    for (const [key, value] of Object.entries(expected)) {
      it(`shortcuts.${key}`, () => {
        expect(enUS.shortcuts).toHaveProperty(key, value);
      });
    }

    it("has 7 keys", () => {
      expect(Object.keys(enUS.shortcuts)).toHaveLength(7);
    });
  });

  // =======================================================================
  // settings
  // =======================================================================
  describe("settings", () => {
    it("settings.title", () => {
      expect(enUS.settings.title).toBe("Settings");
    });

    it("settings.description mentions iDeer", () => {
      expect(enUS.settings.description).toContain("iDeer");
    });

    // -------------------------------------------------------------------
    // settings.sections
    // -------------------------------------------------------------------
    describe("sections", () => {
      const expected: Record<string, string> = {
        account: "Account",
        appearance: "Appearance",
        memory: "Memory",
        tools: "Tools",
        skills: "Skills",
        notification: "Notification",
        about: "About",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`settings.sections.${key}`, () => {
          expect(enUS.settings.sections).toHaveProperty(key, value);
        });
      }

      it("has 7 keys", () => {
        expect(Object.keys(enUS.settings.sections)).toHaveLength(7);
      });
    });

    // -------------------------------------------------------------------
    // settings.memory
    // -------------------------------------------------------------------
    describe("memory", () => {
      const stringKeys: Record<string, string> = {
        title: "Memory",
        description:
          "iDeer automatically learns from your conversations in the background. These memories help iDeer understand you better and deliver a more personalized experience.",
        empty: "No memory data to display.",
        rawJson: "Raw JSON",
        exportButton: "Export memory",
        exportSuccess: "Memory exported",
        importButton: "Import memory",
        importConfirmTitle: "Import memory?",
        importConfirmDescription:
          "This will overwrite your current memory with the selected JSON backup.",
        importFileLabel: "Selected file",
        importInvalidFile:
          "Failed to read the selected memory file. Please choose a valid JSON export.",
        importSuccess: "Memory imported",
        manualFactSource: "Manual",
        addFact: "Add fact",
        addFactTitle: "Add memory fact",
        editFactTitle: "Edit memory fact",
        addFactSuccess: "Fact created",
        editFactSuccess: "Fact updated",
        clearAll: "Clear all memory",
        clearAllConfirmTitle: "Clear all memory?",
        clearAllConfirmDescription:
          "This will remove all saved summaries and facts. This action cannot be undone.",
        clearAllSuccess: "All memory cleared",
        factDeleteConfirmTitle: "Delete this fact?",
        factDeleteConfirmDescription:
          "This fact will be removed from memory immediately. This action cannot be undone.",
        factDeleteSuccess: "Fact deleted",
        factContentLabel: "Content",
        factCategoryLabel: "Category",
        factConfidenceLabel: "Confidence",
        factContentPlaceholder: "Describe the memory fact you want to save",
        factCategoryPlaceholder: "context",
        factConfidenceHint: "Use a number between 0 and 1.",
        factSave: "Save fact",
        factValidationContent: "Fact content cannot be empty.",
        factValidationConfidence:
          "Confidence must be a number between 0 and 1.",
        noFacts: "No saved facts yet.",
        summaryReadOnly:
          "Summary sections are read-only for now. You can currently add, edit, or delete individual facts, or clear all memory.",
        memoryFullyEmpty: "No memory saved yet.",
        factPreviewLabel: "Fact to delete",
        searchPlaceholder: "Search memory",
        filterAll: "All",
        filterFacts: "Facts",
        filterSummaries: "Summaries",
        noMatches: "No matching memory found.",
      };

      for (const [key, value] of Object.entries(stringKeys)) {
        it(`settings.memory.${key}`, () => {
          expect(enUS.settings.memory).toHaveProperty(key, value);
        });
      }

      describe("markdown", () => {
        const stringKeys: Record<string, string> = {
          overview: "Overview",
          userContext: "User context",
          work: "Work",
          personal: "Personal",
          topOfMind: "Top of mind",
          historyBackground: "History",
          recentMonths: "Recent months",
          earlierContext: "Earlier context",
          longTermBackground: "Long-term background",
          updatedAt: "Updated at",
          facts: "Facts",
          empty: "(empty)",
        };

        for (const [key, value] of Object.entries(stringKeys)) {
          it(`settings.memory.markdown.${key}`, () => {
            expect(enUS.settings.memory.markdown).toHaveProperty(key, value);
          });
        }

        describe("table", () => {
          const tableKeys: Record<string, string> = {
            category: "Category",
            confidence: "Confidence",
            content: "Content",
            source: "Source",
            createdAt: "CreatedAt",
            view: "View",
          };

          for (const [key, value] of Object.entries(tableKeys)) {
            it(`settings.memory.markdown.table.${key}`, () => {
              expect(enUS.settings.memory.markdown.table).toHaveProperty(
                key,
                value,
              );
            });
          }

          describe("confidenceLevel", () => {
            const expected: Record<string, string> = {
              veryHigh: "Very high",
              high: "High",
              normal: "Normal",
              unknown: "Unknown",
            };

            for (const [key, value] of Object.entries(expected)) {
              it(`settings.memory.markdown.table.confidenceLevel.${key}`, () => {
                expect(
                  enUS.settings.memory.markdown.table.confidenceLevel,
                ).toHaveProperty(key, value);
              });
            }

            it("has 4 keys", () => {
              expect(
                Object.keys(
                  enUS.settings.memory.markdown.table.confidenceLevel,
                ),
              ).toHaveLength(4);
            });
          });
        });
      });
    });

    // -------------------------------------------------------------------
    // settings.appearance
    // -------------------------------------------------------------------
    describe("appearance", () => {
      const expected: Record<string, string> = {
        themeTitle: "Theme",
        themeDescription:
          "Choose how the interface follows your device or stays fixed.",
        system: "System",
        light: "Light",
        dark: "Dark",
        systemDescription:
          "Match the operating system preference automatically.",
        lightDescription: "Bright palette with higher contrast for daytime.",
        darkDescription: "Dim palette that reduces glare for focus.",
        languageTitle: "Language",
        languageDescription: "Switch between languages.",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`settings.appearance.${key}`, () => {
          expect(enUS.settings.appearance).toHaveProperty(key, value);
        });
      }

      it("has 10 keys", () => {
        expect(Object.keys(enUS.settings.appearance)).toHaveLength(10);
      });
    });

    // -------------------------------------------------------------------
    // settings.tools
    // -------------------------------------------------------------------
    describe("tools", () => {
      it("settings.tools.description mentions MCP", () => {
        expect(enUS.settings.tools.description).toContain("MCP");
      });

      const expected: Record<string, string> = {
        title: "Tools",
        description:
          "Manage the configuration and enabled status of MCP tools.",
        addServer: "Add Server",
        editServer: "Edit Server",
        deleteConfirmTitle: "Delete server?",
        deleteConfirmDescription:
          "This server will be removed from the configuration. This action cannot be undone.",
        serverName: "Server Name",
        serverType: "Type",
        command: "Command",
        args: "Arguments",
        url: "URL",
        env: "Environment Variables",
        headers: "Headers",
        emptyState:
          'No MCP servers configured. Click "Add Server" to get started.',
        validationNameRequired: "Server name cannot be empty.",
        validationNameExists: "A server with this name already exists.",
        addSuccess: "Server added",
        editSuccess: "Server updated",
        deleteSuccess: "Server deleted",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`settings.tools.${key}`, () => {
          expect(enUS.settings.tools).toHaveProperty(key, value);
        });
      }

      it("has 19 keys", () => {
        expect(Object.keys(enUS.settings.tools)).toHaveLength(19);
      });
    });

    // -------------------------------------------------------------------
    // settings.skills
    // -------------------------------------------------------------------
    describe("skills", () => {
      const expected: Record<string, string> = {
        title: "Agent Skills",
        description:
          "Manage the configuration and enabled status of the agent skills.",
        createSkill: "Create skill",
        emptyTitle: "No agent skill yet",
        emptyDescription:
          "Put your agent skill folders under the `/resources/skills` folder under the root folder of iDeer.",
        emptyButton: "Create Your First Skill",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`settings.skills.${key}`, () => {
          expect(enUS.settings.skills).toHaveProperty(key, value);
        });
      }

      it("has 29 keys", () => {
        expect(Object.keys(enUS.settings.skills)).toHaveLength(29);
      });
    });

    // -------------------------------------------------------------------
    // settings.notification
    // -------------------------------------------------------------------
    describe("notification", () => {
      const expected: Record<string, string> = {
        title: "Notification",
        description:
          "iDeer only sends a completion notification when the window is not active. This is especially useful for long-running tasks so you can switch to other work and get notified when done.",
        requestPermission: "Request notification permission",
        deniedHint:
          "Notification permission was denied. You can enable it in your browser's site settings to receive completion alerts.",
        testButton: "Send test notification",
        testTitle: "iDeer",
        testBody: "This is a test notification.",
        notSupported: "Your browser does not support notifications.",
        disableNotification: "Disable notification",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`settings.notification.${key}`, () => {
          expect(enUS.settings.notification).toHaveProperty(key, value);
        });
      }

      it("has 9 keys", () => {
        expect(Object.keys(enUS.settings.notification)).toHaveLength(9);
      });
    });

    // -------------------------------------------------------------------
    // settings.account
    // -------------------------------------------------------------------
    describe("account", () => {
      const expected: Record<string, string> = {
        profileTitle: "Profile",
        email: "Email",
        role: "Role",
        changePasswordTitle: "Change Password",
        changePasswordDescription: "Update your account password.",
        currentPassword: "Current password",
        newPassword: "New password",
        confirmNewPassword: "Confirm new password",
        passwordMismatch: "New passwords do not match",
        passwordTooShort: "Password must be at least 8 characters",
        passwordChangedSuccess: "Password changed successfully",
        networkError: "Network error. Please try again.",
        updating: "Updating...",
        updatePassword: "Update Password",
        signOut: "Sign Out",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`settings.account.${key}`, () => {
          expect(enUS.settings.account).toHaveProperty(key, value);
        });
      }

      it("has 15 keys", () => {
        expect(Object.keys(enUS.settings.account)).toHaveLength(15);
      });
    });

    // -------------------------------------------------------------------
    // settings.acknowledge
    // -------------------------------------------------------------------
    describe("acknowledge", () => {
      it("settings.acknowledge.emptyTitle", () => {
        expect(enUS.settings.acknowledge.emptyTitle).toBe("Acknowledgements");
      });

      it("settings.acknowledge.emptyDescription", () => {
        expect(enUS.settings.acknowledge.emptyDescription).toBe(
          "Credits and acknowledgements will show here.",
        );
      });

      it("has 2 keys", () => {
        expect(Object.keys(enUS.settings.acknowledge)).toHaveLength(2);
      });
    });
  });

  // =======================================================================
  // Cross-cutting: every string leaf is non-empty
  // =======================================================================
  describe("all string leaves are non-empty", () => {
    const leaves = collectLeafPaths(enUS as unknown as Record<string, unknown>);

    for (const [path, value] of leaves) {
      if (typeof value === "string") {
        it(`${path} is a non-empty string`, () => {
          expect(value.trim().length).toBeGreaterThan(0);
        });
      }
    }
  });

  // =======================================================================
  // Cross-cutting: no Chinese characters in en-US strings (brand除外)
  // =======================================================================
  describe("brand consistency", () => {
    it("pages.appName uses iDeer", () => {
      expect(enUS.pages.appName).toBe("iDeer");
    });

    it("welcome.description mentions iDeer", () => {
      expect(enUS.welcome.description).toContain("iDeer");
    });

    it("settings.description mentions iDeer", () => {
      expect(enUS.settings.description).toContain("iDeer");
    });

    it("shortcuts.keyboardShortcutsDescription mentions iDeer", () => {
      expect(enUS.shortcuts.keyboardShortcutsDescription).toContain("iDeer");
    });

    it("workspace.about mentions iDeer", () => {
      expect(enUS.workspace.about).toBeDefined();
    });
  });

  // =======================================================================
  // Cross-cutting: key parity between en-US and Translations interface
  // =======================================================================
  describe("key completeness against Translations type", () => {
    it("common has all required keys", () => {
      const requiredKeys = [
        "home",
        "settings",
        "delete",
        "edit",
        "rename",
        "share",
        "openInNewWindow",
        "close",
        "more",
        "search",
        "loadMore",
        "download",
        "thinking",
        "artifacts",
        "public",
        "custom",
        "notAvailableInDemoMode",
        "loading",
        "version",
        "lastUpdated",
        "code",
        "preview",
        "cancel",
        "save",
        "install",
        "create",
        "import",
        "export",
        "exportAsMarkdown",
        "exportAsJSON",
        "exportSuccess",
      ];
      for (const key of requiredKeys) {
        expect(enUS.common).toHaveProperty(key);
      }
    });

    it("settings has all sub-sections", () => {
      expect(enUS.settings).toHaveProperty("sections");
      expect(enUS.settings).toHaveProperty("memory");
      expect(enUS.settings).toHaveProperty("appearance");
      expect(enUS.settings).toHaveProperty("tools");
      expect(enUS.settings).toHaveProperty("skills");
      expect(enUS.settings).toHaveProperty("notification");
      expect(enUS.settings).toHaveProperty("account");
      expect(enUS.settings).toHaveProperty("acknowledge");
    });
  });
});
