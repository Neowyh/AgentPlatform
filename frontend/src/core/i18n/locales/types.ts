import type { LucideIcon } from "lucide-react";

export interface Translations {
  // Locale meta
  locale: {
    localName: string;
  };

  // Common
  common: {
    home: string;
    settings: string;
    delete: string;
    edit: string;
    rename: string;
    share: string;
    openInNewWindow: string;
    close: string;
    more: string;
    search: string;
    loadMore: string;
    download: string;
    thinking: string;
    artifacts: string;
    public: string;
    custom: string;
    notAvailableInDemoMode: string;
    loading: string;
    version: string;
    lastUpdated: string;
    code: string;
    preview: string;
    cancel: string;
    save: string;
    install: string;
    create: string;
    import: string;
    export: string;
    exportAsMarkdown: string;
    exportAsJSON: string;
    exportSuccess: string;
    showAll: string;
    favoritesOnly: string;
  };

  home: {
    docs: string;
    blog: string;
  };

  // Welcome
  welcome: {
    greeting: string;
    description: string;
    createYourOwnSkill: string;
    createYourOwnSkillDescription: string;
  };

  // Workbench home (welcome state)
  workbench: {
    recentChatsTitle: string;
  };

  // Scenario cascade bar
  scenarios: {
    daily: string;
    creative: string;
    professional: string;
    // Pills
    pills: Record<string, string>;
    // Chips
    chips: Record<string, string>;
  };

  // Clipboard
  clipboard: {
    copyToClipboard: string;
    copiedToClipboard: string;
    failedToCopyToClipboard: string;
    linkCopied: string;
  };

  // Input Box
  inputBox: {
    placeholder: string;
    createSkillPrompt: string;
    addAttachments: string;
    selectModel: string;
    invokeSkill: string;
    skill: string;
    skillDialogDescription: string;
    mode: string;
    flashMode: string;
    flashModeDescription: string;
    reasoningMode: string;
    reasoningModeDescription: string;
    proMode: string;
    proModeDescription: string;
    ultraMode: string;
    ultraModeDescription: string;
    reasoningEffort: string;
    reasoningEffortMinimal: string;
    reasoningEffortMinimalDescription: string;
    reasoningEffortLow: string;
    reasoningEffortLowDescription: string;
    reasoningEffortMedium: string;
    reasoningEffortMediumDescription: string;
    reasoningEffortHigh: string;
    reasoningEffortHighDescription: string;
    searchModels: string;
    surpriseMe: string;
    surpriseMePrompt: string;
    followupLoading: string;
    followupConfirmTitle: string;
    followupConfirmDescription: string;
    followupConfirmAppend: string;
    followupConfirmReplace: string;
    suggestions: {
      suggestion: string;
      prompt: string;
      icon: LucideIcon;
    }[];
    suggestionsCreate: (
      | {
          suggestion: string;
          prompt: string;
          icon: LucideIcon;
        }
      | {
          type: "separator";
        }
    )[];
  };

  // Sidebar
  sidebar: {
    recentChats: string;
    newChat: string;
    chats: string;
    capabilities: string;
    demoChats: string;
    agents: string;
    resources: string;
    automations: string;
    library: string;
    workflows: string;
  };

  // Agents
  agents: {
    title: string;
    description: string;
    newAgent: string;
    emptyTitle: string;
    emptyDescription: string;
    chat: string;
    delete: string;
    deleteConfirm: string;
    deleteSuccess: string;
    template: string;
    newChat: string;
    createPageTitle: string;
    createPageSubtitle: string;
    nameStepTitle: string;
    nameStepHint: string;
    nameStepPlaceholder: string;
    nameStepContinue: string;
    nameStepInvalidError: string;
    nameStepAlreadyExistsError: string;
    nameStepNetworkError: string;
    nameStepCheckError: string;
    nameStepBootstrapMessage: string;
    save: string;
    saving: string;
    saveRequested: string;
    saveHint: string;
    saveCommandMessage: string;
    agentCreatedPendingRefresh: string;
    more: string;
    agentCreated: string;
    startChatting: string;
    detailChat: string;
    backToGallery: string;
    visibility: string;
    visibilityPrivate: string;
    visibilityDepartment: string;
    visibilityPublic: string;
    visibilityAdminOnly: string;
    applyVisibility: string;
    changeVisibility: string;
    applyVisibilityDescription: string;
    currentVisibility: string;
    targetVisibility: string;
    reason: string;
    reasonPlaceholder: string;
    visibilityReasonRequired: string;
    submitting: string;
    submit: string;
    applicationSubmitted: string;
    visibilityUpgradeHint: string;
    visibilityDowngradeHint: string;
    visibilityUpdated: string;
    downgradeConfirmTitle: string;
    downgradeConfirmDescription: string;
    confirm: string;
    favoriteAdded: string;
    favoriteRemoved: string;
    exportSuccess: string;
    importSuccess: string;
    edit: string;
    export: string;
    notFound: string;
    configuration: string;
    model: string;
    defaultModel: string;
    toolGroups: string;
    skills: string;
    usage: string;
    command: string;
    source: string;
    notSpecified: string;
    exportFailed: string;
  };

