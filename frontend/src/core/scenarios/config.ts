import type { ScenarioId, ScenarioTab } from "./types";

export const SCENARIOS: ScenarioTab[] = [
  {
    id: "daily",
    labelKey: "scenarios.daily",
    icon: "Briefcase",
    agentPills: [
      {
        agentSlug: "office-docs",
        label: "文档处理",
        chips: [
          {
            label: "Word 创建编辑",
            skillName: "anthropic-docx",
            promptTemplate: "请帮我处理以下文档：[描述需求]",
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
        agentSlug: "gongwen",
        label: "公文写作",
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
        ],
      },
      {
        agentSlug: "translation",
        label: "翻译校对",
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
    ],
  },
  {
    id: "creative",
    labelKey: "scenarios.creative",
    icon: "Palette",
    agentPills: [
      {
        agentSlug: "ppt-web",
        label: "网页 PPT",
        chips: [
          {
            label: "网页 PPT",
            skillName: "guizang-ppt-skill",
            promptTemplate: "请帮我制作以下主题的网页 PPT：[主题]",
          },
        ],
      },
      {
        agentSlug: "slide-deck",
        label: "演示文稿",
        chips: [
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
        agentSlug: "srs-writing",
        label: "需求规格",
        chips: [
          {
            label: "SRS 撰写",
            skillName: "srs-writing",
            promptTemplate:
              "请帮我撰写以下项目的软件需求规格说明：[项目名称/背景]",
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
      {
        agentSlug: "longform-writing",
        label: "长文撰写",
        chips: [
          {
            label: "报告撰写",
            skillName: "structured-longform-writing",
            promptTemplate:
              "请帮我撰写以下结构化长文：[主题/类型]，要求：[具体要求]",
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
