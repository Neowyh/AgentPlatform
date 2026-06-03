# 归零排故智能体可行性与实现路径（代码探索版）

## 1. 结论

基于当前 iDeer 框架搭建归零排故智能体可行。更准确地说，当前框架已经具备“可配置智能体 + Skill 行为固化 + 文件资料读取 + 工具调用 + 子智能体委托 + 报告产物输出”的主体闭环；需要新增的是归零排故领域层能力，包括故障树结构化数据、底事件评估工具、报告模板渲染、证据链管理、知识库接入和流程状态管理。

建议第一阶段不要改造框架内核，而是先采用“custom agent + custom skill + custom subagents + 文件型资料包”的方式完成 PoC。等归零流程稳定后，再补结构化知识库、故障树数据模型和评审闭环。

## 2. 代码探索依据

| 能力 | 当前实现 | 结论 |
| --- | --- | --- |
| 自定义智能体 | `backend/packages/harness/ideer/config/agents_config.py` 定义 `AgentConfig`，支持 `name`、`description`、`model`、`tool_groups`、`skills`；`SOUL.md` 通过 `load_agent_soul()` 读取 | 可直接用来定义“归零排故智能体”的身份、行为边界、模型和技能白名单 |
| 智能体管理 API | `backend/app/gateway/routers/agents.py` 提供 `/api/agents` CRUD；创建时写入 `config.yaml` 和 `SOUL.md` | 可作为配置入口，但默认受 `agents_api.enabled` 控制，生产启用前要加权限边界 |
| 运行时加载 | `backend/packages/harness/ideer/agents/lead_agent/agent.py` 的 `_make_lead_agent()` 读取 `agent_name`、加载 agent config、选择模型、限制 skill、装配工具和中间件 | 归零智能体可以作为现有 lead agent 的一个配置实例运行 |
| Skill | `SkillStorage.load_skills()` 扫描 `skills/public` 与 `skills/custom`，按 `extensions_config.json` 合并启用状态；`parse_skill_file()` 解析 frontmatter 和 `allowed-tools` | 归零流程、故障树构建规则、报告模板说明可以先用 Skill 固化 |
| 文件资料访问 | `UploadsMiddleware` 将上传文件、Markdown 提纲、路径注入对话；sandbox 提供 `glob`、`grep`、`read_file`、`write_file`、`str_replace` | 支持按需读取用户上传资料、日志、试验记录和模板文件 |
| 路径与安全 | `validate_local_tool_path()` 限制本地沙箱访问 `/mnt/user-data`、`/mnt/skills`、`/mnt/acp-workspace` 和配置挂载；写入 skill 路径默认禁止 | 适合处理项目资料，但企业知识库/共享目录需要通过 mount 或 MCP 明确配置 |
| 子智能体 | `subagents_config.py` 支持 `custom_agents`，可配置 `system_prompt`、工具白名单、skill 白名单、模型、超时；`task_tool` 负责委托执行 | 可拆出日志分析、资料检索、概率评估、报告审查等专业子智能体 |
| 报告产物 | `write_file` 写入 `/mnt/user-data/outputs`；`present_files` 仅允许展示 outputs 下文件 | 可生成 Markdown/HTML/JSON 归零报告并在前端展示/下载 |
| 记忆 | `FileMemoryStorage` 使用 JSON 保存用户/agent 记忆、facts 和历史摘要 | 可记录偏好和少量经验事实，但不是正式知识库 |
| MCP | `mcp/client.py` 支持 stdio、SSE、HTTP MCP server 参数构建 | 可外接企业知识库、缺陷系统、日志平台、PLM，但当前没有内置知识库实现 |

## 3. 对四项需求的可行性判断

### 3.1 使用 Skill 配置智能体功能与行为

可行，且应作为第一阶段主路径。

实现方式：
- 创建归零排故 custom agent，例如 `fault-zeroing`。
- 在 agent 的 `config.yaml` 中限制 `skills` 和 `tool_groups`。
- 创建 `skills/custom/fault-zeroing/SKILL.md`，固化：
  - 归零排故角色边界；
  - 信息补全问题清单；
  - 故障树构建步骤；
  - 底事件评估规则；
  - 证据引用规范；
  - 报告生成规则。
- 如需把工具权限压到 skill 层，可在 `SKILL.md` frontmatter 使用 `allowed-tools`。

需要注意：Skill 更适合固化“方法、流程、模板、规则”，不适合存放大量历史文档。大量知识资料应走上传文件、挂载目录、MCP 或后续知识库。

### 3.2 按需访问文件系统与知识库，完成故障树构建

文件系统部分可行；知识库部分当前只有接入框架，没有内置知识库。

当前可直接使用：
- 上传资料进入 `/mnt/user-data/uploads`；
- 工作区文件放在 `/mnt/user-data/workspace`；
- 输出文件写入 `/mnt/user-data/outputs`；
- 用 `glob` 找资料，用 `grep` 搜关键词，用 `read_file` 按行读取。

当前缺口：
- 没有故障案例库 schema；
- 没有向量检索或 RAG；
- 没有知识条目版本、权限、引用溯源；
- 没有“故障树”结构化存储格式。

建议第一阶段采用文件型知识源：用户上传问题描述、日志、试验记录、规范和历史案例，智能体输出 `fault_tree.json` 与 `fault_tree.md`。第二阶段再新增结构化知识库或 MCP 知识库工具。

### 3.3 根据底事件执行工具调用、任务编排和子智能体分工

可行，但要补归零领域的编排规范。