  // Auth
  auth: {
    signInTitle: string;
    createAccountTitle: string;
    email: string;
    password: string;
    signIn: string;
    createAccount: string;
    pleaseWait: string;
    noAccount: string;
    hasAccount: string;
    backToHome: string;
    errorAccountDisabled: string;
    errorTooManyAttempts: string;
    errorInvalidCredentials: string;
    errorNetwork: string;
  };

  // Workflows
  workflows: {
    // Gallery
    title: string;
    description: string;
    newWorkflow: string;
    emptyTitle: string;
    emptyDescription: string;
    // Card
    view: string;
    deleteTitle: string;
    deleteConfirm: (name: string) => string;
    deleteSuccess: string;
    deleting: string;
    unknown: string;
    steps: (count: number) => string;
    inputs: (count: number) => string;
    // Detail
    notFound: string;
    backToWorkflows: string;
    edit: string;
    run: string;
    stepsTitle: (count: number) => string;
    stepsDescription: string;
    noSteps: string;
    inputsTitle: string;
    inputsDescription: string;
    required: string;
    runStatus: string;
    runId: string;
    runHistory: string;
    noRuns: string;
    definitionVersion: string;
    resume: string;
    cancelRun: string;
    commandSubmitted: string;
    streamFallback: string;
    eventTimeline: string;
    selectNodeHint: string;
    nodeDetailTitle: string;
    nodeNotStarted: string;
    duration: string;
    tokenStream: string;
    definitionMismatchHint: string;
    artifacts: string;
    noArtifacts: string;
    artifactLoadError: string;
    artifactSize: string;
    actionOutput: string;
    runNotFound: string;
    yamlDefinition: string;
    // Run Dialog
    runDialog: string;
    runDialogDescription: string;
    model: string;
    modelPlaceholder: string;
    defaultPrefix: string;
    enterInput: (key: string) => string;
    noInputs: string;
    modelLabel: string;
    followSystemModel: string;
    starting: string;
    // Create/Edit
    createSubtitle: string;
    yamlEditor: string;
    creating: string;
    saving: string;
    created: string;
    updated: string;
    requiredMissing: (key: string) => string;
    started: string;
    saveChanges: string;
    // Visibility
    visibility: string;
    export: string;
    exportSuccess: string;
    exportFailed: string;
    applyVisibility: string;
    applyVisibilityDescription: string;
    currentTargetVisibility: string;
    targetVisibility: string;
    private: string;
    department: string;
    public: string;
    reason: string;
    reasonPlaceholder: string;
    reasonRequired: string;
    submitting: string;
    submit: string;
    applicationSubmitted: string;
    visibilityUpgradeHint: string;
    visibilityDowngradeHint: string;
    visibilityUpdated: string;
    downgradeConfirmTitle: string;
    downgradeConfirmDescription: string;
    confirm: string;
    notOwner: string;
    visibilityPrivate: string;
    visibilityDepartment: string;
    visibilityPublic: string;
    favoriteAdded: string;
    favoriteRemoved: string;
  };

  // Breadcrumb
  breadcrumb: {
    workspace: string;
    chats: string;
    workflows: string;
    edit: string;
    runs: string;
  };

  // Workspace
  workspace: {
    officialWebsite: string;
    githubTooltip: string;
    settingsAndMore: string;
    visitGithub: string;
    reportIssue: string;
    contactUs: string;
    about: string;
    logout: string;
    adminPanel: string;
    userManagement: string;
    departmentManagement: string;
    toolManagement: string;
    resourceManagement: string;
    applicationManagement: string;
    auditLogManagement: string;
  };

