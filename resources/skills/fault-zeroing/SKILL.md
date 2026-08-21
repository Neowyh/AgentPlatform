---
name: fault-zeroing
description: 基于文件资料完成归零排故、故障树构建、底事件评估和生成归零报告
allowed-tools:
  - glob
  - grep
  - read_file
  - read_document
  - write_file
  - present_files
  - task
  - ask_clarification
---

# 归零排故工作流

## 工作目标

基于用户上传的问题描述、日志、试验记录、设计资料、历史案例和报告模板，完成故障树构建、底事件评估、根因归因、验证计划和 Markdown 归零报告的生成。

## 输入资料读取规则

1. 先确认顶事件、故障现象、发生条件、影响范围和已有资料清单。
2. 优先读取 `/mnt/user-data/uploads/`，其次读取 `/mnt/user-data/workspace/`。
3. 不确定文件位置时，先用 `glob` 获取目录结构，再用 `grep` 定位关键词。
4. 按文件格式选择读取方式：
   - `.doc` / `.docx` / `.pdf` / `.xls` / `.xlsx` / `.ppt` / `.pptx`：调用 `read_document` 工具转 Markdown 后读取（分段读取，遇截断标记用 `page_range` 或分段继续）。
   - `.md` / `.txt` / `.log` 等纯文本：直接用 `read_file` 读取。
5. 文档读取后检测空文本：PDF 转换结果被判定为扫描件（空白或无正文）时，回复 `FAILED: 资料无法解析，疑似扫描件，请提供电子版` 并停止，不得猜测内容。
6. 长文档按章节或行号范围读取，不一次性吞入无关内容。
7. 缺少关键输入时调用 `ask_clarification`，不得用假设替代资料。
8. 即使用户只给出一句“做归零排故分析”，也必须主动盘点上传目录并按本工作流执行，不要求用户补写详细 prompt。
9. 资料覆盖矩阵必须逐项检查五类资料：问题描述、设计约束、试验记录或日志、总结报告、历史或复核记录。缺失项必须同时写入报告“输入资料”和“遗留风险”。
10. `06_expected_analysis.md`、`*_expected_analysis.md` 等验收参考文件只可用于人工验收，不得作为底事件、根因或报告结论的证据来源。

## 证据处理规则

执行前读取 `references/evidence_rules.md`。每条关键结论必须包含 evidence id 或明确资料来源，来源至少包含文件路径；能定位行号时写明行号或章节名。把内容区分为事实、推断、假设、待验证项。证据台账是证据评估和报告结论的唯一 evidence id 来源；演绎建树不读取证据台账，证据提取与演绎建树的执行关系由 Workflow V2 图和节点文件访问策略控制。底事件、根因和报告结论不得引用证据台账之外的 evidence id。

## 故障树构建规则

1. 顶事件必须来自用户问题或资料原文。
2. 中间事件用于表达故障传播链、功能失效链或条件组合。
3. 底事件必须可验证，避免把笼统原因写成底事件。
4. 对每个底事件记录 `id`、`name`、`description`、`parent_ids`、`evidence_ids`、`probability`、`probability_basis`、`confidence`、`status`、`verification_suggestion`。
5. 证据不足时，`probability` 填 `null`，`confidence` 填 `low`，`status` 填 `to_verify`。
6. `fault_tree.json` 必须符合 `templates/fault_tree.schema.json`。不确定字段也要保留键名并填 `null`、空数组或“待验证”说明。
7. `verification_plan` 每项必须包含 `id`、`target_id`（引用其指向的底事件或根因 id）、`item`、`method`、`expected_result`、`status` 六个字段；`status` 枚举为 `pending` / `in_progress` / `passed` / `failed` / `blocked`（新验证项用 `pending`）。注意与底事件/根因的 `status` 枚举（`confirmed` / `rejected` / `to_verify` / `not_applicable`）区分，不要混用。

## 底事件评估规则

使用“证据强度 + 机理一致性 + 反证情况 + 复现实验情况”形成概率判断。没有行业统计、历史频次或专家打分表时，不得给出精确数值概率，只给出高/中/低倾向和置信度。

## 输出规则

输出文件写入 `/mnt/user-data/outputs/`：

1. `/mnt/user-data/outputs/fault_tree.json`
2. `/mnt/user-data/outputs/fault_tree.svg`
3. `/mnt/user-data/outputs/bottom_event_assessment.md`
4. `/mnt/user-data/outputs/analysis_process.svg`
5. `/mnt/user-data/outputs/zeroing_report.md`

`fault_tree.svg` 必须是静态 SVG 框图，展示顶事件、中间事件、底事件、逻辑门和底事件状态。`analysis_process.svg` 必须展示证据提取、故障树构建、底事件评估、根因归因、纠正措施、文档生产这条分析链路。SVG 只使用内联 `<svg>`、`<rect>`、`<line>`、`<text>` 等静态元素，不写脚本和外链资源。

写完后调用 `present_files` 展示五份文件。输出前必须自检：

1. 五份文件全部存在，缺一份即视为失败并补齐。
2. 报告包含问题概述、输入资料、故障现象、故障树分析、底事件评估、根因归因、验证计划、纠正措施、遗留风险和证据附录。
3. 根因结论至少引用一条 A/B 级证据；否则必须写“待验证”。
4. 数值概率必须有统计、历史频次或专家打分依据；没有依据时 `probability` 保持 `null`。
5. `zeroing_report.md` 的顶事件、主根因和待验证项必须与 `fault_tree.json` 一致。
6. 两个 SVG 均为静态内容，不包含脚本、外链、远程图片或动态交互代码。
7. 报告必须显式包含资料覆盖矩阵、证据台账摘要、待验证项和遗留风险。
8. 报告必须包含各阶段职责说明：演绎建树阶段不依赖证据台账；证据检漏只做添加不做删除；文档阶段不修改分析数据。
9. 写完五件套后提示用户可运行离线 validator：`python scripts/validate_fault_zeroing_outputs.py --outputs-dir /mnt/user-data/outputs`。
