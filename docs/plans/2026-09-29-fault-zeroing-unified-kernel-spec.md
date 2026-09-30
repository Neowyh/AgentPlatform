# 归零智能体「三入口一内核」统一执行内核 — Spec

- **date**: 2026-09-29
- **status**: ready-for-agent（本地 triage 标记；迁移 tracker 时映射为 `ready-for-agent` 标签）
- **source**: 会话《归零智能体 skill-agent-workflow 三级机制审查》→ grill-with-docs 需求澄清 → to-spec
- **tickets**: `.scratch/fault-zeroing-unified-kernel/issues/01..05`

## Problem Statement

用户从聊天（Skill / Expert）发起的归零分析与从工作流页面发起的正式 Run 走的是两套事实标准：聊天产出无任何机器验收，格式错误、证据缺口可以被静默带过；工作流入口虽有多重节点门禁，但最终完成判定不经过归零 Result Contract。设计文档承诺的「三入口共享执行内核、统一验收」在产品中并未兑现（内核包仅被测试与离线脚本引用），用户无法判断一份归零报告的可信等级，系统也不区分「已验收的完成」与「模型自称的完成」。

## Solution

三个入口（Skill、Expert、Workflow）的真实归零分析统一路由经 Fault-zeroing Execution Kernel：发起前经过 Hybrid Evidence Intake（缺侧暂停待确认、双缺拒绝），Run 快照钉扎 Result Contract 版本，完成后由同一契约判定——通过才算 Fault-zeroing Completion，未通过则 Run 终态 failed、违规清单入档、产物保留可查。

聊天中不再有「内联直出五件套」模式：答疑与有限编辑仍是普通对话，真实分析由 Agent 代用户发起正式 Run 并把产物送回会话。

缺侧判定以 CONTEXT.md 词典为准：非空问题描述或任一文档附件即满足文档侧，代码侧必须提供 Code Evidence Package，证据模式由系统派生而非用户声明。

## User Stories

1. As a 普通用户, I want 在聊天里用一句自然语言描述问题就能发起正式归零分析, so that 我不需要理解工作流概念也能得到经过验收的报告。
2. As a 普通用户, I want 聊天里的概念解释、方法答疑和报告措辞微调保持普通对话, so that 简单问题不会被强制走完整分析流程。
3. As a 普通用户, I want 只提供问题描述（无附件）也能发起分析, so that 文档侧不因「没有上传文件」被误判缺失。
4. As a 普通用户, I want 缺少代码证据包时系统用确认卡片问我「补传 / 缺侧继续 / 停止」, so that 我对证据缺口知情并做出选择。
5. As a 普通用户, I want 我确认后系统又发现新材料时要求我重新确认, so that 不会在我知情范围外扩大分析输入。
6. As a 普通用户, I want 两类证据都缺失时得到引导而不是一个失败的 Run, so that 我知道该准备什么材料。
7. As a 普通用户, I want 分析运行中看到 Run 进度入口, so that 我可以随时查看执行状态。
8. As a 普通用户, I want Run 完成后五件套产物自动送回聊天窗口, so that 我在对话里直接获取结果。
9. As a 普通用户, I want 未通过验收的 Run 仍然能查看产物和违规清单, so that 我可以修正材料后重新发起而不是从零排查。
10. As a 质量工程师, I want 从工作流页面发起归零时同样经过收件检查（缺侧暂停、双缺拒绝）, so that 正式流程的输入质量有统一保障。
11. As a 质量工程师, I want Run 完成前由 Result Contract 判定, so that 「已完成」代表机器验收通过而非文件存在。
12. As a 质量工程师, I want Run 详情页看到收件决定、契约版本与契约判定事件, so that 我能追溯每次分析的门禁记录。
13. As a 质量工程师, I want 补齐缺失证据后重新发起完整证据的 Run, so that 分析结论的证据等级可以随输入提升。
14. As a 审计人员, I want Run 记录标注发起入口（skill / expert / workflow）, so that 我能按入口统计与审计分析行为。
15. As a 审计人员, I want 确认操作记录确认人与确认时的输入快照哈希, so that 追责链条完整。
16. As a 平台开发者, I want 三个入口共享同一套 Intake / Contract 内核而入口只做演示适配, so that 修一处规则三个入口同时生效，不再发生枚举漂移。
17. As a 平台开发者, I want 引擎的契约门通过声明式校验器挂载, so that 其他工作流未来可以复用同一机制而引擎不知道归零业务。
18. As a 平台开发者, I want 离线校验脚本与运行时门共享同一契约实现, so that 不存在第二套校验标准。
19. As a 平台开发者, I want 废弃的非规范适配器与遗留子代理配置被移除, so that 不存在会被误改的第二套实现。
20. As a 部门管理员, I want 发起归零 Run 仍然经过资源可见性与使用授权校验, so that 内核收编不绕过既有 RBAC。
21. As a 归零领域专家, I want 充分披露 pending_verification 的报告可以合法完成, so that 「如实声明未验证」不被迫伪装成「已确认」。
22. As a 普通用户, I want 聊天技能说明不再承诺不存在的模式与工具, so that 我被引导的行为与系统真实能力一致。

## Implementation Decisions