  // Conversation
  conversation: {
    noMessages: string;
    startConversation: string;
  };

  // Chats
  chats: {
    searchChats: string;
  };

  // Page titles (document title)
  pages: {
    appName: string;
    chats: string;
    newChat: string;
    untitled: string;
  };

  // Tool calls
  toolCalls: {
    moreSteps: (count: number) => string;
    lessSteps: string;
    executeCommand: string;
    presentFiles: string;
    needYourHelp: string;
    useTool: (toolName: string) => string;
    searchForRelatedInfo: string;
    searchForRelatedImages: string;
    searchFor: (query: string) => string;
    searchForRelatedImagesFor: (query: string) => string;
    searchOnWebFor: (query: string) => string;
    viewWebPage: string;
    listFolder: string;
    readFile: string;
    writeFile: string;
    clickToViewContent: string;
    writeTodos: string;
    skillInstallTooltip: string;
  };

  // Uploads
  uploads: {
    uploading: string;
    uploadingFiles: string;
  };

  // Subtasks
  subtasks: {
    subtask: string;
    executing: (count: number) => string;
    in_progress: string;
    completed: string;
    failed: string;
  };

  // Token Usage
  tokenUsage: {
    title: string;
    label: string;
    input: string;
    output: string;
    total: string;
    view: string;
    unavailable: string;
    unavailableShort: string;
    note: string;
    presets: {
      off: string;
      summary: string;
      perTurn: string;
      debug: string;
    };
    presetDescriptions: {
      off: string;
      summary: string;
      perTurn: string;
      debug: string;
    };
    finalAnswer: string;
    stepTotal: string;
    sharedAttribution: string;
    subagent: (description: string) => string;
    startTodo: (content: string) => string;
    completeTodo: (content: string) => string;
    updateTodo: (content: string) => string;
    removeTodo: (content: string) => string;
  };

  // Shortcuts
  shortcuts: {
    searchActions: string;
    noResults: string;
    actions: string;
    keyboardShortcuts: string;
    keyboardShortcutsDescription: string;
    openCommandPalette: string;
    toggleSidebar: string;
  };

  // Resources
  resources: {
    title: string;
    description: string;
    experts: string;
    skills: string;
    connectors: string;
    impactTitle: string;
    impactSummary: (
      total: number,
      direct: number,
      transitive: number,
    ) => string;
    impactBlockedSummary: (count: number) => string;
    impactCascadeLabel: string;
    impactLoadError: string;
    resourceTypeAgent: string;
    resourceTypeSkill: string;
    resourceTypeWorkflow: string;
    resourceTypeTool: string;
    visibilityPrivate: string;
    visibilityDepartment: string;
    visibilityPublic: string;
    notificationsTitle: string;
    notificationsEmpty: string;
    notificationsMarkAllRead: string;
    notificationsMarkAllReadDone: string;
    notificationsVisibilityReduced: (name: string) => string;
    notificationsVisibilityReducedCascade: (name: string) => string;
    notificationsAdminVisibilityReduced: (count: number) => string;
    notificationsUnknownEvent: string;
    notificationsLoadFailed: string;
  };

  // Automations
  automations: {
    title: string;
    description: string;
    create: string;
    templates: string;
    myAutomations: string;
  };

  // Library
  library: {
    title: string;
    description: string;
    upload: string;
    search: string;
    documents: string;
    knowledgeBases: string;
  };

