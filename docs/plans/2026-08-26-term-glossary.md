# 小白友好术语对照表（第三期）

- 日期：2026-08-26
- 范围：仅 UI 文案层（i18n），不动后端模型、API、路由标识
- 原则：用户语言只用日常词；专有名词（产品名/协议名）保留；调试向功能文案保持精确性

## 已执行的重命名（2026-08-26）

| 位置 | 原文案 | 新文案 | 理由 |
|------|--------|--------|------|
| agents.description (zh) | 创建和管理具有专属 Prompt 与能力的自定义智能体 | 创建和管理你的专属智能体，为它设定职责和能力。 | 去中英混排术语 |
| agents.description (en) | …with specialized prompts and capabilities | …with dedicated responsibilities and capabilities | 同上 |
| workflows.description (zh) | 管理和运行工作流定义 | 把固定流程交给 iDeer 自动执行，适合可重复的任务。 | "定义"为系统视角黑话 |
| workflows.description (en) | Manage and run your workflow definitions | Automate repeatable, step-by-step tasks with iDeer. | 同上 |
| workflows.emptyDescription (zh/en) | 创建你的第一个工作流以开始使用 | 创建你的第一个工作流，让重复性任务自动跑起来。 | 首现场景化解释 |
| workflows.runId (zh) | 运行 ID： | 运行编号： | 去英文混排 |
| workflows.tokenStream (zh) | Token 流 | 生成过程 | 面向小白的节点详情 |
| workflows.actionOutput (zh) | Action 输出 | 执行输出 | 去英文混排 |
| tokenUsage.unavailable (zh/en) | …供应商提供 usage_metadata 时才会显示 | 模型成功回复后才会显示 | 去实现细节字段名 |
| tokenUsage.note (zh/en) | 后端持久化的线程用量；流式返回… | 以后端保存的数据为准；回复还在生成时… | 去持久化/流式黑话 |

## 审视后保留的术语

| 术语 | 保留理由 |
|------|----------|
| 对话（thread）、智能体（agent）、工作流（workflow）、运行（run） | 此前版本已人话化，本次确认无需再改 |
| MCP / MCP 服务器 | 协议专名，设置页受众本身是进阶用户 |
| YAML 定义 | 编辑工作流定义的受众需要准确名称 |
| SOUL.md / skill-creator | 产品内专有名词，重命名会破坏与文档/对话指令的一致性 |
| Token 用量（设置区标题、presets.debug 等） | 用量统计面向关注成本的用户，"Token"是行业通用词且与账单对应 |
| 调试（debug preset） | 功能本身就是调试用途，改名反而失真 |

## 后续候选（本期不做）

- 工作流运行详情页的"事件时间线""定义版本"等半技术词，待收到真实小白反馈后再定
