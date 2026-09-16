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
    renameFailed: string;
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
    exportFailed: string;
    regenerate: string;
    editAndRerun: string;
    updateAndRerun: string;
    editRerunWarning: string;
    branch: string;
    showArtifacts: string;
    browser: string;
    showBrowser: string;
    deleteTitle: string;
    deleteThreadConfirm: (title: string) => string;
    deleteFailed: string;
    showAll: string;
    favoritesOnly: string;
  };

  runDuration: {
    reasoning: string;
    working: string;
    completedIn: (duration: string) => string;
    description: string;
    lessThanSecond: string;
    hours: (value: number) => string;
    minutes: (value: number) => string;
    seconds: (value: number) => string;
    separator: string;
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

  // Clipboard
  clipboard: {
    copyToClipboard: string;
    copiedToClipboard: string;
    failedToCopyToClipboard: string;
    linkCopied: string;
  };

  artifactEditing: {
    unsaved: string;
    saving: string;
    saved: string;
    exit: string;
    discard: string;
    discardChanges: string;
    conflict: string;
    conflictShort: string;
    runInProgress: string;
    saveFailed: string;
  };

  artifactPreview: {
    limited: (previewSize: string, totalSize?: string) => string;
    loadFullFile: string;
    loadingFullFile: string;
    previewFailed: string;
    viewSource: string;
    missingTarget: string;
  };

  artifactArchive: {
    downloadCurrent: (count: number) => string;
    currentVersionNotice: string;
    downloadFailed: string;
  };

  // Citations
  citations: {
    sourcesSummary: (count: number) => string;
    citeCount: (count: number) => string;
    copyReference: (title: string) => string;
    copiedReference: (title: string) => string;
  };

  // Workspace Changes
  workspaceChanges: {
    title: string;
    editedTitle: (count: number) => string;
    badge: (count: number, additions: number, deletions: number) => string;
    viewChanges: string;
    created: string;
    modified: string;
    deleted: string;
    openFile: string;
    loading: string;
    noChanges: string;
    diffUnavailable: string;
    binaryUnavailable: string;
    largeUnavailable: string;
    sensitiveUnavailable: string;
    truncatedUnavailable: string;
    symlinkUnavailable: string;
    truncatedSummary: string;
  };

  // Input Box
  inputBox: {
    placeholder: string;
    disclaimer: string;
    createSkillPrompt: string;
    addAttachments: string;
    inputPolish: string;
    inputPolishing: string;
    inputPolishNoChanges: string;
    inputPolishFailed: string;
    inputPolishUndo: string;
    inputPolishCancel: string;
    voiceInputStartLabel: string;
    voiceInputStopLabel: string;
    voiceInputStart: string;
    voiceInputStop: string;
    voiceInputListening: string;
    voiceInputUnsupported: string;
    voiceInputPermissionDenied: string;
    voiceInputMicrophoneUnavailable: string;
    voiceInputUnsupportedLanguage: string;
    voiceInputNetworkError: string;
    voiceInputNoSpeech: string;
    voiceInputFailed: string;
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
    suggestionPlaceholderRequired: string;
    goalCommandDescription: string;
    compactCommandDescription: string;
    goalLabel: string;
    goalContinuing: string;
    goalContinuationTooltip: string;
    goalSet: string;
    goalCleared: string;
    goalNone: string;
    goalActive: string;
    goalFailed: string;
    goalTooLong: string;
    goalLengthCounter: string;
    compactSuccess: string;
    compactSkipped: string;
    compactFailed: string;
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
    pleaseWaitStreaming: string;
    selectModel: string;
    invokeSkill: string;
    skill: string;
    skillDialogDescription: string;
  };

  // Sidebar
  sidebar: {
    recentChats: string;
    newChat: string;
    chats: string;
    demoChats: string;
    agents: string;
    scheduledTasks: string;
    agentsDisabledTooltip: string;
    channels: string;
    capabilities: string;
    resources: string;
    automations: string;
    library: string;
    workflows: string;
  };

  // Thread-scoped MCP background tasks
  backgroundTasks: {
    label: string;
    title: string;
    description: string;
    active: string;
    recent: string;
    empty: string;
    emptyHint: string;
    loadFailed: string;
    retry: string;
    cancel: string;
    cancelling: string;
    cancelFailed: string;
    cancellationRetrying: (attempt: number) => string;
    notificationRetrying: (attempt: number) => string;
    notificationStopped: string;
    trackingDegraded: string;
    viewDetails: string;
    hideDetails: string;
    detailsFailed: string;
    result: string;
    resultArtifact: string;
    inputRequired: string;
    inputUnavailable: string;
    lastPollError: string;
    created: (time: string) => string;
    updated: (time: string) => string;
    status: {
      submitted: string;
      working: string;
      inputRequired: string;
      completed: string;
      failed: string;
      cancelled: string;
    };
  };

  subagentBatches: {
    label: string;
    title: string;
    description: string;
    workerUnavailable: string;
    empty: string;
    emptyHint: string;
    loadFailed: string;
    active: string;
    recent: string;
    pause: string;
    resume: string;
    cancel: string;
    retryItem: string;
    exportResults: string;
    viewItems: string;
    hideItems: string;
    itemsFailed: string;
    progress: (completed: number, total: number) => string;
    limits: (live: number, running: number) => string;
    status: {
      queued: string;
      running: string;
      paused: string;
      completed: string;
      failed: string;
      cancelled: string;
    };
  };

  // Scheduled tasks
  scheduledTasks: {
    scheduleType: { cron: string; once: string };
    preset: {
      label: string;
      hourly: string;
      daily: string;
      weekly: string;
      monthly: string;
      custom: string;
    };
    fields: {
      minute: string;
      time: string;
      weekday: string;
      dayOfMonth: string;
      cron: string;
      cronPlaceholder: string;
      runAt: string;
      timezone: string;
    };
    weekdays: {
      mon: string;
      tue: string;
      wed: string;
      thu: string;
      fri: string;
      sat: string;
      sun: string;
    };
    preview: string;
    cronHelp: string;
    create: {
      title: string;
      taskTitle: string;
      prompt: string;
      submit: string;
      fillRequired: string;
    };
    context: {
      fresh: string;
      reuse: string;
      threadIdPlaceholder: string;
      reuseNoticeTitle: string;
      reuseNoticeDescription: string;
    };
    filters: {
      allStatuses: string;
      enabled: string;
      paused: string;
      completed: string;
      failed: string;
      allTypes: string;
      cron: string;
      once: string;
    };
    detail: {
      contextMode: string;
      thread: string;
      lastThread: string;
      schedule: string;
      nextRun: string;
      lastRun: string;
      lastRunId: string;
      lastError: string;
      runsCount: string;
      runsCountOne: string;
      noRuns: string;
      noSelection: string;
      filteredByThread: string;
      loadFailed: string;
    };
    actions: {
      edit: string;
      cancelEdit: string;
      pause: string;
      resume: string;
      trigger: string;
      duplicate: string;
      duplicateTitleSuffix: string;
      delete: string;
    };
    deleteConfirm: string;
    errors: {
      create: string;
      update: string;
      pause: string;
      resume: string;
      trigger: string;
      delete: string;
    };
    edit: {
      titlePlaceholder: string;
      promptPlaceholder: string;
      submit: string;
    };
    status: {
      enabled: string;
      paused: string;
      running: string;
      completed: string;
      failed: string;
      cancelled: string;
    };
    runTrigger: { scheduled: string; manual: string };
    runStatus: {
      queued: string;
      launching: string;
      running: string;
      success: string;
      failed: string;
      skipped: string;
      interrupted: string;
    };
    recipes: {
      label: string;
      trending: { title: string; desc: string };
      news: { title: string; desc: string };
      issues: { title: string; desc: string };
      weekly: { title: string; desc: string };
    };
  };

  // Agents
  agents: {
    title: string;
    description: string;
    newAgent: string;
    emptyTitle: string;
    emptyDescription: string;
    featureDisabledTitle: string;
    featureDisabledDescription: string;
    chat: string;
    delete: string;
    deleteConfirm: string;
    deleteSuccess: string;
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
    nameStepCheckErrorWithDetail: string;
    nameStepApiDisabledError: string;
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
    backToGallery: string;
    settings: string;
    settingsTitle: string;
    settingsDescription: string;
    settingsModel: string;
    settingsModelDefault: string;
    settingsTemperature: string;
    settingsTemperatureHint: string;
    settingsMaxTokens: string;
    settingsMaxTokensPlaceholder: string;
    settingsThinking: string;
    settingsThinkingOn: string;
    settingsThinkingOff: string;
    settingsReasoningEffort: string;
    settingsInherit: string;
    settingsSaved: string;
    settingsInvalidTemperature: string;
    settingsInvalidMaxTokens: string;
    template: string;
    detailChat: string;
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
    gatewayUnavailable: string;
    gatewayUnavailableRetrying: string;
    modelLoadFailed: string;
    modelLoadRetry: string;
    modelLoadRetrying: string;
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
    branchCreated: string;
    branchFailed: string;
    streamReplayGap: string;
    outlineLabel: string;
    outlineAttachmentFallback: string;
  };

  // Chats
  chats: {
    searchChats: string;
    branchLabel: (title: string, parentTitle: string) => string;
    loadMoreToSearch: string;
    loadingMore: string;
    loadOlderChats: string;
    pinChat: string;
    unpinChat: string;
    pinChatFailed: string;
  };

  // Sidecar
  sidecar: {
    title: string;
    open: string;
    close: string;
    delete: string;
    deleteConfirm: string;
    deleteSuccess: string;
    deleteFailed: string;
    addToConversation: string;
    askInSideChat: string;
    reference: string;
    selectedTextFragment: string;
    selectedTextFragments: string;
    clearReferences: string;
    emptyTitle: string;
    emptyDescription: string;
    placeholder: string;
    send: string;
    sendFailed: string;
    noContext: string;
    continuing: string;
    selectionCrossesMessages: string;
  };

  // Channels
  channels: {
    title: string;
    connect: string;
    modify: string;
    reconnect: string;
    disconnect: string;
    connected: string;
    notConnected: string;
    pending: string;
    revoked: string;
    disabled: string;
    unconfigured: string;
    unavailable: string;
    unavailableShort: string;
    setupTitle: (name: string) => string;
    setupEditTitle: (name: string) => string;
    setupDescription: string;
    saveAndConnect: string;
    saveChanges: string;
    descriptions: Record<string, string>;
    connectedAs: (name: string) => string;
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
    browserNavigate: (url: string) => string;
    browserNavigateGeneric: string;
    browserClick: string;
    browserType: string;
    browserSnapshot: string;
    browserGetText: string;
    browserBack: string;
    browserScreenshot: string;
    browserClose: string;
  };

  humanInput: {
    answered: string;
    pending: string;
    readOnly: string;
    otherLabel: string;
    otherPlaceholder: string;
    submit: string;
    emptyError: string;
    requiredError: string;
    requiredA11yLabel: string;
    selectPlaceholder: string;
    answeredValue: (value: string) => string;
  };

  // Uploads
  uploads: {
    uploading: string;
    uploadingFiles: string;
    limitsHint: (
      maxFiles: number,
      maxFileSize: string,
      maxTotalSize: string,
    ) => string;
    filesTooLarge: (files: string, maxFileSize: string) => string;
    tooManyFiles: (count: number, maxFiles: number) => string;
    totalSizeTooLarge: (count: number, maxTotalSize: string) => string;
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
    collecting: string;
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

  contextUsage: {
    label: string;
    title: string;
    badgeAriaLabel: (percentage: string) => string;
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

  // Settings
  settings: {
    title: string;
    description: string;
    sections: {
      account: string;
      appearance: string;
      channels: string;
      integrations: string;
      memory: string;
      tools: string;
      subagents: string;
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
      adminRequired: string;
      empty: string;
      addServer: string;
      addServerDescription: string;
      addServerPlaceholder: string;
      serverDefinitionLabel: string;
      definitionEmpty: string;
      definitionInvalidJson: string;
      definitionRootNotObject: string;
      definitionNoServers: string;
      definitionServerNotObject: string;
      editServer: string;
      editServerDescription: string;
      editSingleServer: string;
      editServerNameMismatch: string;
      serverAlreadyExists: string;
      removeServer: string;
      removeServerDescription: string;
      unnamedServer: string;
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
    subagents: {
      title: string;
      description: string;
      executionNote: string;
      adminNote: string;
      create: string;
      empty: string;
      sourceBuiltin: string;
      sourceConfig: string;
      sourceManaged: string;
      conflict: string;
      overridden: string;
      createTitle: string;
      editTitle: string;
      name: string;
      nameHint: string;
      displayName: string;
      descriptionLabel: string;
      systemPrompt: string;
      model: string;
      inheritModel: string;
      tools: string;
      skills: string;
      listModeAll: string;
      listModeNone: string;
      listModeSelected: string;
      listNamesPlaceholder: string;
      maxTurns: string;
      timeout: string;
      created: string;
      saved: string;
      deleted: string;
      deleteConfirm: string;
      bindingTitle: string;
      bindingDescription: string;
      allAllowed: string;
      noneAllowed: string;
      selectedAllowed: string;
      missing: string;
    };
    channels: {
      title: string;
      description: string;
      disabled: string;
    };
    integrations: {
      title: string;
      description: string;
      refresh: string;
      install: string;
      reinstall: string;
      installing: string;
      ready: string;
      pending: string;
      available: string;
      unavailable: string;
      connected: string;
      loadFailed: string;
      adminRequired: string;
      lark: {
        title: string;
        description: string;
        skillPack: string;
        gatewayCli: string;
        auth: string;
        sandboxRuntime: string;
        sandboxRuntimeInitContainer: string;
        sandboxRuntimeBroker: string;
        sandboxRuntimeGatewayDownload: string;
        sandboxRuntimeNotReady: string;
        notInstalled: string;
        skillsInstalled: (installed: number, expected: number) => string;
        installedVersion: (version: string) => string;
        updateAvailable: (version: string) => string;
        runtimeVersionMismatch: string;
        authNotConfigured: string;
        authConfigured: string;
        authConfiguredFor: (user: string) => string;
        connect: string;
        authStarting: string;
        checkingConnection: string;
        connectedAction: string;
        requestPermissions: string;
        alreadyConnected: string;
        changeAppButton: string;
        changeAppTitle: string;
        changeAppDescription: string;
        changeAppIdLabel: string;
        changeAppSecretLabel: string;
        changeAppAuthResetNote: string;
        changeAppSubmit: string;
        changeAppReRegister: string;
        changeAppSwitched: string;
        brandFeishu: string;
        brandLark: string;
        connectionStarted: string;
        connectionReady: string;
        authStarted: string;
        authorizationStillPending: string;
        permissionTitle: string;
        permissionDescription: string;
        authDomains: Record<
          | "approval"
          | "apps"
          | "attendance"
          | "base"
          | "calendar"
          | "contact"
          | "docs"
          | "drive"
          | "event"
          | "im"
          | "mail"
          | "markdown"
          | "mindnotes"
          | "minutes"
          | "note"
          | "okr"
          | "sheets"
          | "slides"
          | "task"
          | "vc"
          | "wiki"
          | "all",
          { label: string; description: string }
        >;
        customScopeLabel: string;
        customScopePlaceholder: string;
        customScopeDescription: string;
        openConnectionLinkTitle: string;
        openConnectionLinkDescription: string;
        openAuthLinkTitle: string;
        openAuthLinkDescription: string;
        waitingAuthTitle: string;
        waitingAuthDescription: string;
        openAuthLink: string;
        copyAuthLink: string;
        completeAuth: string;
        continueAuth: string;
        preparingAuthorization: string;
        completingAuth: string;
        authExpiresIn: (seconds: number) => string;
        installingTitle: string;
        installingDescription: string;
        installNextTitle: string;
        installNextDescription: string;
        cliNextTitle: string;
        cliNextDescription: string;
        configuredTitle: string;
        configuredDescription: string;
        connectedTitle: string;
        connectedDescription: string;
        authNextTitle: string;
        authNextDescription: string;
      };
    };
    skills: {
      title: string;
      description: string;
      createSkill: string;
      emptyTitle: string;
      emptyDescription: string;
      emptyButton: string;
      adminRequired: string;
      installAdminRequired: string;
      installFromFile: string;
      installingArchive: string;
      invalidArchive: string;
      archiveTooLarge: string;
      installFailed: string;
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
      descriptionLabel: string;
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
      ssoProvider: string;
      ssoPasswordDescription: string;
      ssoPasswordMessage: string;
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

  // Login / Auth
  login: {
    signInTitle: string;
    createAccountTitle: string;
    email: string;
    emailPlaceholder: string;
    password: string;
    passwordPlaceholder: string;
    rememberMe: string;
    rememberMeDescription: string;
    pleaseWait: string;
    signIn: string;
    createAccount: string;
    createAdminAccount: string;
    adminSetupRequiredTitle: string;
    adminSetupRequiredDescription: string;
    orContinueWith: string;
    ssoHint: string;
    continueWith: (provider: string) => string;
    noAccountSignUp: string;
    haveAccountSignIn: string;
    backToHome: string;
    networkError: string;
    serviceUnavailableTitle: string;
    serviceUnavailableDescription: string;
    retry: string;
    authFailed: string;
    errors: {
      sso_failed: string;
      sso_cancelled: string;
      sso_account_exists: string;
      sso_not_allowed: string;
    };
  };

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
    knowledgeSnapshot: {
      title: string;
      entry: (kb: string, no: number | string, hash: string) => string;
    };
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
    addFiles: string;
    fileSelectionHint: string;
    selectedFiles: string;
    noSelectedFiles: string;
    fileCount: (count: number) => string;
    removeFile: (name: string) => string;
    singleSourceZip: string;
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
    revisions: string;
    evalCases: string;
    retrievalTestTab: string;
    revisionList: {
      selectKnowledgeBase: string;
      loading: string;
      loadFailed: string;
      empty: string;
      createCandidate: string;
      creating: string;
      createFailed: string;
      publishFailed: string;
      prepareFailed: string;
      viewDetails: string;
      hideDetails: string;
      documentsAndManifest: (count: number, hash: string) => string;
      publishingStatus: string;
      integrityFlagged: (status: string) => string;
      publish: string;
      publishingAction: string;
      publishAria: (no: number) => string;
      prepare: string;
      preparing: string;
      prepareAria: (no: number) => string;
    };
    evalCaseList: {
      selectKnowledgeBase: string;
      loading: string;
      loadFailed: string;
      empty: string;
      restricted: string;
      createTitle: string;
      questionLabel: string;
      questionPlaceholder: string;
      expectedDocsLabel: string;
      expectedDocsEmpty: string;
      tagsLabel: string;
      tagsPlaceholder: string;
      create: string;
      creating: string;
      createFailed: string;
      viewDetails: string;
      hideDetails: string;
      versionsTitle: string;
      versionAndHash: (no: number, hash: string) => string;
      expectedDocsCount: (count: number) => string;
      edit: string;
      cancel: string;
      save: string;
      saving: string;
      updateFailed: string;
      delete: string;
      deleting: string;
      deleteFailed: string;
      deleteConfirm: string;
      applicabilityTitle: string;
      applicabilityPlaceholder: string;
      revisionOption: (no: number, status: string) => string;
      applicabilityLoading: string;
      applicabilityLoadFailed: string;
      applicable: string;
      notApplicable: (count: number) => string;
    };
    retrievalTest: {
      selectKnowledgeBase: string;
      loading: string;
      revisionsLoadFailed: string;
      noPublishedRevision: string;
      revisionLabel: string;
      profileLabel: string;
      frozenProfile: string;
      configuredProfile: string;
      questionLabel: string;
      questionPlaceholder: string;
      topKLabel: string;
      run: string;
      running: string;
      runFailed: string;
      restricted: string;
      emptyResult: string;
      providerFailed: (code: string) => string;
      hitsTitle: (count: number) => string;
      manifest: (hash: string) => string;
      archivedTitle: string;
      archivedEmpty: string;
      archivedLoadFailed: string;
      viewRecord: string;
      recordLoadFailed: string;
      appliedParameters: string;
    };
    dependencySelector: {
      loadError: string;
      live: string;
      pinned: string;
      selectRevision: string;
      revisionsUnavailable: string;
      noPublishedRevisions: string;
      modeAria: (slug: string) => string;
      revisionAria: (slug: string) => string;
    };
  };

  // Settings
  landing: {
    heroTitlePrefix: string;
    heroWords: string[];
    heroTagline: string;
    heroCta: string;
  };

  admin: {
    knowledgeReconciliation: {
      title: string;
      description: string;
      run: string;
      running: string;
      loading: string;
      loadFailed: string;
      emptyHint: (kb: string) => string;
      noPublished: string;
      recorded: (n: number) => string;
      lastChecked: (at: string) => string;
      checkHistory: string;
      noChecks: string;
      unknown: string;
    };
    dashboard: {
      title: string;
      subtitle: string;
      totalUsers: string;
      totalDepartments: string;
      totalTools: string;
      pendingApplications: string;
      totalResources: string;
      auditLogs: string;
      knowledgeReconciliation: string;
      viewDetails: string;
      loading: string;
    };
    devices: {
      pageTitle: string;
      pageDescription: string;
      createPairing: string;
      pairingCode: string;
      pairingInstructions: string;
      confirmPairing: string;
      confirming: string;
      loading: string;
      empty: string;
      revoke: string;
      revokeConfirm: string;
      revoked: string;
      status: string;
      runtime: string;
      protocol: string;
      capabilities: string;
      lastSeen: string;
      never: string;
      pending: string;
      online: string;
      offline: string;
      blocked: string;
      outdated: string;
      error: string;
    };
    users: {
      pageTitle: string;
      subtitleSuperAdmin: string;
      subtitleDeptAdmin: string;
      filterDepartment: string;
      allDepartments: string;
      filterRole: string;
      allRoles: string;
      createUser: string;
      loading: string;
      noUsers: string;
      noDepartment: string;
      currentUserBadge: string;
      disabledBadge: string;
      createdAt: (date: string) => string;
      lastLogin: (date: string) => string;
      roleUser: string;
      roleDepartmentAdmin: string;
      roleSuperAdmin: string;
      editUser: string;
      deleteUser: string;
      disableFirst: string;
      enableUser: string;
      disableUser: string;
      cannotChangeOwnRole: string;
      cannotChangeOwnStatus: string;
      roleChangeConfirm: (
        username: string,
        fromRole: string,
        toRole: string,
      ) => string;
      roleUpdated: string;
      enableUserConfirm: string;
      disableUserConfirm: string;
      userEnabled: string;
      userDisabled: string;
      fillRequiredFields: string;
      passwordTooShort: string;
      userCreated: string;
      usernameRequired: string;
      userUpdated: string;
      userDeleted: string;
      createUserDesc: string;
      emailLabel: string;
      passwordLabel: string;
      usernameLabel: string;
      passwordPlaceholder: string;
      usernamePlaceholder: string;
      roleLabel: string;
      departmentLabel: string;
      departmentOptional: string;
      cancel: string;
      creating: string;
      create: string;
      editUserDesc: string;
      saving: string;
      save: string;
      deleteConfirm: (name: string) => string;
      resourceStrategy: string;
      softDelete: string;
      softDeleteDesc: string;
      hardDelete: string;
      hardDeleteDesc: string;
      transferResources: string;
      transferDesc: string;
      selectTargetUser: string;
      deleting: string;
      confirmDelete: string;
    };
    departments: {
      pageTitle: string;
      pageDescription: string;
      createDepartment: string;
      loading: string;
      noDepartments: string;
      noDescription: string;
      edit: string;
      delete: string;
      memberCount: (count: number | null) => string;
      agentCount: (count: number) => string;
      skillCount: (count: number) => string;
      createdAt: (date: string) => string;
      createDescription: string;
      nameLabel: string;
      enterDepartmentName: string;
      descriptionLabel: string;
      descriptionPlaceholder: string;
      cancel: string;
      creating: string;
      create: string;
      editDepartment: string;
      editDescription: string;
      saving: string;
      save: string;
      createdSuccess: string;
      updatedSuccess: string;
      deleteConfirm: string;
      deletedSuccess: string;
      reallocTitle: string;
      reallocDescription: (name: string, count: number) => string;
      loadingResources: string;
      affectedResources: string;
      visibilityDepartment: string;
      visibilityPrivate: string;
      noResources: string;
      reallocMethodLabel: string;
      reassignToDept: string;
      selectTargetDept: string;
      downgradeToPrivate: string;
      deleting: string;
      confirmDelete: string;
    };
    resources: {
      pageTitle: string;
      totalCount: (total: number) => string;
      allTypesLabel: string;
      agentLabel: string;
      toolLabel: string;
      workflowLabel: string;
      knowledgeBaseLabel: string;
      allVisibilityLabel: string;
      privateLabel: string;
      departmentLabel: string;
      publicLabel: string;
      allStatusLabel: string;
      activeLabel: string;
      archivedLabel: string;
      suspendedLabel: string;
      allOwnersLabel: string;
      typeLabel: string;
      nameLabel: string;
      visibilityLabel: string;
      statusLabel: string;
      ownerLabel: string;
      createdAtLabel: string;
      actionsLabel: string;
      suspendAction: string;
      restoreAction: string;
      archiveAction: string;
      prevPage: string;
      nextPage: string;
      loading: string;
      empty: string;
    };
    tools: {
      pageTitle: string;
      subtitle: string;
      requiresNetworkLabel: string;
      availableLabel: string;
      noDescription: string;
      testInputLabel: string;
      testingLabel: string;
      testButton: string;
      testResultLabel: string;
      closeButton: string;
      invalidJsonError: string;
      errorWithMessage: (message: string) => string;
      loading: string;
      empty: string;
    };
    auditLogs: {
      pageTitle: string;
      pageDescription: string;
      loading: string;
      none: string;
      operatorLabel: string;
      userIdPlaceholder: string;
      actionTypeLabel: string;
      all: string;
      startTimeLabel: string;
      endTimeLabel: string;
      reset: string;
      totalCount: (total: number) => string;
      emptyState: string;
      system: string;
      resourceLabel: string;
      previousPage: string;
      nextPage: string;
      detailTitle: string;
      logIdLabel: string;
      actionTimeLabel: string;
      ipAddressLabel: string;
      resourceIdLabel: string;
      resourceTypeLabel: string;
      detailContentLabel: string;
      actionCreate: string;
      actionUpdate: string;
      actionDelete: string;
      actionReview: string;
      actionApprove: string;
      actionReject: string;
      actionWithdraw: string;
      actionGrant: string;
      actionRevoke: string;
      actionApply: string;
      actionWithdrawal: string;
      resourceTypeTool: string;
      resourceTypeSkill: string;
      resourceTypeWorkflow: string;
      resourceTypeAgent: string;
    };
    visibilityApplications: {
      pageTitle: string;
      pageDescription: string;
      loading: string;
      operationFailed: string;
      closeError: string;
      statusPending: string;
      statusApproved: string;
      statusRejected: string;
      statusWithdrawn: string;
      resourceTypeTool: string;
      resourceTypeSkill: string;
      resourceTypeWorkflow: string;
      resourceTypeAgent: string;
      visibilityPrivate: string;
      visibilityDepartment: string;
      visibilityPublic: string;
      status: string;
      resourceType: string;
      targetVisibility: string;
      applicant: string;
      allStatuses: string;
      allTypes: string;
      allVisibilities: string;
      allApplicants: string;
      totalCount: (total: number) => string;
      emptyPending: string;
      emptyNotFound: string;
      applicationId: string;
      visibility: string;
      reason: string;
      none: string;
      submittedAt: string;
      reviewedAt: string;
      reviewComment: string;
      review: string;
      withdraw: string;
      previousPage: string;
      nextPage: string;
      reviewDialogTitle: string;
      resourceId: string;
      visibilityChange: string;
      reviewCommentPlaceholder: string;
      cancel: string;
      reject: string;
      approve: string;
      confirmWithdraw: string;
      withdrawConfirmDescription: string;
    };
    skillApplications: {
      redirecting: string;
    };
  };
}
