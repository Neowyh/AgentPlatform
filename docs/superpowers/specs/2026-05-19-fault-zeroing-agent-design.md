# 归零排故智能体 PoC 设计

## 背景

当前目标是在 DeerFlow 框架上搭建一个归零排故智能体，先验证归零分析闭环，不在第一版建设正式知识库、专用业务页面或生产级审批流程。

第一版采用文件型知识源：用户上传问题描述、日志、试验记录、设计文档、历史案例和报告模板，智能体按需读取文件并完成故障树构建、底事件评估、归因分析和 Markdown 归零报告生成。

## 设计结论

PoC 不改 DeerFlow 核心运行时，优先复用现有能力：

- custom agent：定义 `fault-zeroing` 智能体身份、模型、工具组和 Skill 白名单。
- Skill：固化归零排故流程、故障树构建规则、底事件评估口径和报告生成要求。
- uploads/workspace：作为第一版知识输入来源。
- sandbox tools：使用 `glob`、`grep`、`read_file`、`write_file` 按需访问资料和生成产物。
- custom subagents：拆分资料读取、故障树构建、概率评估、归因分析和报告审查。
- artifacts：将最终报告和中间结构化结果写入 `/mnt/user-data/outputs` 并通过 `present_files` 展示。

## 范围

### PoC 包含

- 创建 `fault-zeroing` custom agent。
- 创建 `fault-zeroing` Skill。
- 配置归零排故子智能体。
- 使用上传文件和工作区文件作为知识源。
- 生成故障树、底事件评估和归零报告。
- 报告格式先采用 Markdown。
- 输出中间产物，便于人工检查。

### PoC 不包含

- 不建设正式 RAG 或向量知识库。
- 不新增归零排故专用前端页面。
- 不接入 PLM、缺陷系统、测试平台、日志平台等企业系统。
- 不实现生产级审批、签核、权限和审计闭环。
- 不生成 Word/PDF，后续可扩展。

## 组件设计

### 1. fault-zeroing Custom Agent

目录由现有 custom agent 机制管理，运行时通过 `agent_name=fault-zeroing` 加载。

`config.yaml` 建议内容：

```yaml
name: fault-zeroing
description: 归零排故智能体，用于基于资料证据构建故障树、评估底事件并生成归零报告
tool_groups:
  - file:read
  - file:write
  - web
skills:
  - fault-zeroing
```

`SOUL.md` 负责约束智能体行为：

- 必须先读取用户输入和上传资料。
- 不得凭空给出底事件概率。
- 结论必须绑定证据来源；证据不足时标记“待验证”。
- 需要区分事实、推断、假设和验证建议。
- 输出报告前必须检查章节完整性和证据闭环。

### 2. fault-zeroing Skill

Skill 位于 `skills/custom/fault-zeroing/SKILL.md`，用于配置功能与行为。

建议结构：

```markdown
---
name: fault-zeroing
description: 基于文件资料完成归零排故、故障树构建、底事件评估和归零报告生成
allowed-tools:
  - glob
  - grep
  - read_file
  - write_file
  - present_files
  - task
  - ask_clarification
---

## 工作目标
...

## 输入资料读取规则
...

## 故障树构建规则
...

## 底事件评估规则
...

## 归因分析规则
...

## 报告生成规则
...
```

Skill 支持文件建议：

- `templates/zeroing_report.md`：Markdown 报告模板。
- `templates/fault_tree.json`：故障树 JSON 模板。
- `templates/bottom_event_assessment.md`：底事件评估表模板。
- `references/evidence_rules.md`：证据等级和引用规范。

### 3. 子智能体配置

通过 `config.yaml` 的 `subagents.custom_agents` 配置。第一版建议 5 类：

| 子智能体 | 职责 | 推荐工具 |
| --- | --- | --- |
| `evidence-reader` | 读取资料、抽取关键证据、标注文件和行号 | `glob`、`grep`、`read_file` |
| `fault-tree-builder` | 根据顶事件和证据构建故障树 | `read_file`、`write_file` |
| `probability-assessor` | 评估底事件概率、置信度和证据等级 | `read_file`、`write_file` |
| `root-cause-analyst` | 综合底事件概率和证据强度形成归因 | `read_file`、`write_file` |
| `report-reviewer` | 检查报告章节、证据引用和待验证项 | `read_file`、`write_file` |

