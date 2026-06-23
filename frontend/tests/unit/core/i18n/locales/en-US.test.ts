import { describe, expect, it } from "vitest";

import { enUS } from "@/core/i18n/locales/en-US";

describe("en-US translations", () => {
  describe("locale meta", () => {
    it("has locale.localName as English", () => {
      expect(enUS.locale.localName).toBe("English");
    });
  });

  describe("common section", () => {
    it("has all expected string keys", () => {
      const expectedKeys = [
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
      for (const key of expectedKeys) {
        expect(enUS.common).toHaveProperty(key);
        expect(typeof (enUS.common as Record<string, unknown>)[key]).toBe(
          "string",
        );
      }
    });
  });

  describe("home section", () => {
    it("has docs and blog", () => {
      expect(enUS.home.docs).toBe("Docs");
      expect(enUS.home.blog).toBe("Blog");
    });
  });

  describe("welcome section", () => {
    it("has greeting and description", () => {
      expect(typeof enUS.welcome.greeting).toBe("string");
      expect(typeof enUS.welcome.description).toBe("string");
      expect(enUS.welcome.description).toContain("iDeer");
    });

    it("has createYourOwnSkill fields", () => {
      expect(typeof enUS.welcome.createYourOwnSkill).toBe("string");
      expect(typeof enUS.welcome.createYourOwnSkillDescription).toBe("string");
    });
  });

  describe("clipboard section", () => {
    it("has all clipboard keys", () => {
      expect(enUS.clipboard.copyToClipboard).toBeTruthy();
      expect(enUS.clipboard.copiedToClipboard).toBeTruthy();
      expect(enUS.clipboard.failedToCopyToClipboard).toBeTruthy();
      expect(enUS.clipboard.linkCopied).toBeTruthy();
    });
  });

  describe("inputBox section", () => {
    it("has basic input box keys", () => {
      expect(enUS.inputBox.placeholder).toBeTruthy();
      expect(enUS.inputBox.createSkillPrompt).toBeTruthy();
      expect(enUS.inputBox.addAttachments).toBeTruthy();
    });

    it("has mode descriptions", () => {
      expect(enUS.inputBox.flashMode).toBeTruthy();
      expect(enUS.inputBox.flashModeDescription).toBeTruthy();
      expect(enUS.inputBox.reasoningMode).toBeTruthy();
      expect(enUS.inputBox.reasoningModeDescription).toBeTruthy();
      expect(enUS.inputBox.proMode).toBeTruthy();
      expect(enUS.inputBox.proModeDescription).toBeTruthy();
      expect(enUS.inputBox.ultraMode).toBeTruthy();
      expect(enUS.inputBox.ultraModeDescription).toBeTruthy();
    });

    it("has reasoning effort levels", () => {
      expect(enUS.inputBox.reasoningEffortMinimal).toBeTruthy();
      expect(enUS.inputBox.reasoningEffortMinimalDescription).toBeTruthy();
      expect(enUS.inputBox.reasoningEffortLow).toBeTruthy();
      expect(enUS.inputBox.reasoningEffortLowDescription).toBeTruthy();
      expect(enUS.inputBox.reasoningEffortMedium).toBeTruthy();
      expect(enUS.inputBox.reasoningEffortMediumDescription).toBeTruthy();
      expect(enUS.inputBox.reasoningEffortHigh).toBeTruthy();
      expect(enUS.inputBox.reasoningEffortHighDescription).toBeTruthy();
    });

    it("has followup keys", () => {
      expect(enUS.inputBox.followupLoading).toBeTruthy();
      expect(enUS.inputBox.followupConfirmTitle).toBeTruthy();
      expect(enUS.inputBox.followupConfirmDescription).toBeTruthy();
      expect(enUS.inputBox.followupConfirmAppend).toBeTruthy();
      expect(enUS.inputBox.followupConfirmReplace).toBeTruthy();
    });

    it("has suggestions array with correct structure", () => {
      expect(Array.isArray(enUS.inputBox.suggestions)).toBe(true);
      expect(enUS.inputBox.suggestions.length).toBeGreaterThanOrEqual(4);
      for (const item of enUS.inputBox.suggestions) {
        expect(item).toHaveProperty("suggestion");
        expect(item).toHaveProperty("prompt");
        expect(item).toHaveProperty("icon");
        expect(typeof item.suggestion).toBe("string");
        expect(typeof item.prompt).toBe("string");
      }
    });

    it("has suggestionsCreate array with separator", () => {
      expect(Array.isArray(enUS.inputBox.suggestionsCreate)).toBe(true);
      const separators = enUS.inputBox.suggestionsCreate.filter(
        (s) => "type" in s && s.type === "separator",
      );
      expect(separators.length).toBe(1);
      const nonSeparators = enUS.inputBox.suggestionsCreate.filter(
        (s) => !("type" in s),
      );
      expect(nonSeparators.length).toBeGreaterThanOrEqual(3);
    });
  });

  describe("sidebar section", () => {
    it("has all sidebar keys", () => {
      expect(enUS.sidebar.newChat).toBeTruthy();
      expect(enUS.sidebar.chats).toBeTruthy();
      expect(enUS.sidebar.recentChats).toBeTruthy();
      expect(enUS.sidebar.demoChats).toBeTruthy();
      expect(enUS.sidebar.agents).toBeTruthy();
      expect(enUS.sidebar.workflows).toBeTruthy();
    });
  });

  describe("agents section", () => {
    it("has all agent management keys", () => {
      expect(enUS.agents.title).toBeTruthy();
      expect(enUS.agents.description).toBeTruthy();
      expect(enUS.agents.newAgent).toBeTruthy();
      expect(enUS.agents.emptyTitle).toBeTruthy();
      expect(enUS.agents.emptyDescription).toBeTruthy();
      expect(enUS.agents.chat).toBeTruthy();
      expect(enUS.agents.delete).toBeTruthy();
      expect(enUS.agents.deleteConfirm).toBeTruthy();
      expect(enUS.agents.deleteSuccess).toBeTruthy();
      expect(enUS.agents.template).toBeTruthy();
      expect(enUS.agents.newChat).toBeTruthy();
    });

    it("has agent creation page keys", () => {
      expect(enUS.agents.createPageTitle).toBeTruthy();
      expect(enUS.agents.createPageSubtitle).toBeTruthy();
    });

    it("has name step keys", () => {
      expect(enUS.agents.nameStepTitle).toBeTruthy();
      expect(enUS.agents.nameStepHint).toBeTruthy();
      expect(enUS.agents.nameStepPlaceholder).toBeTruthy();
      expect(enUS.agents.nameStepContinue).toBeTruthy();
      expect(enUS.agents.nameStepInvalidError).toBeTruthy();
      expect(enUS.agents.nameStepAlreadyExistsError).toBeTruthy();
      expect(enUS.agents.nameStepNetworkError).toBeTruthy();
      expect(enUS.agents.nameStepCheckError).toBeTruthy();
      expect(enUS.agents.nameStepApiDisabledError).toBeTruthy();
    });

    it("has nameStepBootstrapMessage with placeholder", () => {
      expect(enUS.agents.nameStepBootstrapMessage).toContain("{name}");
    });

    it("has save-related keys", () => {
      expect(enUS.agents.save).toBeTruthy();
      expect(enUS.agents.saving).toBeTruthy();
      expect(enUS.agents.saveRequested).toBeTruthy();
      expect(enUS.agents.saveHint).toBeTruthy();
      expect(enUS.agents.saveCommandMessage).toBeTruthy();
      expect(enUS.agents.agentCreatedPendingRefresh).toBeTruthy();
      expect(enUS.agents.more).toBeTruthy();
      expect(enUS.agents.agentCreated).toBeTruthy();
      expect(enUS.agents.startChatting).toBeTruthy();
      expect(enUS.agents.backToGallery).toBeTruthy();
    });
  });

  describe("workflows section", () => {
    it("has gallery keys", () => {
      expect(enUS.workflows.title).toBeTruthy();
      expect(enUS.workflows.description).toBeTruthy();
      expect(enUS.workflows.newWorkflow).toBeTruthy();
      expect(enUS.workflows.emptyTitle).toBeTruthy();
      expect(enUS.workflows.emptyDescription).toBeTruthy();
    });

    it("has card keys", () => {
      expect(enUS.workflows.view).toBeTruthy();
      expect(enUS.workflows.deleteTitle).toBeTruthy();
      expect(enUS.workflows.deleteSuccess).toBeTruthy();
      expect(enUS.workflows.deleting).toBeTruthy();
      expect(enUS.workflows.unknown).toBeTruthy();
    });

    it("has deleteConfirm as function", () => {
      expect(typeof enUS.workflows.deleteConfirm).toBe("function");
      const result = enUS.workflows.deleteConfirm("test-workflow");
      expect(result).toContain("test-workflow");
    });

    it("has steps function for plural/singular", () => {
      expect(typeof enUS.workflows.steps).toBe("function");
      expect(enUS.workflows.steps(1)).toBe("1 step");
      expect(enUS.workflows.steps(5)).toBe("5 steps");
    });

    it("has inputs function for plural/singular", () => {
      expect(typeof enUS.workflows.inputs).toBe("function");
      expect(enUS.workflows.inputs(1)).toBe("1 input");
      expect(enUS.workflows.inputs(3)).toBe("3 inputs");
    });

    it("has detail keys", () => {
      expect(enUS.workflows.notFound).toBeTruthy();
      expect(enUS.workflows.backToWorkflows).toBeTruthy();
      expect(enUS.workflows.edit).toBeTruthy();
      expect(enUS.workflows.run).toBeTruthy();
      expect(enUS.workflows.stepsDescription).toBeTruthy();
      expect(enUS.workflows.noSteps).toBeTruthy();
      expect(enUS.workflows.inputsTitle).toBeTruthy();
      expect(enUS.workflows.inputsDescription).toBeTruthy();
      expect(enUS.workflows.required).toBeTruthy();
      expect(enUS.workflows.runStatus).toBeTruthy();
      expect(enUS.workflows.runId).toBeTruthy();
      expect(enUS.workflows.yamlDefinition).toBeTruthy();
    });

    it("has stepsTitle function", () => {
      expect(typeof enUS.workflows.stepsTitle).toBe("function");
      expect(enUS.workflows.stepsTitle(3)).toBe("Steps (3)");
    });

    it("has run dialog keys", () => {
      expect(enUS.workflows.runDialog).toBeTruthy();
      expect(enUS.workflows.runDialogDescription).toBeTruthy();
      expect(enUS.workflows.defaultPrefix).toBeTruthy();
      expect(enUS.workflows.noInputs).toBeTruthy();
      expect(enUS.workflows.starting).toBeTruthy();
    });

    it("has enterInput function", () => {
      expect(typeof enUS.workflows.enterInput).toBe("function");
      expect(enUS.workflows.enterInput("prompt")).toBe("Enter prompt...");
    });

    it("has create/edit keys", () => {
      expect(enUS.workflows.createSubtitle).toBeTruthy();
      expect(enUS.workflows.yamlEditor).toBeTruthy();
      expect(enUS.workflows.creating).toBeTruthy();
      expect(enUS.workflows.saving).toBeTruthy();
      expect(enUS.workflows.created).toBeTruthy();
      expect(enUS.workflows.updated).toBeTruthy();
      expect(enUS.workflows.started).toBeTruthy();
      expect(enUS.workflows.saveChanges).toBeTruthy();
    });

    it("has requiredMissing function", () => {
      expect(typeof enUS.workflows.requiredMissing).toBe("function");
      const result = enUS.workflows.requiredMissing("input_name");
      expect(result).toContain("input_name");
    });
  });

  describe("breadcrumb section", () => {
    it("has all breadcrumb keys", () => {
      expect(enUS.breadcrumb.workspace).toBeTruthy();
      expect(enUS.breadcrumb.chats).toBeTruthy();
      expect(enUS.breadcrumb.workflows).toBeTruthy();
      expect(enUS.breadcrumb.edit).toBeTruthy();
      expect(enUS.breadcrumb.runs).toBeTruthy();
    });
  });

  describe("workspace section", () => {
    it("has all workspace keys", () => {
      expect(enUS.workspace.officialWebsite).toBeTruthy();
      expect(enUS.workspace.githubTooltip).toBeTruthy();
      expect(enUS.workspace.settingsAndMore).toBeTruthy();
      expect(enUS.workspace.visitGithub).toBeTruthy();
      expect(enUS.workspace.reportIssue).toBeTruthy();
      expect(enUS.workspace.contactUs).toBeTruthy();
      expect(enUS.workspace.about).toBeTruthy();
      expect(enUS.workspace.logout).toBeTruthy();
      expect(enUS.workspace.adminPanel).toBeTruthy();
      expect(enUS.workspace.userManagement).toBeTruthy();
      expect(enUS.workspace.departmentManagement).toBeTruthy();
      expect(enUS.workspace.toolManagement).toBeTruthy();
    });
  });

  describe("conversation section", () => {
    it("has conversation keys", () => {
      expect(enUS.conversation.noMessages).toBeTruthy();
      expect(enUS.conversation.startConversation).toBeTruthy();
    });
  });

  describe("chats section", () => {
    it("has searchChats", () => {
      expect(enUS.chats.searchChats).toBeTruthy();
    });
  });

  describe("pages section", () => {
    it("has page title keys", () => {
      expect(enUS.pages.appName).toBe("iDeer");
      expect(enUS.pages.chats).toBeTruthy();
      expect(enUS.pages.newChat).toBeTruthy();
      expect(enUS.pages.untitled).toBeTruthy();
    });
  });

  describe("toolCalls section", () => {
    it("has all tool call string keys", () => {
      expect(enUS.toolCalls.lessSteps).toBeTruthy();
      expect(enUS.toolCalls.executeCommand).toBeTruthy();
      expect(enUS.toolCalls.presentFiles).toBeTruthy();
      expect(enUS.toolCalls.needYourHelp).toBeTruthy();
      expect(enUS.toolCalls.searchForRelatedInfo).toBeTruthy();
      expect(enUS.toolCalls.searchForRelatedImages).toBeTruthy();
      expect(enUS.toolCalls.viewWebPage).toBeTruthy();
      expect(enUS.toolCalls.listFolder).toBeTruthy();
      expect(enUS.toolCalls.readFile).toBeTruthy();
      expect(enUS.toolCalls.writeFile).toBeTruthy();
      expect(enUS.toolCalls.clickToViewContent).toBeTruthy();
      expect(enUS.toolCalls.writeTodos).toBeTruthy();
      expect(enUS.toolCalls.skillInstallTooltip).toBeTruthy();
    });

    it("has moreSteps function", () => {
      expect(typeof enUS.toolCalls.moreSteps).toBe("function");
      expect(enUS.toolCalls.moreSteps(1)).toBe("1 more step");
      expect(enUS.toolCalls.moreSteps(5)).toBe("5 more steps");
    });

    it("has useTool function", () => {
      expect(typeof enUS.toolCalls.useTool).toBe("function");
      expect(enUS.toolCalls.useTool("web_search")).toContain("web_search");
    });

    it("has searchFor function", () => {
      expect(typeof enUS.toolCalls.searchFor).toBe("function");
      expect(enUS.toolCalls.searchFor("query")).toContain("query");
    });

    it("has searchForRelatedImagesFor function", () => {
      expect(typeof enUS.toolCalls.searchForRelatedImagesFor).toBe("function");
      expect(enUS.toolCalls.searchForRelatedImagesFor("cats")).toContain(
        "cats",
      );
    });

    it("has searchOnWebFor function", () => {
      expect(typeof enUS.toolCalls.searchOnWebFor).toBe("function");
      expect(enUS.toolCalls.searchOnWebFor("news")).toContain("news");
    });
  });

  describe("uploads section", () => {
    it("has upload keys", () => {
      expect(enUS.uploads.uploading).toBeTruthy();
      expect(enUS.uploads.uploadingFiles).toBeTruthy();
    });
  });

  describe("subtasks section", () => {
    it("has subtask keys", () => {
      expect(enUS.subtasks.subtask).toBeTruthy();
      expect(enUS.subtasks.in_progress).toBeTruthy();
      expect(enUS.subtasks.completed).toBeTruthy();
      expect(enUS.subtasks.failed).toBeTruthy();
    });

    it("has executing function for singular", () => {
      expect(typeof enUS.subtasks.executing).toBe("function");
      expect(enUS.subtasks.executing(1)).toBe("Executing subtask");
    });

    it("has executing function for plural", () => {
      const result = enUS.subtasks.executing(3);
      expect(result).toContain("3");
      expect(result).toContain("subtasks");
      expect(result).toContain("parallel");
    });
  });

  describe("tokenUsage section", () => {
    it("has basic token usage keys", () => {
      expect(enUS.tokenUsage.title).toBeTruthy();
      expect(enUS.tokenUsage.label).toBeTruthy();
      expect(enUS.tokenUsage.input).toBeTruthy();
      expect(enUS.tokenUsage.output).toBeTruthy();
      expect(enUS.tokenUsage.total).toBeTruthy();
      expect(enUS.tokenUsage.view).toBeTruthy();
      expect(enUS.tokenUsage.unavailable).toBeTruthy();
      expect(enUS.tokenUsage.unavailableShort).toBeTruthy();
      expect(enUS.tokenUsage.note).toBeTruthy();
      expect(enUS.tokenUsage.finalAnswer).toBeTruthy();
      expect(enUS.tokenUsage.stepTotal).toBeTruthy();
      expect(enUS.tokenUsage.sharedAttribution).toBeTruthy();
    });

    it("has presets", () => {
      expect(enUS.tokenUsage.presets.off).toBeTruthy();
      expect(enUS.tokenUsage.presets.summary).toBeTruthy();
      expect(enUS.tokenUsage.presets.perTurn).toBeTruthy();
      expect(enUS.tokenUsage.presets.debug).toBeTruthy();
    });

    it("has presetDescriptions", () => {
      expect(enUS.tokenUsage.presetDescriptions.off).toBeTruthy();
      expect(enUS.tokenUsage.presetDescriptions.summary).toBeTruthy();
      expect(enUS.tokenUsage.presetDescriptions.perTurn).toBeTruthy();
      expect(enUS.tokenUsage.presetDescriptions.debug).toBeTruthy();
    });

    it("has subagent function", () => {
      expect(typeof enUS.tokenUsage.subagent).toBe("function");
      expect(enUS.tokenUsage.subagent("planning")).toContain("planning");
    });

    it("has todo functions", () => {
      expect(typeof enUS.tokenUsage.startTodo).toBe("function");
      expect(typeof enUS.tokenUsage.completeTodo).toBe("function");
      expect(typeof enUS.tokenUsage.updateTodo).toBe("function");
      expect(typeof enUS.tokenUsage.removeTodo).toBe("function");

      expect(enUS.tokenUsage.startTodo("task A")).toContain("task A");
      expect(enUS.tokenUsage.completeTodo("task B")).toContain("task B");
      expect(enUS.tokenUsage.updateTodo("task C")).toContain("task C");
      expect(enUS.tokenUsage.removeTodo("task D")).toContain("task D");
    });
  });

  describe("shortcuts section", () => {
    it("has all shortcut keys", () => {
      expect(enUS.shortcuts.searchActions).toBeTruthy();
      expect(enUS.shortcuts.noResults).toBeTruthy();
      expect(enUS.shortcuts.actions).toBeTruthy();
      expect(enUS.shortcuts.keyboardShortcuts).toBeTruthy();
      expect(enUS.shortcuts.keyboardShortcutsDescription).toBeTruthy();
      expect(enUS.shortcuts.openCommandPalette).toBeTruthy();
      expect(enUS.shortcuts.toggleSidebar).toBeTruthy();
    });
  });

  describe("settings section", () => {
    it("has top-level settings keys", () => {
      expect(enUS.settings.title).toBeTruthy();
      expect(enUS.settings.description).toBeTruthy();
    });

    it("has section keys", () => {
      expect(enUS.settings.sections.account).toBeTruthy();
      expect(enUS.settings.sections.appearance).toBeTruthy();
      expect(enUS.settings.sections.memory).toBeTruthy();
      expect(enUS.settings.sections.tools).toBeTruthy();
      expect(enUS.settings.sections.skills).toBeTruthy();
      expect(enUS.settings.sections.notification).toBeTruthy();
      expect(enUS.settings.sections.about).toBeTruthy();
    });

    it("has memory settings", () => {
      expect(enUS.settings.memory.title).toBeTruthy();
      expect(enUS.settings.memory.description).toBeTruthy();
      expect(enUS.settings.memory.empty).toBeTruthy();
      expect(enUS.settings.memory.rawJson).toBeTruthy();
      expect(enUS.settings.memory.exportButton).toBeTruthy();
      expect(enUS.settings.memory.exportSuccess).toBeTruthy();
      expect(enUS.settings.memory.importButton).toBeTruthy();
      expect(enUS.settings.memory.importConfirmTitle).toBeTruthy();
      expect(enUS.settings.memory.importConfirmDescription).toBeTruthy();
      expect(enUS.settings.memory.importFileLabel).toBeTruthy();
      expect(enUS.settings.memory.importInvalidFile).toBeTruthy();
      expect(enUS.settings.memory.importSuccess).toBeTruthy();
    });

    it("has memory fact management keys", () => {
      expect(enUS.settings.memory.manualFactSource).toBeTruthy();
      expect(enUS.settings.memory.addFact).toBeTruthy();
      expect(enUS.settings.memory.addFactTitle).toBeTruthy();
      expect(enUS.settings.memory.editFactTitle).toBeTruthy();
      expect(enUS.settings.memory.addFactSuccess).toBeTruthy();
      expect(enUS.settings.memory.editFactSuccess).toBeTruthy();
      expect(enUS.settings.memory.factSave).toBeTruthy();
      expect(enUS.settings.memory.factValidationContent).toBeTruthy();
      expect(enUS.settings.memory.factValidationConfidence).toBeTruthy();
      expect(enUS.settings.memory.noFacts).toBeTruthy();
    });

    it("has memory clear and delete keys", () => {
      expect(enUS.settings.memory.clearAll).toBeTruthy();
      expect(enUS.settings.memory.clearAllConfirmTitle).toBeTruthy();
      expect(enUS.settings.memory.clearAllConfirmDescription).toBeTruthy();
      expect(enUS.settings.memory.clearAllSuccess).toBeTruthy();
      expect(enUS.settings.memory.factDeleteConfirmTitle).toBeTruthy();
      expect(enUS.settings.memory.factDeleteConfirmDescription).toBeTruthy();
      expect(enUS.settings.memory.factDeleteSuccess).toBeTruthy();
    });

    it("has memory fact form label keys", () => {
      expect(enUS.settings.memory.factContentLabel).toBeTruthy();
      expect(enUS.settings.memory.factCategoryLabel).toBeTruthy();
      expect(enUS.settings.memory.factConfidenceLabel).toBeTruthy();
      expect(enUS.settings.memory.factContentPlaceholder).toBeTruthy();
      expect(enUS.settings.memory.factCategoryPlaceholder).toBeTruthy();
      expect(enUS.settings.memory.factConfidenceHint).toBeTruthy();
    });

    it("has memory filter and search keys", () => {
      expect(enUS.settings.memory.summaryReadOnly).toBeTruthy();
      expect(enUS.settings.memory.memoryFullyEmpty).toBeTruthy();
      expect(enUS.settings.memory.factPreviewLabel).toBeTruthy();
      expect(enUS.settings.memory.searchPlaceholder).toBeTruthy();
      expect(enUS.settings.memory.filterAll).toBeTruthy();
      expect(enUS.settings.memory.filterFacts).toBeTruthy();
      expect(enUS.settings.memory.filterSummaries).toBeTruthy();
      expect(enUS.settings.memory.noMatches).toBeTruthy();
    });

    it("has memory markdown keys", () => {
      expect(enUS.settings.memory.markdown.overview).toBeTruthy();
      expect(enUS.settings.memory.markdown.userContext).toBeTruthy();
      expect(enUS.settings.memory.markdown.work).toBeTruthy();
      expect(enUS.settings.memory.markdown.personal).toBeTruthy();
      expect(enUS.settings.memory.markdown.topOfMind).toBeTruthy();
      expect(enUS.settings.memory.markdown.historyBackground).toBeTruthy();
      expect(enUS.settings.memory.markdown.recentMonths).toBeTruthy();
      expect(enUS.settings.memory.markdown.earlierContext).toBeTruthy();
      expect(enUS.settings.memory.markdown.longTermBackground).toBeTruthy();
      expect(enUS.settings.memory.markdown.updatedAt).toBeTruthy();
      expect(enUS.settings.memory.markdown.facts).toBeTruthy();
      expect(enUS.settings.memory.markdown.empty).toBeTruthy();
    });

    it("has memory markdown table keys", () => {
      expect(enUS.settings.memory.markdown.table.category).toBeTruthy();
      expect(enUS.settings.memory.markdown.table.confidence).toBeTruthy();
      expect(enUS.settings.memory.markdown.table.content).toBeTruthy();
      expect(enUS.settings.memory.markdown.table.source).toBeTruthy();
      expect(enUS.settings.memory.markdown.table.createdAt).toBeTruthy();
      expect(enUS.settings.memory.markdown.table.view).toBeTruthy();
    });

    it("has memory markdown table confidenceLevel keys", () => {
      expect(
        enUS.settings.memory.markdown.table.confidenceLevel.veryHigh,
      ).toBeTruthy();
      expect(
        enUS.settings.memory.markdown.table.confidenceLevel.high,
      ).toBeTruthy();
      expect(
        enUS.settings.memory.markdown.table.confidenceLevel.normal,
      ).toBeTruthy();
      expect(
        enUS.settings.memory.markdown.table.confidenceLevel.unknown,
      ).toBeTruthy();
    });

    it("has appearance settings", () => {
      expect(enUS.settings.appearance.themeTitle).toBeTruthy();
      expect(enUS.settings.appearance.themeDescription).toBeTruthy();
      expect(enUS.settings.appearance.system).toBeTruthy();
      expect(enUS.settings.appearance.light).toBeTruthy();
      expect(enUS.settings.appearance.dark).toBeTruthy();
      expect(enUS.settings.appearance.systemDescription).toBeTruthy();
      expect(enUS.settings.appearance.lightDescription).toBeTruthy();
      expect(enUS.settings.appearance.darkDescription).toBeTruthy();
      expect(enUS.settings.appearance.languageTitle).toBeTruthy();
      expect(enUS.settings.appearance.languageDescription).toBeTruthy();
    });

    it("has tools settings", () => {
      expect(enUS.settings.tools.title).toBeTruthy();
      expect(enUS.settings.tools.description).toBeTruthy();
    });

    it("has skills settings", () => {
      expect(enUS.settings.skills.title).toBeTruthy();
      expect(enUS.settings.skills.description).toBeTruthy();
      expect(enUS.settings.skills.createSkill).toBeTruthy();
      expect(enUS.settings.skills.emptyTitle).toBeTruthy();
      expect(enUS.settings.skills.emptyDescription).toBeTruthy();
      expect(enUS.settings.skills.emptyButton).toBeTruthy();
    });

    it("has notification settings", () => {
      expect(enUS.settings.notification.title).toBeTruthy();
      expect(enUS.settings.notification.description).toBeTruthy();
      expect(enUS.settings.notification.requestPermission).toBeTruthy();
      expect(enUS.settings.notification.deniedHint).toBeTruthy();
      expect(enUS.settings.notification.testButton).toBeTruthy();
      expect(enUS.settings.notification.testTitle).toBeTruthy();
      expect(enUS.settings.notification.testBody).toBeTruthy();
      expect(enUS.settings.notification.notSupported).toBeTruthy();
      expect(enUS.settings.notification.disableNotification).toBeTruthy();
    });

    it("has account settings", () => {
      expect(enUS.settings.account.profileTitle).toBeTruthy();
      expect(enUS.settings.account.email).toBeTruthy();
      expect(enUS.settings.account.role).toBeTruthy();
      expect(enUS.settings.account.changePasswordTitle).toBeTruthy();
      expect(enUS.settings.account.changePasswordDescription).toBeTruthy();
      expect(enUS.settings.account.currentPassword).toBeTruthy();
      expect(enUS.settings.account.newPassword).toBeTruthy();
      expect(enUS.settings.account.confirmNewPassword).toBeTruthy();
      expect(enUS.settings.account.passwordMismatch).toBeTruthy();
      expect(enUS.settings.account.passwordTooShort).toBeTruthy();
      expect(enUS.settings.account.passwordChangedSuccess).toBeTruthy();
      expect(enUS.settings.account.networkError).toBeTruthy();
      expect(enUS.settings.account.updating).toBeTruthy();
      expect(enUS.settings.account.updatePassword).toBeTruthy();
      expect(enUS.settings.account.signOut).toBeTruthy();
    });

    it("has acknowledge settings", () => {
      expect(enUS.settings.acknowledge.emptyTitle).toBeTruthy();
      expect(enUS.settings.acknowledge.emptyDescription).toBeTruthy();
    });
  });

  describe("all sections are non-empty", () => {
    it("every top-level section has at least one key", () => {
      const sections = [
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
      for (const section of sections) {
        expect(
          Object.keys(
            (enUS as unknown as Record<string, unknown>)[section] as object,
          ).length,
        ).toBeGreaterThan(0);
      }
    });
  });
});
