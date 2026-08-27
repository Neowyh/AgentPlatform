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
            label: "Word 创建编辑",
            skillName: "anthropic-docx",
            promptTemplate: "请帮我处理以下 Word 文档：[描述需求]",
          },
          {
            label: "PDF 处理合并",
            skillName: "anthropic-pdf",
            promptTemplate: "请帮我处理以下 PDF：[描述需求]",
          },
          {
            label: "Excel 读写",
            skillName: "officecli",
            promptTemplate: "请帮我处理以下 Excel：[描述需求]",
          },
        ],
      },
      {
        agentSlug: "data-analysis",
        label: "数据分析",
        chips: [
          {
            label: "Excel 数据分析",
            skillName: "data-analysis",
            promptTemplate: "请帮我分析以下数据：[粘贴数据或描述数据]",
          },
          {
            label: "Excel 公式",
            skillName: "anthropic-xlsx",
            promptTemplate: "请帮我处理以下 Excel 公式：[描述需求]",
          },
        ],
      },
      {
        agentSlug: "translation",
        label: "翻译润色",
        chips: [
          {
            label: "文档翻译",
            skillName: "translate",
            promptTemplate: "请将以下内容翻译成[目标语言]：[粘贴原文]",
          },
          {
            label: "去 AI 味",
            skillName: "humanizer-zh",
            promptTemplate: "请对以下中文内容进行去 AI 味处理：[粘贴文字]",
          },
        ],
      },
      {
        agentSlug: "document-writing",
        label: "文书处理",
        chips: [
          {
            label: "公文撰写",
            skillName: "wps-gongwen",
            promptTemplate: "请帮我撰写以下公文：[文种] [主题]",
          },
          {
            label: "文字校对",
            skillName: "wps-proofread",
            promptTemplate: "请校对以下文字：[粘贴文字]",
          },
          {
            label: "报告撰写",
            skillName: "structured-longform-writing",
            promptTemplate:
              "请帮我撰写以下结构化长文：[主题/类型]，要求：[具体要求]",
          },
        ],
      },
      {
        agentSlug: "summarize",
        label: "智能摘要",
        chips: [
          {
            label: "文档摘要",
            skillName: "summarize",
            promptTemplate:
              "请用 summarize 技能对我上传的文档做 medium 长度摘要（markdown 输出，含 摘要/核心要点 5条/关键词 5个，标注来源页码）：[粘贴文本或上传附件]",
          },
          {
            label: "会议纪要",
            skillName: "summarize",
            promptTemplate:
              "请用 summarize 技能将以下会议记录整理为纪要（long 长度，分 摘要/决议/待办 三段，待办含责任人与截止日期）：[粘贴记录]",
          },
          {
            label: "要点提炼",
            skillName: "summarize",
            promptTemplate:
              "请用 summarize 技能对以下长文做 short 长度要点提炼（3-5 条，每条 ≤40 字，附关键词 5个）：[粘贴长文]",
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
            label: "网页 PPT",
            skillName: "guizang-ppt-skill",
            promptTemplate: "请帮我制作以下主题的网页 PPT：[主题]",
          },
          {
            label: "PPT 创建",
            skillName: "anthropic-pptx",
            promptTemplate: "请帮我创建以下主题的 PPT：[主题]",
          },
          {
            label: "PPT 编辑",
            skillName: "officecli",
            promptTemplate: "请帮我编辑以下 PPT：[描述修改内容]",
          },
        ],
      },
      {
        agentSlug: "visual-doc",
        label: "版式文档",
        chips: [
          {
            label: "视觉报告",
            skillName: "anthropic-docx",
            promptTemplate: "请帮我制作一份视觉化报告：[主题]",
          },
          {
            label: "PDF 排版",
            skillName: "anthropic-pdf",
            promptTemplate: "请帮我排版以下 PDF 文档：[描述需求]",
          },
        ],
      },
      {
        agentSlug: "frontend-design",
        label: "前端设计",
        chips: [
          {
            label: "页面生成",
            skillName: "frontend-design",
            promptTemplate: "请帮我生成以下前端页面：[描述页面类型/功能/风格]",
          },
          {
            label: "设计审计",
            skillName: "web-design-guidelines",
            promptTemplate:
              "请帮我审计以下前端页面的设计规范与无障碍合规性：[粘贴代码或描述页面]",
          },
        ],
      },
      {
        agentSlug: "creative-play",
        label: "创意探索",
        chips: [
          {
            label: "给我惊喜",
            skillName: "surprise-me",
            promptTemplate:
              "请给我个惊喜：基于已启用的技能动态组合，生成一份有视觉冲击力的创意作品，偏好[主题/风格]",
          },
          {
            label: "深度追问",
            skillName: "grill-me",
            promptTemplate:
              "请使用深度追问技能帮我审查以下方案：[粘贴方案/PRD/计划]",
          },
          {
            label: "极简模式",
            skillName: "caveman",
            promptTemplate:
              "请进入 caveman 极简模式，用超压缩风格回答以下问题：[问题]",
          },
        ],
      },
      {
        agentSlug: "skill-workshop",
        label: "技能工坊",
        chips: [
          {
            label: "定制智能体",
            skillName: "bootstrap",
            promptTemplate:
              "请帮我定制智能体人格：我叫[姓名]，角色是[角色/背景]，希望 AI 叫[AI 名称]",
          },
          {
            label: "创建技能",
            skillName: "skill-creator",
            promptTemplate:
              "请帮我创建一个新技能，目标：[技能目标]，触发词：[触发词]",
          },
          {
            label: "主动巡检",
            skillName: "proactive-agent",
            promptTemplate:
              "请帮我配置主动巡检：[描述巡检目标/触发条件/巡检周期]",
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
            label: "TDD 驱动",
            skillName: "tdd",
            promptTemplate: "请帮我用 TDD 方式实现以下功能：[描述功能需求]",
          },
          {
            label: "代码评审",
            skillName: "code-review",
            promptTemplate: "请帮我评审以下代码变更：[粘贴 diff 或描述变更]",
          },
          {
            label: "排故诊断",
            skillName: "diagnosing-bugs",
            promptTemplate: "请帮我诊断以下 Bug：[描述错误现象/堆栈信息]",
          },
          {
            label: "架构深潜",
            skillName: "improve-codebase-architecture",
            promptTemplate:
              "请帮我分析以下代码库的架构改进机会：[粘贴代码或描述模块]",
          },
          {
            label: "领域建模",
            skillName: "domain-modeling",
            promptTemplate:
              "请帮我构建/梳理以下领域的领域模型：[描述业务领域/术语]",
          },
          {
            label: "SRS 撰写",
            skillName: "srs-writing",
            promptTemplate:
              "请帮我撰写以下项目的软件需求规格说明：[项目名称/背景]",
          },
        ],
      },
      {
        agentSlug: "abaqus",
        label: "仿真分析",
        chips: [
          {
            label: "零件装配",
            skillName: "abaqus-geometry",
            promptTemplate:
              "请帮我审查/创建 Abaqus 零件与装配：[描述几何或上传 INP]",
          },
          {
            label: "材料截面",
            skillName: "abaqus-material",
            promptTemplate:
              "请帮我审查/定义 Abaqus 材料与截面属性：[描述材料需求]",
          },
          {
            label: "网格划分",
            skillName: "abaqus-mesh",
            promptTemplate:
              "请帮我审查/生成 Abaqus 网格：[描述单元类型/种子/控制]",
          },
          {
            label: "依赖预检",
            skillName: "abaqus-dependency-preflight-validator",
            promptTemplate:
              "请帮我预检 Abaqus 脚本项目的依赖与标识符漂移：[描述项目结构]",
          },
          {
            label: "脚本调试",
            skillName: "abaqus-script-debugging-checklist",
            promptTemplate:
              "请帮我调试 Abaqus Python 脚本：[粘贴报错信息或描述问题]",
          },
          {
            label: "ODB 检查",
            skillName: "abaqus-odb",
            promptTemplate:
              "请帮我检查 Abaqus ODB 结果数据库：[描述步骤/帧/场输出]",
          },
          {
            label: "结果导出",
            skillName: "abaqus-export",
            promptTemplate:
              "请帮我规划 Abaqus 结果导出：[描述导出格式/目标/溯源]",
          },
        ],
      },
      {
        agentSlug: "fault-zeroing",
        label: "故障归零",
        chips: [
          {
            label: "故障归零",
            skillName: "fault-zeroing",
            promptTemplate: "请帮我进行以下故障的归零分析：[故障描述]",
          },
        ],
      },
      {
        agentSlug: "paper-review",
        label: "论文评审",
        chips: [
          {
            label: "论文评审",
            skillName: "academic-paper-review",
            promptTemplate: "请帮我评审以下学术论文：[上传 PDF 或粘贴内容]",
          },
        ],
      },
    ],
  },
];

export function getScenarioById(id: ScenarioId) {
  return SCENARIOS.find((s) => s.id === id);
}

export function getPillsByScenario(scenarioId: ScenarioId) {
  return getScenarioById(scenarioId)?.agentPills ?? [];
}

export function getChipsByPill(scenarioId: ScenarioId, agentSlug: string) {
  return (
    getPillsByScenario(scenarioId).find((p) => p.agentSlug === agentSlug)
      ?.chips ?? []
  );
}