- **引擎契约门（通用机制）**：Workflow 定义新增顶层可选声明「完成前 Result Contract 校验器」（模块:函数路径）。运行器在图执行成功后、终态写入前调用；违规 → 终态 failed + 违规摘要写入 Run 记录 + 五件套产物保留；校验器自身异常按 failed（fail-closed）；未声明的工作流行为不变。引擎对业务无知。
- **统一完成判定**：声明了契约门的归零工作流，完成判定统一经 Fault-zeroing Execution Kernel 的完成评估——契约通过/失败事件、pending_verification 语义、缺侧披露校验全部经内核事件日志留痕。
- **缺侧判定对齐词典**：文档侧 = 非空问题描述或任一文档附件；代码侧 = Code Evidence Package 存在；单缺 → paused + 确认；双缺 → 拒绝且不创建 Run；证据模式为派生结果，从用户可传输入中移除；上传目录变为可选输入；问题描述纳入输入快照哈希。
- **工作流入口收编**：声明契约门的工作流启动改经内核 canonical 创建路径（依赖闭包冻结 + 契约版本钉扎 + Intake 门），RBAC 校验保持既有网关链路不绕过。
- **聊天入口**：新增归零专用发起工具，仅注册给归零 Expert 闭包；发起前把声明的证据物化到 Run 工作区（复制，输入快照绑定物化结果，Run 自包含）；缺侧确认经澄清卡片完成并回传确认命令；产物回桥复制到线程 outputs 并经产物展示工具呈现；契约违规的 Run 回桥违规摘要与产物链接。
- **内联模式移除**：Skill 文本与 Agent 人格文本改写为二分规则（答疑/有限编辑 = 对话；真实分析 = 发起 Run），工作流节点模式条款保留；过时模块引用修正；离线校验脚本随 Skill 目录打包使指路可达。
- **收口清理**：移除非规范的工作流节点适配器实现与根配置中已废弃的自定义子代理声明。
- **文档**：词典增补「Invocation Adapter」词条；ADR-0004 修订（实现现状、内联移除、缺侧代码对齐、违规 failed 终态）。

### 决策记录（需求澄清产出）

1. **交付范围**：内核接线一个交付序列（合并后 5 工单）；工具库 P0（静态分析工具接线、GBK 编码、代码证据上下文中间件默认注册）另列并行切片。
2. **缺侧判定基准**：以 CONTEXT.md 词典为准改代码（冲突 1：intake 现实现只认路径，与词典「问题描述满足文档侧」冲突；冲突 2：词典 Avoid「Evidence Mode selection」，但网关保留用户可传 evidence_mode——两者均按词典修正）。
3. **契约违规终态**：failed + 违规清单入 Run 记录 + 产物保留，修正后重新发起。
4. **聊天内联模式**：彻底移除（词典「Fault-zeroing Execution Kernel」Avoid prompt-only orchestration，既有定）。
5. **工程锁定**：证据物化 = 复制进 Run 工作区；v1 归零专用发起工具（通用「聊天→任意工作流」互操作留后续）；内核保持归零专用、引擎契约门才是通用机制。

## Testing Decisions

- 只测外部行为：终态、违规清单、披露语义、事件记录；不测内部调用顺序。
- 接缝方案（经确认）：

| # | 接缝 | 现状 | 覆盖内容 |
|---|---|---|---|
| S1 | 内核存储接缝：内核发起/确认/完成评估 × 真实工作流存储（SQLite） | 现有 | Intake 三态、确认与快照哈希绑定、契约判定与事件 |
| S2 | Worker 运行时接缝：run_once 驱动真实图（agent 节点打桩） | 现有 | 契约门 failed 终态、违规摘要、产物保留、未声明工作流不受影响 |
| S3 | 网关 API 接缝：工作流启动路由 + 聊天 run 准备物化 | 现有 | canonical 路由、双缺 4xx、移除 evidence_mode 后的入参契约 |
| S4 | 工具边界接缝：发起工具协程直调 + 真实 intake + 内核桩 | **唯一新接缝** | 发起、缺侧确认回桥、完成/违规产物回桥 |

- 三入口等价性验收不新增接缝：复用 S1+S2，同一证据走三个入口驱动同一套存储与运行器，断言收件决定、契约版本、契约判定、产物集合四项一致。
- 先例：现有 worker 运行时集成测试、契约单元测试、网关契约测试、内核假存储单测。
- 验收门：后端标准 lane + pr-standard（Agent/Skill/Workflow 变更强制）；报告各子 lane 汇总与 TEST_LANE_DURATION。

## Out of Scope

- 工具库 P0 并行切片：静态分析工具接线、GBK 编码实现、代码证据上下文中间件默认注册（另列工单）。
- 通用「聊天 → 任意工作流」互操作。
- 契约违规自动自修复回路（违规回注重验节点）。
- 前端专家会话 slash 技能面板恢复（preferred_skill 死路径处理）。
- P2 能力项：数据工具注册、OCR、Python 静态分析、二进制证据策略等。

## Further Notes

- 行为变化需在发布说明标注：聊天不再内联产出五件套，真实分析一律发起正式 Run——慢一点，但结论可信、可查、可追责。
- 真实模型验收仍由 eval 用例承担；现有三案例不含代码包，工具库并行切片将补充带 C 代码包案例。
- 工单位于 `.scratch/fault-zeroing-unified-kernel/issues/`（会话临时区，不入 git），迁移 tracker 时按依赖序建 issue 并映射阻塞边。