当前框架已经有 `task` 工具和 custom subagents。建议定义以下子智能体：
- `evidence-reader`：读取资料、抽取证据、输出证据引用。
- `fault-tree-builder`：构建顶事件、中间事件、底事件和逻辑关系。
- `probability-assessor`：按证据、历史频次、专家规则或测试结果评估底事件概率。
- `root-cause-analyst`：综合概率、证据强度和验证结果做归因。
- `report-reviewer`：检查报告完整性、证据引用、结论闭环。

第一阶段可以让主智能体通过 prompt 约束完成编排；如果需要稳定性，应新增一个轻量工具 `fault_tree_tool`，专门读写和校验故障树 JSON，避免全靠自然语言维护结构。

### 3.4 根据报告模板生成归零报告文件

可行。

当前 `write_file` 可写报告到 `/mnt/user-data/outputs`，`present_files` 可将报告暴露给前端。建议 Skill 中放模板，或在 `skills/custom/fault-zeroing/templates/` 放：
- `fault_zeroing_report.md`
- `fault_tree.schema.json`
- `bottom_event_assessment.schema.json`
- `evidence_table.md`

第一阶段生成 Markdown 报告即可；第二阶段可增加 HTML 渲染；第三阶段再考虑 Word/PDF 导出。

## 4. 推荐实现方案

### 阶段一：配置型 PoC

目标：不改框架核心，验证完整归零闭环。

工作内容：
1. 创建 `fault-zeroing` custom agent。
2. 创建 `fault-zeroing` skill，固化归零排故流程。
3. 在 `config.yaml` 中定义 3-5 个 custom subagents。
4. 准备报告模板和故障树 JSON 模板。
5. 通过上传资料 + 对话触发，生成：
   - `fault_tree.json`
   - `bottom_event_assessment.md`
   - `zeroing_report.md`
6. 用 `present_files` 展示报告。

交付标准：
- 给定一组样例材料，可以完成“故障现象 → 故障树 → 底事件评估 → 归因结论 → 归零报告”的闭环。
- 报告中每个关键结论都有证据来源或“待验证”标记。
- 子智能体分工能稳定执行，不出现无限委托或工具越权。

### 阶段二：结构化业务层

目标：把 PoC 从对话能力升级为可复用业务流程。

工作内容：
1. 新增故障树数据模型和校验工具。
2. 新增底事件概率评估工具，统一概率、置信度、证据等级、验证状态。
3. 新增任务实例模型，记录问题状态、附件、报告版本、工具调用摘要。
4. 新增报告模板渲染服务。
5. 新增历史案例检索接口：先从文件/SQLite 做起，再接企业知识库。

交付标准：
- 故障树和报告不是纯自然语言，而是有可校验 JSON。
- 每次分析有任务实例和版本记录。
- 报告可复现：能追溯到输入材料、工具调用和子智能体结论。

### 阶段三：生产级集成

目标：接入企业系统，形成可审计、可协作、可治理的归零平台能力。

工作内容：
1. 接入 PLM、缺陷系统、测试平台、代码仓、日志平台。
2. 构建正式知识库：结构化案例库 + 文档检索 + 权限过滤。
3. 增加审批、评审、签核、关闭流程。
4. 增加工具调用审计、敏感信息脱敏、模型调用留痕。
5. 建立评测集，评估流程完整率、证据引用率、结论准确率、报告合规率。

## 5. 待办工作清单

### P0：PoC 必做

- 编写 `fault-zeroing` agent 的 `SOUL.md`。
- 编写 `fault-zeroing` skill。
- 增加归零报告 Markdown 模板。
- 增加故障树 JSON 模板。
- 配置 custom subagents。
- 准备 2-3 个样例故障材料包。
- 跑通文件读取、故障树构建、底事件评估、报告输出。
- 形成 PoC 验证记录。

### P1：MVP 必做

- 实现故障树 JSON schema 校验。
- 实现底事件评估结果 schema。
- 实现报告模板渲染工具。
- 增加任务实例和报告版本记录。
- 增加证据引用表。
- 增加历史案例检索的最小实现。
- 增加回归测试和端到端样例。

### P2：生产增强

- 接入企业知识库或 RAG/MCP 检索。
- 接入日志、缺陷、测试、代码等外部系统。
- 增加项目/角色权限。
- 增加工具调用审计和敏感操作审批。
- 增加评审闭环。
- 增加质量评测集和指标看板。

## 6. 当前最大风险

1. **知识库不是现成能力**：当前只有 Memory、Skill、Uploads 和 MCP 接入通道，没有内置 RAG/向量库。
2. **故障树需要结构化约束**：如果只依赖 prompt，复杂故障树容易出现字段漂移和前后矛盾。
3. **概率评估需要领域规则**：底事件概率不能只靠模型猜测，需要明确证据等级、历史频次、试验结果和专家规则。
4. **企业系统接入成本不可忽略**：PLM、缺陷、日志、试验平台的数据权限和接口适配会决定 MVP 复杂度。
5. **报告合规性需要模板和校验**：正式归零报告必须有固定章节、证据引用、验证闭环和人工评审机制。

## 7. 建议下一步

先做阶段一 PoC。不要先建设完整知识库和专用前端页面。第一版重点是验证当前 iDeer 框架能否稳定完成：

`上传材料 -> 读取证据 -> 构建故障树 -> 底事件评估 -> 子智能体归因 -> 生成归零报告`

PoC 成功后，再把故障树、概率评估、任务实例、报告模板和知识库沉淀为正式业务模块。