  // Settings
  settings: {
    title: string;
    description: string;
    sections: {
      account: string;
      appearance: string;
      memory: string;
      tools: string;
      skills: string;
      notification: string;
      about: string;
    };
    memory: {
      title: string;
      description: string;
      empty: string;
      rawJson: string;
      exportButton: string;
      exportSuccess: string;
      importButton: string;
      importConfirmTitle: string;
      importConfirmDescription: string;
      importFileLabel: string;
      importInvalidFile: string;
      importSuccess: string;
      manualFactSource: string;
      addFact: string;
      addFactTitle: string;
      editFactTitle: string;
      addFactSuccess: string;
      editFactSuccess: string;
      clearAll: string;
      clearAllConfirmTitle: string;
      clearAllConfirmDescription: string;
      clearAllSuccess: string;
      factDeleteConfirmTitle: string;
      factDeleteConfirmDescription: string;
      factDeleteSuccess: string;
      factContentLabel: string;
      factCategoryLabel: string;
      factConfidenceLabel: string;
      factContentPlaceholder: string;
      factCategoryPlaceholder: string;
      factConfidenceHint: string;
      factSave: string;
      factValidationContent: string;
      factValidationConfidence: string;
      noFacts: string;
      summaryReadOnly: string;
      memoryFullyEmpty: string;
      factPreviewLabel: string;
      searchPlaceholder: string;
      filterAll: string;
      filterFacts: string;
      filterSummaries: string;
      noMatches: string;
      markdown: {
        overview: string;
        userContext: string;
        work: string;
        personal: string;
        topOfMind: string;
        historyBackground: string;
        recentMonths: string;
        earlierContext: string;
        longTermBackground: string;
        updatedAt: string;
        facts: string;
        empty: string;
        table: {
          category: string;
          confidence: string;
          confidenceLevel: {
            veryHigh: string;
            high: string;
            normal: string;
            unknown: string;
          };
          content: string;
          source: string;
          createdAt: string;
          view: string;
        };
      };
    };
    appearance: {
      themeTitle: string;
      themeDescription: string;
      system: string;
      light: string;
      dark: string;
      systemDescription: string;
      lightDescription: string;
      darkDescription: string;
      languageTitle: string;
      languageDescription: string;
    };
    tools: {
      title: string;
      description: string;
      addServer: string;
      editServer: string;
      deleteConfirmTitle: string;
      deleteConfirmDescription: string;
      serverName: string;
      serverType: string;
      command: string;
      args: string;
      url: string;
      env: string;
      headers: string;
      emptyState: string;
      validationNameRequired: string;
      validationNameExists: string;
      addSuccess: string;
      editSuccess: string;
      deleteSuccess: string;
    };
    skills: {
      title: string;
      description: string;
      createSkill: string;
      emptyTitle: string;
      emptyDescription: string;
      emptyButton: string;
      applyVisibility: string;
      applyVisibilityDescription: string;
      locked: string;
      lockedTooltip: string;
      applicationSubmitted: string;
      applicationSubmitFailed: string;
      applyDialogTitle: string;
      applyDialogDescription: string;
      applyDialogCurrentVisibility: string;
      applyDialogTargetVisibility: string;
      applyDialogVisibilityPrivate: string;
      applyDialogVisibilityDepartment: string;
      applyDialogVisibilityPublic: string;
      applyDialogReason: string;
      applyDialogReasonPlaceholder: string;
      applyDialogCancel: string;
      applyDialogSubmit: string;
      applyDialogUpgradeHint: string;
      applyDialogDowngradeHint: string;
      visibilityUpdated: string;
      applyDialogDowngradeConfirmTitle: string;
      applyDialogDowngradeConfirmDescription: string;
      applyDialogConfirm: string;
      details: string;
      use: string;
      searchPlaceholder: string;
      importSuccess: string;
      archiveSuccess: string;
      noResults: string;
      backToSkills: string;
      notFound: string;
      edit: string;
      export: string;
      information: string;
      license: string;
      allowedTools: string;
      internet: string;
      required: string;
      notRequired: string;
      version: string;
      skillMd: string;
      notSpecified: string;
      noDescription: string;
      readOnly: string;
      saved: string;
      saveFailed: string;
      exportFailed: string;
      category: string;
      command: string;
      usage: string;
      input: string;
      output: string;
      inputDescription: string;
      outputDescription: string;
    };
    notification: {
      title: string;
      description: string;
      requestPermission: string;
      deniedHint: string;
      testButton: string;
      testTitle: string;
      testBody: string;
      notSupported: string;
      disableNotification: string;
    };
    account: {
      profileTitle: string;
      email: string;
      role: string;
      changePasswordTitle: string;
      changePasswordDescription: string;
      currentPassword: string;
      newPassword: string;
      confirmNewPassword: string;
      passwordMismatch: string;
      passwordTooShort: string;
      passwordChangedSuccess: string;
      networkError: string;
      updating: string;
      updatePassword: string;
      signOut: string;
    };
    acknowledge: {
      emptyTitle: string;
      emptyDescription: string;
    };
  };
}