子智能体默认不再嵌套调用 `task`，避免递归委托。

### 4. 输入资料组织

PoC 采用文件型知识源。

推荐目录约定：

```text
/mnt/user-data/uploads/
  problem_statement.md
  logs/
  test_records/
  design_docs/
  historical_cases/

/mnt/user-data/workspace/
  working_notes.md

/mnt/user-data/outputs/
  fault_tree.json
  bottom_event_assessment.md
  zeroing_report.md
```

智能体读取规则：

- 优先读取用户上传资料和目录提纲。
- 不确定资料位置时先用 `glob` 和 `grep` 定位。
- 对长文档按行号范围读取，避免一次性读入过多内容。
- 资料不足时通过 `ask_clarification` 追问。

### 5. 输出产物

PoC 输出 3 个核心文件：

`fault_tree.json`：

```json
{
  "top_event": "",
  "intermediate_events": [],
  "bottom_events": [
    {
      "id": "",
      "name": "",
      "description": "",
      "evidence": [],
      "probability": null,
      "confidence": "low",
      "status": "to_verify"
    }
  ],
  "logic": []
}
```

`bottom_event_assessment.md`：

```markdown
| 底事件 | 证据 | 概率判断 | 置信度 | 验证状态 | 后续动作 |
| --- | --- | --- | --- | --- | --- |
```

`zeroing_report.md`：

```markdown
# 归零报告

## 1. 问题概述
## 2. 输入资料
## 3. 故障现象
## 4. 故障树分析
## 5. 底事件概率评估
## 6. 根因归因
## 7. 验证计划与结果
## 8. 纠正措施
## 9. 遗留风险
## 10. 附录：证据引用
```

## 工作流

1. 用户上传资料并描述问题。
2. 主智能体检查资料完整性，必要时追问。
3. 主智能体调用 `evidence-reader` 抽取证据。
4. 主智能体调用 `fault-tree-builder` 生成故障树。
5. 主智能体调用 `probability-assessor` 评估底事件。
6. 主智能体调用 `root-cause-analyst` 形成归因结论。
7. 主智能体生成 `zeroing_report.md`。
8. 主智能体调用 `report-reviewer` 做完整性检查。
9. 主智能体修订报告并调用 `present_files` 展示产物。

## 错误处理

- 缺少关键输入：使用 `ask_clarification` 追问，不直接补全。
- 找不到文件：列出已发现文件和期望文件，不伪造证据。
- 证据冲突：保留冲突项，标记冲突来源和需要验证的假设。
- 概率依据不足：概率字段可为空，置信度标为 `low`，状态标为 `to_verify`。
- 子智能体失败：主智能体记录失败原因，必要时用直接工具读取资料完成降级分析。

## 验收标准

PoC 至少通过 2-3 个样例故障资料包验证。

通过标准：

- 能生成 `fault_tree.json`、`bottom_event_assessment.md`、`zeroing_report.md`。
- 报告关键结论有证据来源。
- 证据不足的结论明确标记“待验证”。
- 子智能体分工清晰，中间结果可检查。
- 最终 Markdown 报告可通过前端 artifact 查看或下载。

## 待办工作

### P0：PoC 必做

- 创建 `fault-zeroing` agent 配置。
- 编写 `fault-zeroing` 的 `SOUL.md`。
- 创建 `skills/custom/fault-zeroing/SKILL.md`。
- 编写 Markdown 报告模板。
- 编写故障树 JSON 模板。
- 编写底事件评估表模板。
- 配置 5 类 custom subagents。
- 准备 2-3 个样例故障资料包。
- 跑通端到端闭环。
- 记录 PoC 验证结果和主要问题。

### P1：MVP 增强

- 新增故障树 JSON schema 校验工具。
- 新增底事件评估 schema。
- 新增报告模板渲染工具。
- 增加证据引用表。
- 增加报告版本记录。
- 增加历史案例检索的最小实现。
- 增加端到端样例测试。

## 开放问题

- 样例故障资料包由谁提供，是否包含真实日志和测试记录。
- 底事件概率是否有既定行业规则、历史统计数据或专家打分表。
- PoC 是否需要支持多模态资料，例如图片、截图、波形图。
- 报告模板是否已有公司标准版本。
