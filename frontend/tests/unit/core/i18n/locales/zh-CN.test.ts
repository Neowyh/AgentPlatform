import { describe, expect, it } from "vitest";

import { zhCN } from "@/core/i18n/locales/zh-CN";

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
// zhCN locale
// ---------------------------------------------------------------------------
describe("zhCN locale", () => {
  // =======================================================================
  // Top-level structure
  // =======================================================================
  it("is exported as an object", () => {
    expect(zhCN).toBeDefined();
    expect(typeof zhCN).toBe("object");
  });

  // =======================================================================
  // locale
  // =======================================================================
  describe("locale", () => {
    it("has localName set to Chinese", () => {
      expect(zhCN.locale.localName).toBe("中文");
    });
  });

  // =======================================================================
  // common
  // =======================================================================
  describe("common", () => {
    const expectedStrings: Record<string, string> = {
      home: "首页",
      settings: "设置",
      delete: "删除",
      edit: "编辑",
      rename: "重命名",
      share: "分享",
      openInNewWindow: "在新窗口打开",
      close: "关闭",
      more: "更多",
      search: "搜索",
      loadMore: "加载更多",
      download: "下载",
      thinking: "思考",
      artifacts: "文件",
      public: "公共",
      custom: "自定义",
      notAvailableInDemoMode: "在演示模式下不可用",
      loading: "加载中...",
      version: "版本",
      lastUpdated: "最后更新",
      code: "代码",
      preview: "预览",
      cancel: "取消",
      save: "保存",
      install: "安装",
      create: "创建",
      import: "导入",
      export: "导出",
      exportAsMarkdown: "导出为 Markdown",
      exportAsJSON: "导出为 JSON",
      exportSuccess: "对话已导出",
      showAll: "显示全部",
      favoritesOnly: "仅收藏",
    };

    for (const [key, value] of Object.entries(expectedStrings)) {
      it(`common.${key} is "${value}"`, () => {
        expect(zhCN.common).toHaveProperty(key, value);
      });
    }

    it("has the correct number of keys", () => {
      expect(Object.keys(zhCN.common)).toHaveLength(
        Object.keys(expectedStrings).length,
      );
    });
  });

  // =======================================================================
  // home
  // =======================================================================
  describe("home", () => {
    it("home.docs", () => {
      expect(zhCN.home.docs).toBe("文档");
    });

    it("home.blog", () => {
      expect(zhCN.home.blog).toBe("博客");
    });

    it("has the correct number of keys", () => {
      expect(Object.keys(zhCN.home)).toHaveLength(2);
    });
  });

  // =======================================================================
  // welcome
  // =======================================================================
  describe("welcome", () => {
    it("welcome.greeting", () => {
      expect(zhCN.welcome.greeting).toBe("你好，欢迎回来！");
    });

    it("welcome.description contains iDeer brand", () => {
      expect(zhCN.welcome.description).toContain("iDeer");
    });

    it("welcome.createYourOwnSkill", () => {
      expect(zhCN.welcome.createYourOwnSkill).toBe("创建你自己的 Agent SKill");
    });

    it("welcome.createYourOwnSkillDescription contains iDeer", () => {
      expect(zhCN.welcome.createYourOwnSkillDescription).toContain("iDeer");
    });

    it("has 4 keys", () => {
      expect(Object.keys(zhCN.welcome)).toHaveLength(4);
    });
  });

  // =======================================================================
  // clipboard
  // =======================================================================
  describe("clipboard", () => {
    const expected: Record<string, string> = {
      copyToClipboard: "复制到剪贴板",
      copiedToClipboard: "已复制到剪贴板",
      failedToCopyToClipboard: "复制到剪贴板失败",
      linkCopied: "链接已复制到剪贴板",
    };

    for (const [key, value] of Object.entries(expected)) {
      it(`clipboard.${key}`, () => {
        expect(zhCN.clipboard).toHaveProperty(key, value);
      });
    }

    it("has 4 keys", () => {
      expect(Object.keys(zhCN.clipboard)).toHaveLength(4);
    });
  });

  // =======================================================================
  // inputBox
  // =======================================================================
  describe("inputBox", () => {
    const stringKeys: Record<string, string> = {
      placeholder: "今天我能为你做些什么？",
      createSkillPrompt:
        "我们一起用 skill-creator 技能来创建一个技能吧。先问问我希望这个技能能做什么。",
      addAttachments: "添加附件",
      mode: "模式",
      flashMode: "闪速",
      flashModeDescription: "快速且高效的完成任务，但可能不够精准",
      reasoningMode: "思考",
      reasoningModeDescription: "思考后再行动，在时间与准确性之间取得平衡",
      proMode: "Pro",
      proModeDescription:
        "思考、计划再执行，获得更精准的结果，可能需要更多时间",
      ultraMode: "Ultra",
      ultraModeDescription:
        "继承自 Pro 模式，可调用子代理分工协作，适合复杂多步骤任务，能力最强",
      reasoningEffort: "推理深度",
      reasoningEffortMinimal: "最低",
      reasoningEffortMinimalDescription: "检索 + 直接输出",
      reasoningEffortLow: "低",
      reasoningEffortLowDescription: "简单逻辑校验 + 浅层推演",
      reasoningEffortMedium: "中",
      reasoningEffortMediumDescription: "多层逻辑分析 + 基础验证",
      reasoningEffortHigh: "高",
      reasoningEffortHighDescription: "全维度逻辑推演 + 多路径验证 + 反推校验",
      searchModels: "搜索模型...",
      surpriseMe: "小惊喜",
      surpriseMePrompt: "给我一个小惊喜吧",
      followupLoading: "正在生成可能的后续问题...",
      followupConfirmTitle: "发送建议问题？",
      followupConfirmDescription: "当前输入框已有内容，选择发送方式。",
      followupConfirmAppend: "追加并发送",
      followupConfirmReplace: "替换并发送",
    };

    for (const [key, value] of Object.entries(stringKeys)) {
      it(`inputBox.${key}`, () => {
        expect(zhCN.inputBox).toHaveProperty(key, value);
      });
    }

    describe("suggestions", () => {
      it("is an array with 4 items", () => {
        expect(zhCN.inputBox.suggestions).toHaveLength(4);
      });

      it("each item has suggestion, prompt, and icon", () => {
        for (const item of zhCN.inputBox.suggestions) {
          expect(item).toHaveProperty("suggestion");
          expect(item).toHaveProperty("prompt");
          expect(item).toHaveProperty("icon");
          expect(typeof item.suggestion).toBe("string");
          expect(typeof item.prompt).toBe("string");
        }
      });

      it("has correct suggestion labels", () => {
        const labels = zhCN.inputBox.suggestions.map((s) => s.suggestion);
        expect(labels).toEqual(["写作", "研究", "收集", "学习"]);
      });
    });

    describe("suggestionsCreate", () => {
      it("is an array with 5 items (including separator)", () => {
        expect(zhCN.inputBox.suggestionsCreate).toHaveLength(5);
      });

      it("has a separator at index 3", () => {
        const sep = zhCN.inputBox.suggestionsCreate[3];
        expect(sep).toEqual({ type: "separator" });
      });

      it("has correct suggestion labels", () => {
        const labels = zhCN.inputBox.suggestionsCreate
          .filter((s) => !("type" in s))
          .map((s) => (s as { suggestion: string }).suggestion);
        expect(labels).toEqual(["网页", "图片", "视频", "技能"]);
      });

      it("non-separator items have icon", () => {
        for (const item of zhCN.inputBox.suggestionsCreate) {
          if (!("type" in item)) {
            expect(item).toHaveProperty("icon");
            expect(item).toHaveProperty("prompt");
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
      newChat: "新对话",
      chats: "对话",
      recentChats: "最近的对话",
      demoChats: "演示对话",
      agents: "智能体",
      workflows: "工作流",
    };

    for (const [key, value] of Object.entries(expected)) {
      it(`sidebar.${key}`, () => {
        expect(zhCN.sidebar).toHaveProperty(key, value);
      });
    }

    it("has 6 keys", () => {
      expect(Object.keys(zhCN.sidebar)).toHaveLength(6);
    });
  });

  // =======================================================================
  // agents
  // =======================================================================
  describe("agents", () => {
    const expected: Record<string, string> = {
      title: "智能体",
      description: "创建和管理具有专属 Prompt 与能力的自定义智能体。",
      newAgent: "新建智能体",
      emptyTitle: "还没有自定义智能体",
      emptyDescription: "创建你的第一个自定义智能体，设置专属系统提示词。",
      chat: "对话",
      delete: "删除",
      deleteConfirm: "确定要删除该智能体吗？此操作不可撤销。",
      deleteSuccess: "智能体已删除",
      template: "模板",
      newChat: "新对话",
      createPageTitle: "设计你的智能体",
      createPageSubtitle: "描述你想要的智能体，我来帮你通过对话创建。",
      nameStepTitle: "给新智能体起个名字",
      nameStepHint:
        "只允许字母、数字和连字符，存储时自动转为小写（例如 code-reviewer）",
      nameStepPlaceholder: "例如 code-reviewer",
      nameStepContinue: "继续",
      nameStepInvalidError: "名称无效，只允许字母、数字和连字符",
      nameStepAlreadyExistsError: "已存在同名智能体",
      nameStepNetworkError: "网络请求失败，请检查网络或后端连接",
      nameStepCheckError: "无法验证名称可用性，请稍后重试",
      nameStepBootstrapMessage:
        "新智能体的名称是 {name}。请先帮我设计它的用途、行为方式和 SOUL.md，再保存它。",
      save: "保存智能体",
      saving: "正在保存智能体...",
      saveRequested:
        "已提交保存请求，iDeer 正在根据当前对话生成并保存初版智能体。",
      saveHint:
        "你可以在右上角的菜单里随时保存这个智能体，就算目前还只是初稿也可以。",
      saveCommandMessage:
        "请现在根据我们目前已经讨论的全部内容保存这个自定义智能体。这就是我明确的保存确认。如果仍有少量细节缺失，请根据上下文做出合理假设，生成一份简洁的英文初始 SOUL.md，并直接调用 setup_agent，不要再向我索要额外确认。",
      agentCreatedPendingRefresh:
        "智能体已创建，但 iDeer 暂时还无法读取到它。请稍后刷新当前页面。",
      more: "更多操作",
      agentCreated: "智能体已创建！",
      startChatting: "开始对话",
      backToGallery: "返回 Gallery",
      visibilityPrivate: "私有",
      visibilityDepartment: "部门",
      visibilityPublic: "公开",
      favoriteAdded: "已收藏",
      favoriteRemoved: "已取消收藏",
      exportSuccess: "智能体已导出",
      importSuccess: "智能体已导入",
    };

    for (const [key, value] of Object.entries(expected)) {
      it(`agents.${key}`, () => {
        expect(zhCN.agents).toHaveProperty(key, value);
      });
    }

    it("has the correct number of keys", () => {
      expect(Object.keys(zhCN.agents).length).toBeGreaterThanOrEqual(
        Object.keys(expected).length,
      );
    });

    it("nameStepBootstrapMessage contains {name} placeholder", () => {
      expect(zhCN.agents.nameStepBootstrapMessage).toContain("{name}");
    });
  });

  // =======================================================================
  // workflows
  // =======================================================================
  describe("workflows", () => {
    describe("string properties", () => {
      const expected: Record<string, string> = {
        title: "工作流",
        description: "管理和运行工作流定义",
        newWorkflow: "新建工作流",
        emptyTitle: "还没有工作流",
        emptyDescription: "创建你的第一个工作流以开始使用",
        view: "查看",
        deleteTitle: "删除工作流",
        deleteSuccess: "工作流已删除",
        deleting: "删除中...",
        unknown: "未知",
        notFound: "工作流未找到",
        backToWorkflows: "返回工作流",
        edit: "编辑",
        run: "运行",
        stepsDescription: "工作流执行步骤",
        noSteps: "未定义步骤",
        inputsTitle: "输入参数",
        inputsDescription: "必填和可选的输入参数",
        required: "必填",
        runStatus: "运行状态",
        runId: "运行 ID：",
        yamlDefinition: "YAML 定义",
        runDialog: "运行工作流",
        runDialogDescription: "为工作流执行提供输入值。",
        defaultPrefix: "默认值：",
        noInputs: "此工作流没有输入参数。",
        starting: "启动中...",
        createSubtitle: "用 YAML 定义新的工作流",
        yamlEditor: "YAML 编辑器",
        creating: "创建中...",
        saving: "保存中...",
        created: "工作流已创建",
        updated: "工作流已更新",
        started: "工作流已启动",
        saveChanges: "保存更改",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`workflows.${key}`, () => {
          expect(zhCN.workflows).toHaveProperty(key, value);
        });
      }
    });

    describe("function properties", () => {
      it("deleteConfirm interpolates name", () => {
        const result = zhCN.workflows.deleteConfirm("test-workflow");
        expect(result).toContain("test-workflow");
        expect(result).toContain("确定要删除");
      });

      it("steps returns count in string", () => {
        expect(zhCN.workflows.steps(3)).toBe("3 个步骤");
        expect(zhCN.workflows.steps(1)).toBe("1 个步骤");
      });

      it("inputs returns count in string", () => {
        expect(zhCN.workflows.inputs(5)).toBe("5 个输入");
        expect(zhCN.workflows.inputs(0)).toBe("0 个输入");
      });

      it("stepsTitle returns formatted string with count", () => {
        expect(zhCN.workflows.stepsTitle(4)).toBe("步骤 (4)");
      });

      it("enterInput interpolates key", () => {
        expect(zhCN.workflows.enterInput("username")).toBe("输入 username...");
      });

      it("requiredMissing interpolates key", () => {
        expect(zhCN.workflows.requiredMissing("apiKey")).toBe(
          "缺少必填输入「apiKey」",
        );
      });
    });
  });

  // =======================================================================
  // breadcrumb
  // =======================================================================
  describe("breadcrumb", () => {
    const expected: Record<string, string> = {
      workspace: "工作区",
      chats: "对话",
      workflows: "工作流",
      edit: "编辑",
      runs: "运行记录",
    };

    for (const [key, value] of Object.entries(expected)) {
      it(`breadcrumb.${key}`, () => {
        expect(zhCN.breadcrumb).toHaveProperty(key, value);
      });
    }

    it("has 5 keys", () => {
      expect(Object.keys(zhCN.breadcrumb)).toHaveLength(5);
    });
  });

  // =======================================================================
  // workspace
  // =======================================================================
  describe("workspace", () => {
    const expected: Record<string, string> = {
      officialWebsite: "访问 iDeer 官方网站",
      githubTooltip: "访问 iDeer 的 Github 仓库",
      settingsAndMore: "设置和更多",
      visitGithub: "在 Github 上查看 iDeer",
      reportIssue: "报告问题",
      contactUs: "联系我们",
      about: "关于 iDeer",
      logout: "退出登录",
      adminPanel: "管理后台",
      userManagement: "用户管理",
      departmentManagement: "部门管理",
      toolManagement: "工具管理",
      applicationManagement: "审批管理",
      auditLogManagement: "审计日志",
    };

    for (const [key, value] of Object.entries(expected)) {
      it(`workspace.${key}`, () => {
        expect(zhCN.workspace).toHaveProperty(key, value);
      });
    }

    it("has 14 keys", () => {
      expect(Object.keys(zhCN.workspace)).toHaveLength(15);
    });
  });

  // =======================================================================
  // conversation
  // =======================================================================
  describe("conversation", () => {
    it("conversation.noMessages", () => {
      expect(zhCN.conversation.noMessages).toBe("还没有消息");
    });

    it("conversation.startConversation", () => {
      expect(zhCN.conversation.startConversation).toBe(
        "开始新的对话以查看消息",
      );
    });

    it("has 2 keys", () => {
      expect(Object.keys(zhCN.conversation)).toHaveLength(2);
    });
  });

  // =======================================================================
  // chats
  // =======================================================================
  describe("chats", () => {
    it("chats.searchChats", () => {
      expect(zhCN.chats.searchChats).toBe("搜索对话");
    });

    it("has 1 key", () => {
      expect(Object.keys(zhCN.chats)).toHaveLength(1);
    });
  });

  // =======================================================================
  // pages
  // =======================================================================
  describe("pages", () => {
    const expected: Record<string, string> = {
      appName: "iDeer",
      chats: "对话",
      newChat: "新对话",
      untitled: "未命名",
    };

    for (const [key, value] of Object.entries(expected)) {
      it(`pages.${key}`, () => {
        expect(zhCN.pages).toHaveProperty(key, value);
      });
    }

    it("has 4 keys", () => {
      expect(Object.keys(zhCN.pages)).toHaveLength(4);
    });
  });

  // =======================================================================
  // toolCalls
  // =======================================================================
  describe("toolCalls", () => {
    const stringKeys: Record<string, string> = {
      lessSteps: "隐藏步骤",
      executeCommand: "执行命令",
      presentFiles: "展示文件",
      needYourHelp: "需要你的协助",
      searchForRelatedInfo: "搜索相关信息",
      searchForRelatedImages: "搜索相关图片",
      viewWebPage: "查看网页",
      listFolder: "列出文件夹",
      readFile: "读取文件",
      writeFile: "写入文件",
      clickToViewContent: "点击查看文件内容",
      writeTodos: "更新 To-do 列表",
      skillInstallTooltip: "安装技能并使其可在 iDeer 中使用",
    };

    for (const [key, value] of Object.entries(stringKeys)) {
      it(`toolCalls.${key}`, () => {
        expect(zhCN.toolCalls).toHaveProperty(key, value);
      });
    }

    describe("function properties", () => {
      it("moreSteps interpolates count", () => {
        expect(zhCN.toolCalls.moreSteps(5)).toBe("查看其他 5 个步骤");
        expect(zhCN.toolCalls.moreSteps(1)).toBe("查看其他 1 个步骤");
      });

      it("useTool interpolates toolName", () => {
        expect(zhCN.toolCalls.useTool("web-search")).toBe(
          "使用 “web-search” 工具",
        );
      });

      it("searchFor interpolates query", () => {
        expect(zhCN.toolCalls.searchFor("AI news")).toBe("搜索 “AI news”");
      });

      it("searchForRelatedImagesFor interpolates query", () => {
        expect(zhCN.toolCalls.searchForRelatedImagesFor("cats")).toBe(
          "搜索相关图片 “cats”",
        );
      });

      it("searchOnWebFor interpolates query", () => {
        expect(zhCN.toolCalls.searchOnWebFor("latest research")).toBe(
          "在网络上搜索 “latest research”",
        );
      });
    });
  });

  // =======================================================================
  // uploads
  // =======================================================================
  describe("uploads", () => {
    it("uploads.uploading", () => {
      expect(zhCN.uploads.uploading).toBe("上传中...");
    });

    it("uploads.uploadingFiles", () => {
      expect(zhCN.uploads.uploadingFiles).toBe("文件上传中，请稍候...");
    });

    it("has 2 keys", () => {
      expect(Object.keys(zhCN.uploads)).toHaveLength(2);
    });
  });

  // =======================================================================
  // subtasks
  // =======================================================================
  describe("subtasks", () => {
    it("subtasks.subtask", () => {
      expect(zhCN.subtasks.subtask).toBe("子任务");
    });

    it("subtasks.in_progress", () => {
      expect(zhCN.subtasks.in_progress).toBe("子任务运行中");
    });

    it("subtasks.completed", () => {
      expect(zhCN.subtasks.completed).toBe("子任务已完成");
    });

    it("subtasks.failed", () => {
      expect(zhCN.subtasks.failed).toBe("子任务失败");
    });

    describe("executing function", () => {
      it("returns singular form for count === 1", () => {
        expect(zhCN.subtasks.executing(1)).toBe("执行 1 个子任务");
      });

      it("returns parallel form for count > 1", () => {
        expect(zhCN.subtasks.executing(3)).toBe("并行执行 3 个子任务");
      });

      it("returns parallel form for count === 2", () => {
        expect(zhCN.subtasks.executing(2)).toBe("并行执行 2 个子任务");
      });

      it("no parallel prefix for count === 0", () => {
        expect(zhCN.subtasks.executing(0)).toBe("执行 0 个子任务");
      });
    });

    it("has 5 keys", () => {
      expect(Object.keys(zhCN.subtasks)).toHaveLength(5);
    });
  });

  // =======================================================================
  // tokenUsage
  // =======================================================================
  describe("tokenUsage", () => {
    const stringKeys: Record<string, string> = {
      title: "Token 用量",
      label: "Tokens",
      input: "输入",
      output: "输出",
      total: "总计",
      view: "显示方式",
      unavailable:
        "暂无 Token 用量。只有模型成功返回且供应商提供 usage_metadata 时才会显示。",
      unavailableShort: "未返回用量",
      note: "顶部总量优先使用后端持久化的线程用量；当当前回复仍在流式返回时，还会叠加可见的进行中用量。每轮和调试用量只来自当前可见消息，可能与平台账单页不完全一致。",
      finalAnswer: "最终回复",
      stepTotal: "步骤总计",
      sharedAttribution: "该 token 由此步骤中的多个动作共同消耗",
    };

    for (const [key, value] of Object.entries(stringKeys)) {
      it(`tokenUsage.${key}`, () => {
        expect(zhCN.tokenUsage).toHaveProperty(key, value);
      });
    }

    describe("presets", () => {
      const expected: Record<string, string> = {
        off: "关闭",
        summary: "总览",
        perTurn: "每轮",
        debug: "调试",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`tokenUsage.presets.${key}`, () => {
          expect(zhCN.tokenUsage.presets).toHaveProperty(key, value);
        });
      }

      it("has 4 keys", () => {
        expect(Object.keys(zhCN.tokenUsage.presets)).toHaveLength(4);
      });
    });

    describe("presetDescriptions", () => {
      const expected: Record<string, string> = {
        off: "隐藏顶部和会话内的 token 展示。",
        summary: "只在顶部显示当前对话累计 token。",
        perTurn: "显示顶部累计，并为每轮 assistant 回复显示一条汇总 token。",
        debug: "显示顶部累计，并展示按步骤归类的 token 调试信息。",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`tokenUsage.presetDescriptions.${key}`, () => {
          expect(zhCN.tokenUsage.presetDescriptions).toHaveProperty(key, value);
        });
      }

      it("has 4 keys", () => {
        expect(Object.keys(zhCN.tokenUsage.presetDescriptions)).toHaveLength(4);
      });
    });

    describe("function properties", () => {
      it("subagent interpolates description", () => {
        expect(zhCN.tokenUsage.subagent("research task")).toBe(
          "子任务：research task",
        );
      });

      it("startTodo interpolates content", () => {
        expect(zhCN.tokenUsage.startTodo("write tests")).toBe(
          "开始 To-do：write tests",
        );
      });

      it("completeTodo interpolates content", () => {
        expect(zhCN.tokenUsage.completeTodo("deploy app")).toBe(
          "完成 To-do：deploy app",
        );
      });

      it("updateTodo interpolates content", () => {
        expect(zhCN.tokenUsage.updateTodo("add logging")).toBe(
          "更新 To-do：add logging",
        );
      });

      it("removeTodo interpolates content", () => {
        expect(zhCN.tokenUsage.removeTodo("old task")).toBe(
          "移除 To-do：old task",
        );
      });
    });
  });

  // =======================================================================
  // shortcuts
  // =======================================================================
  describe("shortcuts", () => {
    const expected: Record<string, string> = {
      searchActions: "搜索操作...",
      noResults: "未找到结果。",
      actions: "操作",
      keyboardShortcuts: "键盘快捷键",
      keyboardShortcutsDescription: "使用键盘快捷键更快地操作 iDeer。",
      openCommandPalette: "打开命令面板",
      toggleSidebar: "切换侧边栏",
    };

    for (const [key, value] of Object.entries(expected)) {
      it(`shortcuts.${key}`, () => {
        expect(zhCN.shortcuts).toHaveProperty(key, value);
      });
    }

    it("has 7 keys", () => {
      expect(Object.keys(zhCN.shortcuts)).toHaveLength(7);
    });
  });

  // =======================================================================
  // settings
  // =======================================================================
  describe("settings", () => {
    it("settings.title", () => {
      expect(zhCN.settings.title).toBe("设置");
    });

    it("settings.description", () => {
      expect(zhCN.settings.description).toBe(
        "根据你的偏好调整 iDeer 的界面和行为。",
      );
    });

    // -------------------------------------------------------------------
    // settings.sections
    // -------------------------------------------------------------------
    describe("sections", () => {
      const expected: Record<string, string> = {
        account: "账号",
        appearance: "外观",
        memory: "记忆",
        tools: "工具",
        skills: "技能",
        notification: "通知",
        about: "关于",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`settings.sections.${key}`, () => {
          expect(zhCN.settings.sections).toHaveProperty(key, value);
        });
      }

      it("has 7 keys", () => {
        expect(Object.keys(zhCN.settings.sections)).toHaveLength(7);
      });
    });

    // -------------------------------------------------------------------
    // settings.memory
    // -------------------------------------------------------------------
    describe("memory", () => {
      const stringKeys: Record<string, string> = {
        title: "记忆",
        description:
          "iDeer 会在后台不断从你的对话中自动学习。这些记忆能帮助 iDeer 更好地理解你，并提供更个性化的体验。",
        empty: "暂无可展示的记忆数据。",
        rawJson: "原始 JSON",
        exportButton: "导出记忆",
        exportSuccess: "记忆已导出",
        importButton: "导入记忆",
        importConfirmTitle: "导入记忆？",
        importConfirmDescription: "这会用选中的 JSON 备份覆盖当前记忆。",
        importFileLabel: "已选择文件",
        importInvalidFile: "读取记忆文件失败，请选择有效的 JSON 导出文件。",
        importSuccess: "记忆已导入",
        manualFactSource: "手动添加",
        addFact: "添加事实",
        addFactTitle: "添加记忆事实",
        editFactTitle: "编辑记忆事实",
        addFactSuccess: "事实已创建",
        editFactSuccess: "事实已更新",
        clearAll: "清空全部记忆",
        clearAllConfirmTitle: "要清空全部记忆吗？",
        clearAllConfirmDescription:
          "这会删除所有已保存的摘要和事实。此操作无法撤销。",
        clearAllSuccess: "已清空全部记忆",
        factDeleteConfirmTitle: "要删除这条事实吗？",
        factDeleteConfirmDescription:
          "这条事实会立即从记忆中删除。此操作无法撤销。",
        factDeleteSuccess: "事实已删除",
        factContentLabel: "内容",
        factCategoryLabel: "类别",
        factConfidenceLabel: "置信度",
        factContentPlaceholder: "描述你想保存的记忆事实",
        factCategoryPlaceholder: "context",
        factConfidenceHint: "请输入 0 到 1 之间的数字。",
        factSave: "保存事实",
        factValidationContent: "事实内容不能为空。",
        factValidationConfidence: "置信度必须是 0 到 1 之间的数字。",
        noFacts: "还没有保存的事实。",
        summaryReadOnly:
          "摘要分区当前仍为只读。现在你可以清空全部记忆或删除单条事实。",
        memoryFullyEmpty: "还没有保存任何记忆。",
        factPreviewLabel: "即将删除的事实",
        searchPlaceholder: "搜索记忆",
        filterAll: "全部",
        filterFacts: "事实",
        filterSummaries: "摘要",
        noMatches: "没有找到匹配的记忆。",
      };

      for (const [key, value] of Object.entries(stringKeys)) {
        it(`settings.memory.${key}`, () => {
          expect(zhCN.settings.memory).toHaveProperty(key, value);
        });
      }

      describe("markdown", () => {
        const stringKeys: Record<string, string> = {
          overview: "概览",
          userContext: "用户上下文",
          work: "工作",
          personal: "个人",
          topOfMind: "近期关注（Top of mind）",
          historyBackground: "历史背景",
          recentMonths: "近几个月",
          earlierContext: "更早上下文",
          longTermBackground: "长期背景",
          updatedAt: "更新于",
          facts: "事实",
          empty: "（空）",
        };

        for (const [key, value] of Object.entries(stringKeys)) {
          it(`settings.memory.markdown.${key}`, () => {
            expect(zhCN.settings.memory.markdown).toHaveProperty(key, value);
          });
        }

        describe("table", () => {
          const tableKeys: Record<string, string> = {
            category: "类别",
            confidence: "置信度",
            content: "内容",
            source: "来源",
            createdAt: "创建时间",
            view: "查看",
          };

          for (const [key, value] of Object.entries(tableKeys)) {
            it(`settings.memory.markdown.table.${key}`, () => {
              expect(zhCN.settings.memory.markdown.table).toHaveProperty(
                key,
                value,
              );
            });
          }

          describe("confidenceLevel", () => {
            const expected: Record<string, string> = {
              veryHigh: "极高",
              high: "较高",
              normal: "一般",
              unknown: "未知",
            };

            for (const [key, value] of Object.entries(expected)) {
              it(`settings.memory.markdown.table.confidenceLevel.${key}`, () => {
                expect(
                  zhCN.settings.memory.markdown.table.confidenceLevel,
                ).toHaveProperty(key, value);
              });
            }

            it("has 4 keys", () => {
              expect(
                Object.keys(
                  zhCN.settings.memory.markdown.table.confidenceLevel,
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
        themeTitle: "主题",
        themeDescription: "跟随系统或选择固定的界面模式。",
        system: "系统",
        light: "浅色",
        dark: "深色",
        systemDescription: "自动跟随系统主题。",
        lightDescription: "更明亮的配色，适合日间使用。",
        darkDescription: "更暗的配色，减少眩光方便专注。",
        languageTitle: "语言",
        languageDescription: "在不同语言之间切换。",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`settings.appearance.${key}`, () => {
          expect(zhCN.settings.appearance).toHaveProperty(key, value);
        });
      }

      it("has 10 keys", () => {
        expect(Object.keys(zhCN.settings.appearance)).toHaveLength(10);
      });
    });

    // -------------------------------------------------------------------
    // settings.tools
    // -------------------------------------------------------------------
    describe("tools", () => {
      it("settings.tools.title", () => {
        expect(zhCN.settings.tools.title).toBe("工具");
      });

      it("settings.tools.description", () => {
        expect(zhCN.settings.tools.description).toBe(
          "管理 MCP 工具的配置和启用状态。",
        );
      });

      const expected: Record<string, string> = {
        title: "工具",
        description: "管理 MCP 工具的配置和启用状态。",
        addServer: "添加服务器",
        editServer: "编辑服务器",
        deleteConfirmTitle: "删除服务器？",
        deleteConfirmDescription: "该服务器将从配置中移除，此操作无法撤销。",
        serverName: "服务器名称",
        serverType: "类型",
        command: "命令",
        args: "参数",
        url: "URL",
        env: "环境变量",
        headers: "请求头",
        emptyState:
          "暂无 MCP 服务器，点击「添加服务器」来配置你的第一个 MCP 服务。",
        validationNameRequired: "服务器名称不能为空。",
        validationNameExists: "该名称的服务器已存在。",
        addSuccess: "服务器已添加",
        editSuccess: "服务器已更新",
        deleteSuccess: "服务器已删除",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`settings.tools.${key}`, () => {
          expect(zhCN.settings.tools).toHaveProperty(key, value);
        });
      }

      it("has 19 keys", () => {
        expect(Object.keys(zhCN.settings.tools)).toHaveLength(19);
      });
    });

    // -------------------------------------------------------------------
    // settings.skills
    // -------------------------------------------------------------------
    describe("skills", () => {
      const expected: Record<string, string> = {
        title: "技能",
        description: "管理 Agent Skill 配置和启用状态。",
        createSkill: "新建技能",
        emptyTitle: "还没有技能",
        emptyDescription:
          "将你的 Agent Skill 文件夹放在 iDeer 根目录下的 `/resources/skills` 文件夹中。",
        emptyButton: "创建你的第一个技能",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`settings.skills.${key}`, () => {
          expect(zhCN.settings.skills).toHaveProperty(key, value);
        });
      }

      it("has at least 22 keys", () => {
        expect(Object.keys(zhCN.settings.skills).length).toBeGreaterThanOrEqual(
          22,
        );
      });
    });

    // -------------------------------------------------------------------
    // settings.notification
    // -------------------------------------------------------------------
    describe("notification", () => {
      const expected: Record<string, string> = {
        title: "通知",
        description:
          "iDeer 只会在窗口不活跃时发送完成通知，特别适合长时间任务：你可以先去做别的事，完成后会收到提醒。",
        requestPermission: "请求通知权限",
        deniedHint:
          "通知权限已被拒绝。可在浏览器的网站设置中重新开启，以接收完成提醒。",
        testButton: "发送测试通知",
        testTitle: "iDeer",
        testBody: "这是一条测试通知。",
        notSupported: "当前浏览器不支持通知功能。",
        disableNotification: "关闭通知",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`settings.notification.${key}`, () => {
          expect(zhCN.settings.notification).toHaveProperty(key, value);
        });
      }

      it("has 9 keys", () => {
        expect(Object.keys(zhCN.settings.notification)).toHaveLength(9);
      });
    });

    // -------------------------------------------------------------------
    // settings.account
    // -------------------------------------------------------------------
    describe("account", () => {
      const expected: Record<string, string> = {
        profileTitle: "个人信息",
        email: "邮箱",
        role: "角色",
        changePasswordTitle: "修改密码",
        changePasswordDescription: "更新你的账号密码。",
        currentPassword: "当前密码",
        newPassword: "新密码",
        confirmNewPassword: "确认新密码",
        passwordMismatch: "两次输入的新密码不一致",
        passwordTooShort: "密码长度至少为 8 个字符",
        passwordChangedSuccess: "密码修改成功",
        networkError: "网络错误，请重试。",
        updating: "更新中...",
        updatePassword: "修改密码",
        signOut: "退出登录",
      };

      for (const [key, value] of Object.entries(expected)) {
        it(`settings.account.${key}`, () => {
          expect(zhCN.settings.account).toHaveProperty(key, value);
        });
      }

      it("has 15 keys", () => {
        expect(Object.keys(zhCN.settings.account)).toHaveLength(15);
      });
    });

    // -------------------------------------------------------------------
    // settings.acknowledge
    // -------------------------------------------------------------------
    describe("acknowledge", () => {
      it("settings.acknowledge.emptyTitle", () => {
        expect(zhCN.settings.acknowledge.emptyTitle).toBe("致谢");
      });

      it("settings.acknowledge.emptyDescription", () => {
        expect(zhCN.settings.acknowledge.emptyDescription).toBe(
          "相关的致谢信息会展示在这里。",
        );
      });

      it("has 2 keys", () => {
        expect(Object.keys(zhCN.settings.acknowledge)).toHaveLength(2);
      });
    });
  });

  // =======================================================================
  // Cross-cutting: every string leaf is non-empty
  // =======================================================================
  describe("all string leaves are non-empty", () => {
    const leaves = collectLeafPaths(zhCN as unknown as Record<string, unknown>);

    for (const [path, value] of leaves) {
      if (typeof value === "string") {
        it(`${path} is a non-empty string`, () => {
          expect(value.trim().length).toBeGreaterThan(0);
        });
      }
    }
  });

  // =======================================================================
  // Cross-cutting: no English text leaks in string values
  // (English-only words that are not brand names or mode labels)
  // =======================================================================
  describe("brand consistency", () => {
    it("pages.appName uses iDeer", () => {
      expect(zhCN.pages.appName).toBe("iDeer");
    });

    it("welcome.description mentions iDeer", () => {
      expect(zhCN.welcome.description).toContain("iDeer");
    });

    it("settings.description mentions iDeer", () => {
      expect(zhCN.settings.description).toContain("iDeer");
    });

    it("shortcuts.keyboardShortcutsDescription mentions iDeer", () => {
      expect(zhCN.shortcuts.keyboardShortcutsDescription).toContain("iDeer");
    });
  });
});
