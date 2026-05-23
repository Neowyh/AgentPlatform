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

# 归零排故工作流

## 工作目标

基于用户上传的问题描述、日志、试验记录、设计资料、历史案例和报告模板，完成故障树构建、底事件评估、根因归因、验证计划和 Markdown 归零报告生成。

## 输入资料读取规则

1. 先确认顶事件、故障现象、发生条件、影响范围和已有资料清单。
2. 优先读取 `/mnt/user-data/uploads/`，其次读取 `/mnt/user-data/workspace/`。
3. 不确定文件位置时，先用 `glob` 获取目录结构，再用 `grep` 定位关键词。
4. 长文档按章节或行号范围读取，不一次性吞入无关内容。
5. 缺少关键输入时调用 `ask_clarification`，不得用假设替代资料。
6. 即使用户只给出一句“做归零排故分析”，也必须主动盘点上传目录并按本工作流执行，不要求用户补写详细 prompt。
7. 资料覆盖至少检查问题描述、设计方案或接口约束、试验大纲或试验记录、总结报告或复现记录、试验数据或日志、历史/复核记录。缺失项必须写入报告“输入资料”和“遗留风险”。

## 证据处理规则

执行前读取 `references/evidence_rules.md`。每条关键结论必须包含证据来源，来源至少包含文件路径；能定位行号时写明行号或章节名。把内容区分为事实、推断、假设、待验证项。

## 故障树构建规则

1. 顶事件必须来自用户问题或资料原文。
2. 中间事件用于表达故障传播链、功能失效链或条件组合。
3. 底事件必须可验证，避免把笼统原因写成底事件。
4. 对每个底事件记录 `id`、`name`、`description`、`parent_ids`、`evidence`、`probability`、`probability_basis`、`confidence`、`status`、`verification_suggestion`。
5. 证据不足时，`probability` 填 `null`，`confidence` 填 `low`，`status` 填 `to_verify`。
6. `fault_tree.json` 必须符合 `templates/fault_tree.schema.json`。不确定字段也要保留键名并填 `null`、空数组或“待验证”说明。

## 底事件评估规则

使用“证据强度 + 机理一致性 + 反证情况 + 复现实验情况”形成概率判断。没有行业统计、历史频次或专家打分表时，不得给出精确数值概率，只给出高/中/低倾向和置信度。

## 子智能体协作规则

复杂资料包必须优先委托子智能体，但最多只进行一轮核心委托。收到子智能体结果后，主智能体必须进入产物生成和自检，不得反复委托导致不产出。

1. `evidence-reader`：抽取关键证据和来源。
2. `fault-tree-builder`：构建故障树草案。
3. `probability-assessor`：评估底事件概率、置信度和验证状态。
4. `root-cause-analyst`：形成根因归因和验证建议。
5. `report-reviewer`：检查章节完整性、证据闭环和待验证项。

子智能体失败时，记录失败原因，再由主智能体直接读取资料完成降级分析。

## 输出规则

输出文件写入 `/mnt/user-data/outputs/`：

1. `/mnt/user-data/outputs/fault_tree.json`
2. `/mnt/user-data/outputs/fault_tree.svg`
3. `/mnt/user-data/outputs/bottom_event_assessment.md`
4. `/mnt/user-data/outputs/analysis_process.svg`
5. `/mnt/user-data/outputs/zeroing_report.md`

`fault_tree.svg` 必须是静态 SVG 框图，展示顶事件、中间事件、底事件、逻辑门和底事件状态。`analysis_process.svg` 必须展示证据读取、故障树构建、底事件评估、根因归因、报告审查这条分析链路。SVG 只使用内联 `<svg>`、`<rect>`、`<line>`、`<text>` 等静态元素，不写脚本和外链资源。

写完后调用 `present_files` 展示五份文件。输出前必须自检：

1. 五份文件全部存在，缺一份即视为失败并补齐。
2. 报告包含问题概述、输入资料、故障现象、故障树分析、底事件评估、根因归因、验证计划、纠正措施、遗留风险和证据附录。
3. 根因结论至少引用一条 A/B 级证据；否则必须写“待验证”。
4. 数值概率必须有统计、历史频次或专家打分依据；没有依据时 `probability` 保持 `null`。
5. `zeroing_report.md` 的顶事件、主根因和待验证项必须与 `fault_tree.json` 一致。
6. 两个 SVG 均为静态内容，不包含脚本、外链、远程图片或动态交互代码。
