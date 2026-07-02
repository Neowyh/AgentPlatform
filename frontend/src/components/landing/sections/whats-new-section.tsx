"use client";

import MagicBento, { type BentoCardProps } from "@/components/ui/magic-bento";
import { cn } from "@/lib/utils";

import { Section } from "../section";

const COLOR = "#0a0a0a";
const features: BentoCardProps[] = [
  {
    color: COLOR,
    label: "上下文工程",
    title: "长期记忆",
    description: "智能体持续学习你的偏好，让对话更连贯、更个性化",
  },
  {
    color: COLOR,
    label: "工作流引擎",
    title: "任务规划与编排",
    description: "基于 YAML 的可视化工作流，自动化多步骤复杂业务流程",
  },
  {
    color: COLOR,
    label: "可扩展",
    title: "技能与工具",
    description: "即插即用，自由组合内置工具，打造你想要的智能体",
  },

  {
    color: COLOR,
    label: "持久化",
    title: "沙箱与文件系统",
    description: "读、写、运行——就像一台真正的计算机",
  },
  {
    color: COLOR,
    label: "灵活",
    title: "多模型支持",
    description: "豆包、DeepSeek、OpenAI、Gemini 等主流模型",
  },
  {
    color: COLOR,
    label: "自由",
    title: "开源可控",
    description: "MIT 许可，完全自托管，数据隐私尽在掌握",
  },
];

export function WhatsNewSection({ className }: { className?: string }) {
  return (
    <Section
      className={cn("", className)}
      title="iDeer 2.0 新功能"
      subtitle="iDeer 正从 Deep Research 智能体进化为全栈超级智能体，新增工作流引擎、MCP 管理、RBAC 权限及离线部署等企业级能力"
    >
      <div className="flex w-full items-center justify-center">
        <MagicBento data={features} />
      </div>
    </Section>
  );
}
