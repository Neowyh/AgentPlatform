import type { ScenarioId, ScenarioTab } from "./types";

export const SCENARIOS: ScenarioTab[] = [
  {
    id: "daily",
    labelKey: "scenarios.daily",
    icon: "Briefcase",
    agentPills: [
      {
        agentSlug: "office-docs",
        label: "办公文档",
        chips: [
          {
            taskId: "word-editor",
            label: "Word 创建编辑",
            skillName: "anthropic-docx",
            promptTemplate:
              "请处理以下 Word 文档。目标：[要完成的事情]；材料：[上传文件或粘贴内容]；要求：[格式/语气/保留内容]。请先概括处理方案，再完成修改并列出变更点与待确认项。",
          },
          {
            taskId: "pdf-processing",
            label: "PDF 处理合并",
            skillName: "anthropic-pdf",
            promptTemplate:
              "请处理以下 PDF。目标：[合并/拆分/提取/转换/整理]；文件：[上传 PDF]；范围：[页码或章节]；要求：[输出格式与命名]。请检查页序、内容完整性和版式，最后给出处理结果摘要。",
          },
          {
            taskId: "excel-read-write",
            label: "Excel 读写",
            skillName: "officecli",
            promptTemplate:
              "请处理以下 Excel。目标：[读取/清洗/计算/生成]；文件：[上传表格]；工作表：[名称]；要求：[字段、公式、格式与输出]。请保留原始数据，说明关键处理逻辑并标注异常值。",
          },
        ],
      },
      {
        agentSlug: "data-analysis",
        label: "数据分析",
        chips: [
          {
            taskId: "excel-data-analysis",
            label: "Excel 数据分析",
            skillName: "data-analysis",
            promptTemplate:
              "请分析以下数据。业务问题：[希望回答的问题]；数据：[粘贴数据或上传文件]；指标口径：[统计范围与时间]；期望输出：[结论/图表/建议]。请先检查数据质量，再给出可复核的分析过程和行动建议。",
          },
          {
            taskId: "excel-formulas",
            label: "Excel 公式",
            skillName: "anthropic-xlsx",
            promptTemplate:
              "请处理以下 Excel 公式。目标：[修复/设计/批量填充]；工作表与区域：[位置]；现有公式或报错：[粘贴内容]；期望结果：[计算规则]。请解释公式逻辑，覆盖空值、边界值和复制填充场景，并给出可直接使用的公式。",
          },
        ],
      },
      {
        agentSlug: "translation",
        label: "翻译润色",
        chips: [
          {
            taskId: "document-translation",
            label: "文档翻译",
            skillName: "translate",
            promptTemplate:
              "请将以下内容翻译成[目标语言]。原文：[粘贴文本或上传文件]；读者：[受众]；语域：[正式/商务/技术/自然]；术语表：[固定译法]。请保持事实、结构和格式一致，并列出可能存在歧义的译法。",
          },
          {
            taskId: "humanize-chinese",
            label: "去 AI 味",
            skillName: "humanizer-zh",
            promptTemplate:
              "请对以下中文内容进行去 AI 味处理。原文：[粘贴文字]；读者：[受众]；使用场景：[文章/汇报/社交/公文]；希望的语气：[具体风格]。请保留原意和事实，减少模板化表达，输出润色稿并简要说明主要调整。",
          },
        ],
      },
      {
        agentSlug: "document-writing",
        label: "文书处理",
        chips: [
          {
            taskId: "official-writing",
            label: "公文撰写",
            skillName: "wps-gongwen",
            promptTemplate:
              "请撰写以下公文。文种：[通知/请示/报告等]；主题：[事项]；背景与依据：[材料]；对象：[主送单位]；关键事实：[时间、地点、数据]；要求：[篇幅与格式]。请遵循正式、准确、可执行的表达，先列结构提纲再输出正文。",
          },
          {
            taskId: "proofread-text",
            label: "文字校对",
            skillName: "wps-proofread",
            promptTemplate:
              "请校对以下文字。原文：[粘贴内容或上传文件]；类型：[文章/报告/公文/说明书]；重点：[错别字、语法、术语、标点、格式]；规范：[指定词表或写作规范]。请输出修订稿，并用表格列出原文、修改后内容和修改理由。",
          },
          {
            taskId: "structured-report",
            label: "报告撰写",
            skillName: "structured-longform-writing",
            promptTemplate:
              "请撰写一篇结构化长文。主题与类型：[主题/报告类型]；目标读者：[受众]；已有材料：[粘贴或上传]；核心观点：[必须覆盖的结论]；篇幅与结构：[章节要求]；引用规范：[来源要求]。请先给出提纲，正文中区分事实、分析与建议，结尾附摘要和待补信息。",
          },
        ],
      },
      {
        agentSlug: "summarize",
        label: "智能摘要",
        chips: [
          {
            taskId: "document-summary",
            label: "文档摘要",
            skillName: "summarize",
            promptTemplate:
              "请对以下文档做中等长度摘要。材料：[上传附件或粘贴文本]；用途：[阅读决策/汇报/归档]；输出 Markdown，包含：摘要、核心要点 5 条、关键词 5 个、结论与风险；尽量标注来源页码或原文位置，不补写材料中没有的事实。",
          },
          {
            taskId: "meeting-minutes",
            label: "会议纪要",
            skillName: "summarize",
            promptTemplate:
              "请将以下会议记录整理为正式纪要。记录：[粘贴内容或上传附件]；会议主题与日期：[信息]；参会人：[名单]。输出包含：会议摘要、讨论事项、已确认决议、待办清单（责任人/截止日期/依赖）、未决问题；无法确定的信息标记为待确认。",
          },
          {
            taskId: "key-points",
            label: "要点提炼",
            skillName: "summarize",
            promptTemplate:
              "请提炼以下长文要点。原文：[粘贴内容或上传附件]；读者：[受众]；用途：[快速了解/决策/转述]。输出 3-5 条要点，每条不超过 40 字，按重要性排序，并附关键词 5 个；保留限定条件和数字，不把推测写成事实。",
          },
        ],
      },
    ],
  },
  {
    id: "creative",
    labelKey: "scenarios.creative",
    icon: "Palette",
    agentPills: [
      {
        agentSlug: "ppt-web",
        label: "PPT 制作",
        chips: [
          {
            taskId: "web-presentation",
            label: "网页 PPT",
            skillName: "guizang-ppt-skill",
            promptTemplate:
              "请制作一套网页 PPT。主题：[主题]；受众：[听众]；目的：[汇报/教学/说服]；页数：[范围]；内容材料：[粘贴或上传]；视觉方向：[品牌色/风格]。请先给出叙事结构和逐页大纲，再生成页面；每页只保留一个核心信息，并兼顾演示可读性。",
          },
          {
            taskId: "presentation-create",
            label: "PPT 创建",
            skillName: "anthropic-pptx",
            promptTemplate:
              "请创建一套 PPT。主题：[主题]；受众与场景：[信息]；目标：[需要听众理解或采取的行动]；素材：[粘贴或上传]；页数与比例：[设置]；视觉偏好：[风格]。请输出逐页标题、核心信息、证据/图表建议和讲述备注，避免堆砌文字。",
          },
          {
            taskId: "presentation-edit",
            label: "PPT 编辑",
            skillName: "officecli",
            promptTemplate:
              "请编辑以下 PPT。文件：[上传 PPT]；修改目标：[内容/版式/视觉/结构]；必须保留：[页面、数据、品牌元素]；参考风格：[示例或描述]；交付要求：[格式与页数]。请先检查全稿一致性，再执行修改并列出每页的变更与可能影响。",
          },
        ],
      },
      {
        agentSlug: "visual-doc",
        label: "版式文档",
        chips: [
          {
            taskId: "visual-report",
            label: "视觉报告",
            skillName: "anthropic-docx",
            promptTemplate:
              "请制作一份视觉化报告。主题：[主题]；读者：[受众]；决策问题：[需要支持的判断]；数据与材料：[上传或粘贴]；篇幅：[页数/章节]；视觉语言：[色彩、图表偏好]。请建立信息层级，确保每个图表有标题、口径和结论，并输出可执行建议。",
          },
          {
            taskId: "pdf-layout",
            label: "PDF 排版",
            skillName: "anthropic-pdf",
            promptTemplate:
              "请为以下 PDF 文档重新排版。文件：[上传 PDF 或源文档]；目标：[阅读/打印/发布]；页面规格：[尺寸与页边距]；版式要求：[封面、目录、页眉页脚、表格]；视觉风格：[描述]。请检查字体嵌入、断行、图表清晰度和页码连续性，最后列出排版检查结果。",
          },
        ],
      },
      {
        agentSlug: "frontend-design",
        label: "前端设计",
        chips: [
          {
            taskId: "page-generation",
            label: "页面生成",
            skillName: "frontend-design",
            promptTemplate:
              "请生成一个前端页面。页面类型与用户目标：[描述]；核心流程：[用户从进入到完成的步骤]；内容与数据：[字段/示例]；视觉方向：[品牌、色彩、字体与参考]；技术约束：[框架、响应式、组件]。请先给出信息架构和交互状态，再生成可运行页面，确保空态、错误态、键盘操作和移动端可用。",
          },
          {
            taskId: "design-audit",
            label: "设计审计",
            skillName: "web-design-guidelines",
            promptTemplate:
              "请审计以下前端页面。代码或截图：[粘贴/上传]；目标用户与场景：[信息]；重点：[层级、间距、颜色、响应式、键盘、屏幕阅读器]；规范：[WCAG 级别或设计系统]。请按严重程度列出问题、证据、影响和修复建议，并给出验收清单。",
          },
        ],
      },
      {
        agentSlug: "creative-play",
        label: "创意探索",
        chips: [
          {
            taskId: "surprise-me",
            label: "给我惊喜",
            skillName: "surprise-me",
            promptTemplate:
              "请基于以下偏好设计一份有完成度的创意作品。主题或限制：[主题/禁用元素]；受众：[人群]；用途：[展示/传播/实验]；偏好：[风格、色彩、媒介]。请主动选择合适的已启用技能，先说明创意概念与取舍，再交付作品，并附可继续迭代的方向。",
          },
          {
            taskId: "design-review",
            label: "深度追问",
            skillName: "grill-me",
            promptTemplate:
              "请对以下方案进行深度追问。方案：[粘贴 PRD、计划或设计]；目标：[希望达成的结果]；约束：[时间、预算、资源]；已知风险：[信息]。请从目标、用户、证据、边界、依赖、失败路径和验收标准逐层提问，最后归纳关键缺口与建议结论。",
          },
          {
            taskId: "caveman-mode",
            label: "极简模式",
            skillName: "caveman",
            promptTemplate:
              "请进入极简回答模式。问题：[粘贴问题]；需要的输出：[结论/步骤/代码]；必须保留：[关键约束]。先给一句结论，再用最少但完整的要点回答；不重复背景，不使用空泛铺垫，若信息不足只提出最关键的一个问题。",
          },
        ],
      },
      {
        agentSlug: "skill-workshop",
        label: "技能工坊",
        chips: [
          {
            taskId: "custom-agent",
            label: "定制智能体",
            skillName: "bootstrap",
            promptTemplate:
              "请帮我定制一个智能体。我的身份与背景：[信息]；智能体名称：[名称]；主要职责：[要解决的问题]；目标用户：[人群]；语气与边界：[偏好/禁区]；输出格式：[要求]。请生成角色定位、能力范围、工作流程、澄清规则、质量标准和可直接使用的系统提示词。",
          },
          {
            taskId: "create-skill",
            label: "创建技能",
            skillName: "skill-creator",
            promptTemplate:
              "请帮我创建一个可复用的新技能。技能目标：[要完成的任务]；触发词：[用户会怎么说]；输入：[材料与格式]；处理步骤：[规则]；输出：[结构与示例]；工具权限：[需要/禁止]；失败处理：[要求]。请生成技能说明、边界、验收样例和完整 SKILL.md 草稿。",
          },
          {
            taskId: "proactive-inspection",
            label: "主动巡检",
            skillName: "proactive-agent",
            promptTemplate:
              "请配置一个主动巡检。巡检目标：[对象与指标]；触发条件：[事件/阈值]；周期：[频率与时区]；数据来源：[系统或文件]；通知对象：[人或群组]；处理动作：[允许的操作]；升级规则：[条件]。请输出巡检流程、告警模板、误报处理和验收用例。",
          },
        ],
      },
    ],
  },
  {
    id: "professional",
    labelKey: "scenarios.professional",
    icon: "ShieldCheck",
    agentPills: [
      {
        agentSlug: "code-dev",
        label: "代码开发",
        chips: [
          {
            taskId: "plan-challenge",
            label: "方案质询",
            skillName: "grill-with-docs",
            promptTemplate:
              "请质询以下方案并沉淀成评审文档。方案：[粘贴 PRD、计划或技术方案]；背景与目标：[信息]；约束：[时间、成本、合规]；评审标准：[成功指标]。请检查目标一致性、证据、架构、依赖、风险、替代方案和验收标准，输出问题清单、结论、行动项与决策记录。",
          },
          {
            taskId: "requirements-specification",
            label: "需求规格化",
            skillName: "to-spec",
            promptTemplate:
              "请将以下需求整理为完整规格。需求背景：[上下文]；用户与角色：[信息]；目标：[结果]；范围：[包含/不包含]；业务规则：[规则]；数据与接口：[信息]；约束：[性能、权限、兼容性]。请输出可追踪的需求规格、流程、异常场景、验收标准和待澄清问题。",
          },
          {
            taskId: "development-tickets",
            label: "拆分研发任务",
            skillName: "to-tickets",
            promptTemplate:
              "请将以下规格拆分为可执行的研发任务。规格：[粘贴文档]；团队与技术栈：[信息]；迭代周期：[时间]；优先级规则：[规则]。请按依赖关系拆分到可独立交付的粒度，为每项任务给出目标、范围、实现提示、验收标准、测试要求、风险和估算。",
          },
          {
            taskId: "spec-implementation",
            label: "按规格实现",
            skillName: "implement",
            promptTemplate:
              "请按以下规格实现需求。规格或任务：[粘贴内容]；代码库上下文：[目录/约束]；不可变更项：[列表]；验收标准：[标准]。请先分析现状与方案，再进行最小必要修改，补充回归测试，并说明改动文件、验证命令和未解决风险。",
          },
          {
            taskId: "code-review",
            label: "代码变更评审",
            skillName: "code-review",
            promptTemplate:
              "请评审以下代码变更。Diff 或代码：[粘贴内容]；关联需求：[信息]；运行环境：[技术栈]；重点风险：[正确性/安全/性能/兼容性]。请按严重程度给出可复现证据、影响范围和修复建议，优先指出会阻断发布的问题，并检查测试覆盖。",
          },
          {
            taskId: "architecture-analysis",
            label: "代码库架构改进",
            skillName: "improve-codebase-architecture",
            promptTemplate:
              "请分析以下代码库的架构改进机会。代码或模块：[目录、调用链或文件]；业务目标：[目标]；当前痛点：[问题]；约束：[兼容、性能、团队]。请从边界、依赖、状态、可测试性和演进成本出发，给出证据、分阶段方案、风险和可验证的成功指标。",
          },
          {
            taskId: "bug-diagnosis",
            label: "疑难故障诊断",
            skillName: "diagnosing-bugs",
            promptTemplate:
              "请诊断以下 Bug。现象：[描述]；期望与实际：[对比]；复现步骤：[步骤]；日志或堆栈：[粘贴]；环境与版本：[信息]；最近变更：[信息]。请先区分事实与假设，定位最可能根因，给出最小修复、回归测试、验证步骤和仍需观测的风险。",
          },
        ],
      },
      {
        agentSlug: "srs-writing",
        label: "软件需求规格编写",
        chips: [
          {
            taskId: "srs-writing",
            label: "需求规格说明撰写",
            skillName: "srs-writing",
            promptTemplate:
              "请撰写一份软件需求规格说明。项目名称与背景：[信息]；用户与角色：[信息]；目标与成功指标：[指标]；功能范围：[列表]；非功能要求：[性能、安全、可用性]；接口与数据：[信息]；限制与假设：[信息]。请形成结构完整、可追踪、可验收的 SRS，并列出待确认项。",
          },
        ],
      },
      {
        agentSlug: "abaqus",
        label: "仿真分析",
        chips: [
          {
            taskId: "abaqus-assembly",
            label: "零件装配",
            skillName: "abaqus-geometry",
            promptTemplate:
              "请审查或创建以下 Abaqus 零件与装配。模型或 INP：[上传文件/描述几何]；单位制：[信息]；零件关系：[信息]；边界与连接：[信息]；目标分析：[场景]。请检查命名、几何闭合、装配约束和单位一致性，输出修改建议、脚本片段与验证清单。",
          },
          {
            taskId: "abaqus-materials",
            label: "材料截面",
            skillName: "abaqus-material",
            promptTemplate:
              "请审查或定义 Abaqus 材料与截面属性。材料：[名称与本构]；单位制：[信息]；温度/载荷范围：[信息]；截面与厚度：[信息]；实验数据：[上传或粘贴]。请检查参数完整性、单位一致性、适用范围和缺失数据，输出可复用定义与校核方法。",
          },
          {
            taskId: "abaqus-mesh",
            label: "网格划分",
            skillName: "abaqus-mesh",
            promptTemplate:
              "请审查或生成 Abaqus 网格。模型：[上传文件或描述]；分析类型：[静力/显式等]；单元类型：[期望]；种子尺寸：[信息]；局部加密区：[位置]；质量指标：[要求]。请说明网格策略，检查畸变、过渡、收敛与计算成本，并给出可执行设置。",
          },
          {
            taskId: "abaqus-preflight",
            label: "依赖预检",
            skillName: "abaqus-dependency-preflight-validator",
            promptTemplate:
              "请预检 Abaqus 脚本项目。项目结构：[目录树]；入口脚本：[文件]；运行命令：[命令]；依赖与版本：[信息]；近期改动：[信息]。请检查导入、路径、参数、集合/实例标识符、前后处理接口和可重复运行性，输出阻断项与逐项修复建议。",
          },
          {
            taskId: "abaqus-debugging",
            label: "脚本调试",
            skillName: "abaqus-script-debugging-checklist",
            promptTemplate:
              "请调试以下 Abaqus Python 脚本。脚本：[粘贴或上传]；报错与堆栈：[信息]；期望行为：[描述]；模型上下文：[部件/步骤/输出]；版本与运行方式：[信息]。请定位根因，给出最小补丁，并说明如何在干净环境中复现和验证。",
          },
          {
            taskId: "abaqus-odb",
            label: "ODB 检查",
            skillName: "abaqus-odb",
            promptTemplate:
              "请检查以下 Abaqus ODB 结果数据库。文件：[上传 ODB]；分析步骤与帧：[范围]；关心的场输出：[变量]；异常现象：[描述]；期望指标：[指标]。请检查结果可用性、输出频率、单位与提取范围，给出异常解释和可复核的提取方案。",
          },
          {
            taskId: "abaqus-export",
            label: "结果导出",
            skillName: "abaqus-export",
            promptTemplate:
              "请规划 Abaqus 结果导出。ODB 或模型：[文件/描述]；目标结果：[变量与区域]；输出格式：[CSV/表格/图片]；采样规则：[步骤、帧、频率]；命名与溯源：[要求]；后续用途：[分析/报告]。请给出字段定义、导出流程、质量校验和可重复执行的脚本方案。",
          },
        ],
      },
      {
        agentSlug: "fault-zeroing",
        label: "故障归零",
        chips: [
          {
            taskId: "fault-zeroing",
            label: "故障归零",
            skillName: "fault-zeroing",
            promptTemplate:
              "请对以下故障开展归零分析。故障现象：[描述]；发生时间与环境：[信息]；影响范围：[对象/指标]；日志、数据与变更：[材料]；已采取措施：[信息]。请按现象确认、影响评估、根因树、证据验证、修复措施、预防机制和关闭标准输出完整闭环。",
          },
        ],
      },
      {
        agentSlug: "paper-review",
        label: "论文评审",
        chips: [
          {
            taskId: "academic-paper-review",
            label: "论文评审",
            skillName: "academic-paper-review",
            promptTemplate:
              "请评审以下学术论文。论文：[上传 PDF 或粘贴内容]；研究领域：[方向]；目标期刊或会议：[信息]；评审重点：[创新性、方法、数据、论证、复现性、写作]。请先概括贡献，再按问题严重程度给出证据、修改建议和接收建议，区分必改项与可选优化。",
          },
        ],
      },
    ],
  },
];

export function getScenarioById(id: ScenarioId) {
  return SCENARIOS.find((s) => s.id === id);
}

export const SCENARIO_IDS = SCENARIOS.map((scenario) => scenario.id);
export const SCENARIO_ICONS = Object.fromEntries(
  SCENARIOS.map((scenario) => [scenario.id, scenario.icon]),
) as Record<ScenarioId, string>;

export function getPillsByScenario(scenarioId: ScenarioId) {
  return getScenarioById(scenarioId)?.agentPills ?? [];
}

export function getChipsByPill(scenarioId: ScenarioId, agentSlug: string) {
  return (
    getPillsByScenario(scenarioId).find((p) => p.agentSlug === agentSlug)
      ?.chips ?? []
  );
}
