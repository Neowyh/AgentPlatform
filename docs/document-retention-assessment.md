# 项目文档留存必要性评估

> 评估日期：2026-07-15
> 评估范围：项目内普通文档与文档型资产；明确排除所有路径段中的 `skills/**`、其专用模板与引用资料，以及依赖包第三方文档。
> 当前结论：本报告只提出留存、更新、合并和归档建议，不删除原文件。

## 1. 结论摘要

> 2026-07-15 迁移状态：本报告提出的首批测试、权限、离线、优化和决策材料已完成物理迁移；当前入口以 `docs/README.md`、`docs/backlog.md`、`docs/testing/` 和 `docs/archive/2026/README.md` 为准。本文中的旧路径仅作为历史盘点记录，不是可点击入口。

本次盘点得到 263 个纳入评估的文档型文件。原始统计还包含 Skill 目录文件和依赖目录中的第三方文档，均不计入本报告。

总体不建议“大清理”。当前问题不是文档全部无用，而是四类内容混放：

1. 面向用户和开发者的当前参考文档；
2. 可执行的测试、权限和产品线治理文档；
3. 已完成工作的计划、审计、差距分析和变更报告；
4. 归零智能体的配置、案例、评测和验证证据。

建议采用“保留权威文档、归档历史证据、合并重复计划、更新状态文档”的策略。未经代码或引用关系核验，不建议直接删除任何文档。

## 2. 处置等级

| 等级 | 含义 | 处理原则 |
| --- | --- | --- |
| A 保留并作为权威 | 当前仍被使用，或承担安全、部署、测试、权限、合规职责 | 保留；变更代码时同步维护 |
| B 保留但需更新 | 有长期价值，但状态、路径、版本或内容已落后 | 保留文件，补充更新时间和权威性说明 |
| C 合并 | 与同主题文档重复，内容可以收敛 | 指定一个权威文件，其余转为历史链接或合并后归档 |
| D 归档 | 计划已结束、审计已完成、事故已关闭，但仍有追溯价值 | 移入对应 `archive/`，保留来源和结论 |
| E 删除候选 | 无独立事实、无引用、无审计价值，且内容已完全被权威文档覆盖 | 二次确认后再删除；本轮不执行 |

## 3. 按目录评估

### 3.1 根目录与组件旁文档：A 为主，B 少量

| 文件族 | 建议 | 理由 |
| --- | --- | --- |
| `README.md`、`README_zh.md`、`README_ja.md`、`README_fr.md`、`README_ru.md` | A | 项目入口和多语言发布说明；保留，后续需保证链接和版本描述一致 |
| `AGENTS.md`、`CLAUDE.md`、`backend/AGENTS.md`、`backend/CLAUDE.md`、`frontend/AGENTS.md`、`frontend/CLAUDE.md` | A | 代码协作和目录级约束，属于执行规则，不是普通说明文档 |
| `CONTRIBUTING.md`、`backend/CONTRIBUTING.md`、`CODE_OF_CONDUCT.md`、`SECURITY.md`、`Install.md` | A | 社区、安装和安全入口，不能因低频使用归档 |
| `TEST_PLAN.md`、`TEST_COVERAGE_ADVERSARIAL_REVIEW.md`、`B7_REMAINING_FAILURES.md` | B/D | 当前包含测试现状和遗留问题，但状态高度易过期；保留证据，完成后移入测试归档，不作为日常权威入口 |
| `findings.md`、`progress.md`、`task.md` | A（内部） | 当前测试治理的阶段状态和验收依据；标记为内部工作记录，不能与公开产品文档混用 |
| `backend/README.md`、`frontend/README.md`、`docker/provisioner/README.md`、`scripts/README-intranet.md` | A | 组件级启动、配置和运维入口；分别维护，不建议合并成单一超长 README |
| `backend/packages/**/README.md`、`backend/tests/factories/README.md`、`workflows/README.md` | A | 代码旁的局部使用说明，跟随组件保留 |
| `frontend/public/demo/**` 下的研究输出、示例文本 | E/单独管理 | 它们是演示数据，不是项目知识文档；只有被 demo 或测试引用的文件才保留，其余应从文档盘点中剥离 |

### 3.2 `backend/docs`：A、B 并存，计划类需要收敛

建议保留为后端权威参考的文件：

- `README.md`、`API.md`、`CONFIGURATION.md`、`SETUP.md`、`ARCHITECTURE.md`、`ARCHITECTURE_zh.md`；
- `AUTH_DESIGN.md`、`AUTH_UPGRADE.md`、`MCP_SERVER.md`、`STREAMING.md`、`FILE_UPLOAD.md`、`GUARDRAILS.md`；
- `middleware-execution-flow.md`、`PATH_EXAMPLES.md`、`summarization.md`、`plan_mode_usage.md`、`APPLE_CONTAINER.md`；
- `MEMORY_SETTINGS_REVIEW.md` 及仍被 README 或学习路线引用的记忆相关说明；
- `packages/**/README.md` 和测试工厂 README。

需要更新或合并的文件族：

| 文件族 | 建议 |
| --- | --- |
| `BACKEND_IMPROVEMENTS.md`、`engineering-backlog.md`、`TODO.md` | C/B：合并为一份带状态、负责人和更新时间的后端 backlog；已完成条目移至变更记录 |
| `AUTH_TEST_PLAN.md`、`AUTH_TEST_DOCKER_GAP.md` | B/D：保留安全验证证据；若已由当前测试矩阵覆盖，则归档旧计划 |
| `AUTO_TITLE_GENERATION.md`、`TITLE_GENERATION_IMPLEMENTATION.md` | C：实现总结并入功能参考或 changelog；测试 TODO 不应继续作为当前缺口展示 |
| `MEMORY_IMPROVEMENTS.md`、`MEMORY_IMPROVEMENTS_SUMMARY.md`、`MEMORY_SETTINGS_REVIEW.md` | C：保留一份当前行为参考，历史改进总结归档 |
| `rfc-*.md` | D：已实现 RFC 归档；仍未决策的 RFC 保留在 RFC 区，并注明状态 |
| `docs/archive/2026/optimization/**` | B/D：已核对实际引用和代码状态，归档已结束优化计划 |

### 3.3 `frontend/src/content`：A，按发布文档维护

中英文 `application`、`harness`、`introduction`、`tutorials`、`reference` 和已发布 `posts` 是前端文档站内容，应整体保留。它们不是内部计划，不应因为与 README 或后端文档存在主题重叠而删除。

建议：

- 以文档站内容作为面向用户的产品说明权威来源；
- README 只保留入口和快速启动，避免继续复制完整教程；
- 中英文文件按同一功能范围维护，新增功能不得只更新其中一种语言而不注明差异；
- 定期校验 `/docs/**` 内链、版本号、配置字段和实际路由。

### 3.4 `docs/manual` 与部署文档：A/B

| 文件族 | 建议 |
| --- | --- |
| `docs/manual/README.md`、`user-manual.md`、`devops-manual.md` | A/B：保留为正式手册；截图清单和完成状态需与实际图片、页面和脚本同步 |
| `docs/manual/screenshot-issues.md` | D：问题关闭后归档；不作为用户手册入口 |
| `docs/deployment/禁公网内网离线部署作业指导书.md`、`scripts/README-intranet.md` | A：离线部署执行入口，指定唯一权威版本，避免重复维护 |
| `docs/archive/2026/offline/offline-deployment-design.md`、`docs/archive/2026/offline/incidents/2026-06-23-offline-docker-image-build.md` | B/C：保留设计和制作细节，但与作业指导书建立边界，避免同一操作步骤复制三次 |
| `docs/deployment/MCP工具运维排故手册.md` | A：运维排障手册，保留并持续更新 |
| `docs/archive/2026/offline/incidents/2026-05-28-offline-docker-streaming-409.md`、`2026-07-15-agent-memory-path-shadowing.md`、`2026-06-23-offline-docker-deployment-review.md` | D/A：已关闭事故保留为复盘证据；若仍是现行故障手册的一部分，则从手册链接到复盘，不复制修复步骤 |
| `docs/archive/2026/offline/incidents/2026-06-23-offline-docker-remediation.md` | D：整改完成后归档；未完成项已转为带验收标准的当前 backlog |

### 3.5 测试、验证和覆盖率文档：当前权威已出现，应收敛旧计划

当前应作为权威治理文档保留：

- `docs/testing/coverage-matrix.md`：测试能力与主责任层级映射；
- `docs/testing/test-migration-ledger.md`：测试删除、迁移和等价覆盖的安全账本；
- `docs/testing-guidelines.md`：通用测试规范，但需要对齐当前目录和命令；
- `TEST_PLAN.md`、`task.md`、`progress.md`：内部阶段状态，保留但标记内部。

以下文件建议合并或归档：

| 文件族 | 建议 |
| --- | --- |
| `test-coverage-improvement-plan.md`、`test-enhancement-roadmap.md`、`testing-gap-remediation-plan.md` | C/D：内容重叠明显；将仍未完成的目标迁入当前治理计划，其余归档 |
| `test-reorganization-plan.md`、`testing-tools-integration-plan.md` | D：实施计划和迁移细节作为历史证据保留，日常删除/迁移判断只引用 ledger |
| `frontend-test-coverage-plan.md`、`frontend-test-coverage-summary.md`、`screenshot-test-coverage-plan.md` | C/D：保留当前 E2E/视觉测试入口，历史补测计划和总结归档 |
| `validation-best-practices.md`、`validation-gap-analysis.md`、`validation-log.md`、`validation-remaining-issues-plan.md`、`validation-orchestrator-implementation-plan.md` | C：合并为当前验证规范 + 历史验证记录；已完成的实施计划归档 |
| `ai-test-tools-integration.md`、`ai-code-validation-executive-summary.md`、`ai-code-validation-skill-analysis.md` | D/C：作为 AI 测试工具决策和验证证据保留，但不作为当前测试入口 |
| `docs/superpowers/plans/**`、`docs/superpowers/specs/**`、`docs/plans/**`、`docs/compose/plans/**` | D/A：未完成或仍影响当前行为的计划保留；已实现计划转为历史记录，并在文件头标注状态 |

### 3.6 权限、离线产品线和项目治理：A/B

| 文件 | 建议 | 依据 |
| --- | --- | --- |
| `docs/permission-model-redesign.md` | A | 当前权限模型主参考文档，已有审计和待办链接 |
| `docs/archive/2026/permission/permission-model-audit-2026-07-05.md` | A/B | 审计与代码验证证据；每次权限变更后重新审计或标注过期 |
| `docs/backlog.md` | C/B | 与历史审计和当前代码状态分离；保留带状态的权限 backlog |
| `docs/permission-matrix.md` | A/B | 需求和权限矩阵；需与实际 RBAC contract tests 同步 |
| `docs/skill-rbac-api.md` | A/B | API 参考；核对已废弃端点和当前返回码 |
| `docs/offline-product-line-governance-plan.md` | A | 当前产品线、上游同步和发布分支治理依据 |
| `docs/archive/2026/offline-feature-issue-report.md`、`offline-feature-fix-summary.md` | D | 分支问题报告和修复总结属于历史变更证据，不能作为当前产品规范 |
| `docs/archive/2026/offline/branch-change-report.md`、`code-change-summary-by-file.md` | D/E | 变更审计材料；完成审计后归档。若无合规或追溯需求，不应长期占据主文档入口 |

### 3.7 归零智能体和评测资料：A/D 分离

- `docs/fault-zeroing-agent/agent/**`、`samples/**`、`验证记录.md` 属于可复现实验资产，保留；本报告不对对应 Skill 文件本身作留存结论。
- `docs/zero_agent_eval_cases/**` 是评测数据、期望分析和历史复核资料，整体保留；应明确“伪数据/评测基线”，避免被误读为生产事故记录。
- `docs/fault-zeroing-agent/adversarial-review-2026-07-15.md`、`implementation-path.md` 和 `docs/archive/2026/agent-design-2026-06.md` 内容存在阶段性重叠：保留最新评估和实现路径，其余归档并建立互链。
- `docs/srs-writing-agent/**` 是智能体配置资产，不按普通项目说明文档删除。

### 3.8 其他项目分析文档：B/D

| 文件族 | 建议 |
| --- | --- |
| `docs/architecture/overview.md`、`docs/platform-dev-summary.md` | B：保留架构和平台能力概览，但与 `backend/docs/ARCHITECTURE*` 明确分工 |
| `docs/development/learning-roadmap.md` | A/B：新开发者入口，修正已不存在路径并指向当前权威文档 |
| `docs/archive/2026/decisions/intranet-source-import-decision-2026-07-15.md` | D：治理决策证据，归档并保留结论 |
| `docs/技术债务、功能清单、差距分析类文件` | C/D：完成事项转历史，未完成事项只保留一份带状态的 backlog |
| `.agent/**`、`.agents/**`、`.mimocode/**`、`.github/**`、`workflows/**` 中的文档型文件 | A/B：按其所属自动化工具或 CI 流程维护，不纳入普通产品文档导航 |

## 4. 已发现的维护风险

1. 《文档体系梳理与差距分析》描述的是旧快照，不能直接作为当前文件状态或缺口清单。
2. 历史 `docs/archive/2026/governance/feature-backlog-history-2026-07-15.md` 同时承担“未开发功能”和“已完成功能”记录，已拆为当前 backlog 与历史完成记录。
3. 测试治理已经形成 `coverage-matrix.md` + `test-migration-ledger.md` 的权威组合；旧测试计划不能继续作为删除测试的许可来源。
4. 权限模型同时存在主设计、审计、矩阵和待实现清单，必须明确主文档和状态来源，避免四处更新不一致。
5. 离线部署文档有“方案、整改、作业指导、事故复盘、镜像制作”多个层次，内容边界需要明确，但不应把事故复盘直接删除。
6. 部分历史文档仍引用不存在的旧路径或旧目录结构；应先修复索引和互链，再执行归档或删除。
7. 手册中的截图“已生成/待生成”状态需要与 `docs/manual/screenshots/` 和脚本实际结果重新核对。

## 5. 推荐执行顺序

1. 先新增 `docs/README.md` 作为导航，并定义“权威文档 / 内部记录 / 历史归档 / 评测资产”四类。
2. 指定测试、权限、离线部署、架构和用户手册的唯一权威入口。
3. 已更新 `docs/backlog.md`、旧测试计划和权限待办清单的状态，已完成事项转移至历史记录。
4. 将已结束的方案、总结、审计和事故材料移动到带日期的归档目录，保留原始结论和来源链接。
5. 修复失效链接、旧路径和截图状态后，再对无引用、无独立事实、无审计价值的 E 类文件进行二次确认。

## 6. 复核命令

以下命令用于后续复核，均不包含删除操作：

```bash
# 纳入评估的普通文档数量（排除 Skill 和依赖文档）
git ls-files '*.md' '*.mdx' '*.rst' '*.adoc' '*.txt' \
  | grep -v '/node_modules/' \
  | grep -v '/skills/' \
  | wc -l

# 检查文档引用和状态词
git grep -n -E '文档体系梳理与差距分析|待开发功能|coverage-matrix|test-migration-ledger|permission-model|offline-product-line' \
  -- ':!**/skills/**' ':!**/node_modules/**'

# 检查工作区是否有非本次审查变更
git status --short
```

## 附录 A：逐文件纳入清单

下表列出本次评估的全部 263 个普通文档型文件。等级是基于路径和文档角色的初步处置等级；同一族内仍需按正文状态执行第 3 节的合并、更新或归档动作。

| 文件 | 文档族 | 初步等级 |
| --- | --- | --- |
| `.github/copilot-instructions.md` | 自动化与内部工具 | A/B |
| `.github/pull_request_template.md` | 自动化与内部工具 | A/B |
| `.mimocode/plans/1782462446042-misty-river.md` | 自动化与内部工具 | A/B |
| `.mimocode/plans/1782604130944-quiet-orchid.md` | 自动化与内部工具 | A/B |
| `.mimocode/plans/1782821426875-glowing-moon.md` | 自动化与内部工具 | A/B |
| `.mimocode/plans/1782822106619-brave-circuit.md` | 自动化与内部工具 | A/B |
| `.mimocode/plans/1782884577194-hidden-star.md` | 自动化与内部工具 | A/B |
| `.mimocode/plans/1782904570743-silent-tiger.md` | 自动化与内部工具 | A/B |
| `.mimocode/plans/1782917831330-proud-otter.md` | 自动化与内部工具 | A/B |
| `.mimocode/plans/1782996498863-misty-circuit.md` | 自动化与内部工具 | A/B |
| `.mimocode/plans/1783174184169-witty-rocket.md` | 自动化与内部工具 | A/B |
| `.mimocode/plans/1783217784761-nimble-moon.md` | 自动化与内部工具 | A/B |
| `.mimocode/plans/1783255527164-brave-cactus.md` | 自动化与内部工具 | A/B |
| `.mimocode/plans/1783385113483-clever-mountain.md` | 自动化与内部工具 | A/B |
| `AGENTS.md` | 根目录入口文档 | A/B |
| `B7_REMAINING_FAILURES.md` | 根目录入口文档 | A/B |
| `CLAUDE.md` | 根目录入口文档 | A/B |
| `CODE_OF_CONDUCT.md` | 根目录入口文档 | A/B |
| `CONTRIBUTING.md` | 根目录入口文档 | A/B |
| `Install.md` | 根目录入口文档 | A/B |
| `README.md` | 根目录入口文档 | A/B |
| `README_fr.md` | 根目录入口文档 | A/B |
| `README_ja.md` | 根目录入口文档 | A/B |
| `README_ru.md` | 根目录入口文档 | A/B |
| `README_zh.md` | 根目录入口文档 | A/B |
| `SECURITY.md` | 根目录入口文档 | A/B |
| `TEST_COVERAGE_ADVERSARIAL_REVIEW.md` | 测试与验证治理 | A/B/C/D |
| `TEST_PLAN.md` | 测试与验证治理 | A/B/C/D |
| `backend/AGENTS.md` | 后端组件旁文档 | A/B |
| `backend/CLAUDE.md` | 后端组件旁文档 | A/B |
| `backend/CONTRIBUTING.md` | 后端组件旁文档 | A/B |
| `backend/README.md` | 后端组件旁文档 | A/B |
| `backend/docs/API.md` | 后端参考文档 | A/B |
| `backend/docs/APPLE_CONTAINER.md` | 后端参考文档 | A/B |
| `backend/docs/ARCHITECTURE.md` | 后端参考文档 | A/B |
| `backend/docs/ARCHITECTURE_zh.md` | 后端参考文档 | A/B |
| `backend/docs/AUTH_DESIGN.md` | 后端参考文档 | A/B |
| `backend/docs/AUTH_TEST_DOCKER_GAP.md` | 后端参考文档 | A/B |
| `backend/docs/AUTH_TEST_PLAN.md` | 后端参考文档 | A/B |
| `backend/docs/AUTH_UPGRADE.md` | 后端参考文档 | A/B |
| `backend/docs/AUTO_TITLE_GENERATION.md` | 后端参考文档 | A/B |
| `backend/docs/BACKEND_IMPROVEMENTS.md` | 后端参考文档 | A/B |
| `backend/docs/CONFIGURATION.md` | 后端参考文档 | A/B |
| `backend/docs/FILE_UPLOAD.md` | 后端参考文档 | A/B |
| `backend/docs/GUARDRAILS.md` | 后端参考文档 | A/B |
| `backend/docs/MCP_SERVER.md` | 后端参考文档 | A/B |
| `backend/docs/MEMORY_IMPROVEMENTS.md` | 后端参考文档 | A/B |
| `backend/docs/MEMORY_IMPROVEMENTS_SUMMARY.md` | 后端参考文档 | A/B |
| `backend/docs/MEMORY_SETTINGS_REVIEW.md` | 后端参考文档 | A/B |
| `backend/docs/PATH_EXAMPLES.md` | 后端参考文档 | A/B |
| `backend/docs/README.md` | 后端参考文档 | A/B |
| `backend/docs/SETUP.md` | 后端参考文档 | A/B |
| `backend/docs/STREAMING.md` | 后端参考文档 | A/B |
| `backend/docs/TITLE_GENERATION_IMPLEMENTATION.md` | 后端参考文档 | A/B |
| `backend/docs/engineering-backlog.md` | 后端参考文档 | A/B |
| `backend/docs/middleware-execution-flow.md` | 后端参考文档 | A/B |
| `backend/docs/plan_mode_usage.md` | 后端参考文档 | A/B |
| `backend/docs/rfc-create-deerflow-agent.md` | 后端参考文档 | A/B |
| `backend/docs/rfc-extract-shared-modules.md` | 后端参考文档 | A/B |
| `backend/docs/rfc-grep-glob-tools.md` | 后端参考文档 | A/B |
| `backend/docs/summarization.md` | 后端参考文档 | A/B |
| `backend/docs/task_tool_improvements.md` | 后端参考文档 | A/B |
| `backend/packages/harness/ideer/community/code_interpreter/README.md` | 后端组件旁文档 | A/B |
| `backend/packages/harness/ideer/community/data_analyzer/README.md` | 后端组件旁文档 | A/B |
| `backend/packages/harness/ideer/community/doc_reader/README.md` | 后端组件旁文档 | A/B |
| `backend/packages/harness/ideer/workflows/README.md` | 后端组件旁文档 | A/B |
| `backend/test-baseline.md` | 测试与验证治理 | A/B/C/D |
| `backend/tests/factories/README.md` | 后端组件旁文档 | A/B |
| `docker/provisioner/README.md` | 部署组件文档 | A |
| `docs/archive/2026/offline/code-change-summary-by-file.md` | 产品线与变更治理 | A/D |
| `docs/SKILL_NAME_CONFLICT_FIX.md` | 项目分析与内部记录 | B/C/D |
| `docs/archive/2026/testing/ai-code-validation-executive-summary.md` | 测试与验证治理 | A/B/C/D |
| `docs/archive/2026/testing/ai-code-validation-skill-analysis.md` | 测试与验证治理 | A/B/C/D |
| `docs/archive/2026/testing/ai-test-tools-integration.md` | 测试与验证治理 | A/B/C/D |
| `docs/archive/task-briefs/2026-05-23-start-local-and-fault-zeroing-brief.md` | 项目分析与内部记录 | B/C/D |
| `docs/backend-validator-coverage-gap-analysis.md` | 项目分析与内部记录 | B/C/D |
| `docs/backend-validator-coverage-summary.md` | 项目分析与内部记录 | B/C/D |
| `docs/archive/2026/offline/branch-change-report.md` | 产品线与变更治理 | A/D |
| `docs/bug-list.md` | 项目分析与内部记录 | B/C/D |
| `docs/compose/plans/2026-07-02-admin-user-crud.md` | 计划与规格 | A/D |
| `docs/compose/plans/2026-07-03-permission-model-refactor.md` | 计划与规格 | A/D |
| `"docs/deployment/Agent\350\256\260\345\277\206\350\267\257\345\276\204\351\201\256\350\224\275\345\205\261\344\272\253\346\231\272\350\203\275\344\275\223\346\216\222\351\232\234\345\244\215\347\233\230.md"` | 根目录入口文档 | A/B |
| `"docs/deployment/MCP\345\267\245\345\205\267\350\277\220\347\273\264\346\216\222\346\225\205\346\211\213\345\206\214.md"` | 根目录入口文档 | A/B |
| `"docs/deployment/\347\246\201\345\205\254\347\275\221\345\206\205\347\275\221\347\246\273\347\272\277\351\203\250\347\275\262\344\275\234\344\270\232\346\214\207\345\257\274\344\271\246.md"` | 根目录入口文档 | A/B |
| `"docs/deployment/\347\246\201\345\205\254\347\275\221\345\206\205\347\275\221\347\246\273\347\272\277\351\203\250\347\275\262\346\226\271\346\241\210.md"` | 根目录入口文档 | A/B |
| `"docs/deployment/\347\246\273\347\272\277Docker\345\275\222\351\233\266\345\210\206\346\236\220409\351\227\256\351\242\230\345\216\237\345\233\240\344\270\216\344\277\256\345\244\215.md"` | 根目录入口文档 | A/B |
| `"docs/deployment/\347\246\273\347\272\277Docker\351\203\250\347\275\262\345\256\236\346\223\215\351\227\256\351\242\230\344\273\243\347\240\201\345\256\241\346\237\245\346\212\245\345\221\212.md"` | 根目录入口文档 | A/B |
| `"docs/deployment/\347\246\273\347\272\277Docker\351\203\250\347\275\262\346\225\264\346\224\271\346\226\271\346\241\210.md"` | 根目录入口文档 | A/B |
| `"docs/deployment/\347\246\273\347\272\277\351\203\250\347\275\262Docker\351\225\234\345\203\217\345\210\266\344\275\234\351\227\256\351\242\230\344\270\216\350\247\243\345\206\263\346\226\271\346\241\210\346\225\264\347\220\206.md"` | 根目录入口文档 | A/B |
| `docs/fault-zeroing-agent/agent/SOUL.md` | 领域资产与评测 | A/D |
| `docs/fault-zeroing-agent/samples/case-01/design_docs/interface_constraints.md` | 领域资产与评测 | A/D |
| `docs/fault-zeroing-agent/samples/case-01/logs/system_log.md` | 领域资产与评测 | A/D |
| `docs/fault-zeroing-agent/samples/case-01/problem_statement.md` | 领域资产与评测 | A/D |
| `docs/fault-zeroing-agent/samples/case-01/test_records/reproduction_record.md` | 测试与验证治理 | A/B/C/D |
| `docs/fault-zeroing-agent/samples/case-02/historical_cases/similar_case.md` | 领域资产与评测 | A/D |
| `docs/fault-zeroing-agent/samples/case-02/logs/system_log.md` | 领域资产与评测 | A/D |
| `docs/fault-zeroing-agent/samples/case-02/problem_statement.md` | 领域资产与评测 | A/D |
| `docs/fault-zeroing-agent/samples/case-02/test_records/reproduction_record.md` | 测试与验证治理 | A/B/C/D |
| `"docs/fault-zeroing-agent/\345\275\222\351\233\266\346\231\272\350\203\275\344\275\223\345\273\272\350\256\276\350\277\233\345\261\225\346\261\207\346\212\245.md"` | 根目录入口文档 | A/B |
| `"docs/fault-zeroing-agent/\351\252\214\350\257\201\350\256\260\345\275\225.md"` | 根目录入口文档 | A/B |
| `docs/archive/2026/testing/frontend-test-coverage-plan.md` | 项目分析与内部记录 | B/C/D |
| `docs/archive/2026/testing/frontend-test-coverage-summary.md` | 项目分析与内部记录 | B/C/D |
| `docs/manual-generation-plan.md` | 项目分析与内部记录 | B/C/D |
| `docs/manual/README.md` | 手册与部署运维 | A/B |
| `docs/manual/devops-manual.md` | 手册与部署运维 | A/B |
| `docs/manual/screenshot-issues.md` | 手册与部署运维 | A/B |
| `docs/manual/user-manual.md` | 手册与部署运维 | A/B |
| `docs/archive/2026/testing/multi-role-testing.md` | 项目分析与内部记录 | B/C/D |
| `docs/archive/2026/offline-feature-fix-summary.md` | 产品线与变更治理 | A/D |
| `docs/archive/2026/offline-feature-issue-report.md` | 产品线与变更治理 | A/D |
| `docs/offline-product-line-governance-plan.md` | 产品线与变更治理 | A/D |
| `docs/optimization/01-bug-fix-and-feature-completion.md` | 优化方案 | C/D |
| `docs/optimization/02-testing-improvement.md` | 优化方案 | C/D |
| `docs/optimization/03-documentation.md` | 优化方案 | C/D |
| `docs/optimization/04-performance-optimization.md` | 优化方案 | C/D |
| `docs/optimization/05-security-hardening.md` | 优化方案 | C/D |
| `docs/optimization/INDEX.md` | 优化方案 | C/D |
| `docs/optimization/README.md` | 优化方案 | C/D |
| `docs/optimization/implementation-roadmap.md` | 优化方案 | C/D |
| `docs/permission-matrix.md` | 权限模型与 API | A/B/C |
| `docs/archive/2026/permission/permission-model-audit-2026-07-05.md` | 权限模型与 API | A/B/C |
| `docs/permission-model-redesign.md` | 权限模型与 API | A/B/C |
| `docs/plans/2026-04-01-langfuse-tracing.md` | 计划与规格 | A/D |
| `docs/plans/2026-05-21-subagent-unavailable-fix-plan.md` | 计划与规格 | A/D |
| `docs/platform-dev-summary.md` | 项目分析与内部记录 | B/C/D |
| `docs/archive/2026/testing/screenshot-test-coverage-plan.md` | 项目分析与内部记录 | B/C/D |
| `docs/skill-rbac-api.md` | 权限模型与 API | A/B/C |
| `docs/srs-writing-agent/agent/SOUL.md` | 领域资产与评测 | A/D |
| `docs/superpowers/plans/2026-04-10-event-store-history.md` | 计划与规格 | A/D |
| `docs/superpowers/plans/2026-05-19-fault-zeroing-agent-poc.md` | 计划与规格 | A/D |
| `docs/superpowers/plans/2026-05-23-validate-fault-zeroing-review-fixes.md` | 计划与规格 | A/D |
| `docs/superpowers/plans/2026-07-15-test-gate-simplification.md` | 计划与规格 | A/D |
| `docs/superpowers/specs/2026-04-11-runjournal-history-evaluation.md` | 计划与规格 | A/D |
| `docs/superpowers/specs/2026-04-11-summarize-marker-design.md` | 计划与规格 | A/D |
| `docs/superpowers/specs/2026-05-19-fault-zeroing-agent-design.md` | 计划与规格 | A/D |
| `docs/tech-debt-user-tables.md` | 项目分析与内部记录 | B/C/D |
| `docs/archive/2026/testing/test-coverage-improvement-plan.md` | 测试与验证治理 | A/B/C/D |
| `docs/archive/2026/testing/test-enhancement-roadmap.md` | 测试与验证治理 | A/B/C/D |
| `docs/archive/2026/testing/test-reorganization-plan.md` | 测试与验证治理 | A/B/C/D |
| `docs/archive/2026/testing/testing-gap-remediation-plan.md` | 测试与验证治理 | A/B/C/D |
| `docs/testing-guidelines.md` | 测试与验证治理 | A/B/C/D |
| `docs/archive/2026/testing/testing-tools-integration-plan.md` | 测试与验证治理 | A/B/C/D |
| `docs/testing/coverage-matrix.md` | 测试与验证治理 | A/B/C/D |
| `docs/testing/test-migration-ledger.md` | 测试与验证治理 | A/B/C/D |
| `docs/archive/2026/testing/validation-best-practices.md` | 测试与验证治理 | A/B/C/D |
| `docs/archive/2026/testing/validation-gap-analysis.md` | 测试与验证治理 | A/B/C/D |
| `docs/archive/2026/testing/validation-log.md` | 测试与验证治理 | A/B/C/D |
| `docs/archive/2026/testing/validation-orchestrator-implementation-plan.md` | 测试与验证治理 | A/B/C/D |
| `docs/archive/2026/testing/validation-remaining-issues-plan.md` | 测试与验证治理 | A/B/C/D |
| `docs/zero_agent_eval_cases/README.md` | 领域资产与评测 | A/D |
| `docs/zero_agent_eval_cases/case_01_execution_process_evaluation.md` | 领域资产与评测 | A/D |
| `docs/zero_agent_eval_cases/case_01_wind_tunnel_heat_flux_drift/00_problem_statement.md` | 领域资产与评测 | A/D |
| `"docs/zero_agent_eval_cases/case_01_wind_tunnel_heat_flux_drift/01_design\346\226\271\346\241\210.md"` | 根目录入口文档 | A/B |
| `"docs/zero_agent_eval_cases/case_01_wind_tunnel_heat_flux_drift/02_test_outline\350\257\225\351\252\214\345\244\247\347\272\262.md"` | 根目录入口文档 | A/B |
| `"docs/zero_agent_eval_cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary\350\257\225\351\252\214\346\200\273\347\273\223\346\212\245\345\221\212.md"` | 根目录入口文档 | A/B |
| `docs/zero_agent_eval_cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md` | 领域资产与评测 | A/D |
| `docs/zero_agent_eval_cases/case_01_wind_tunnel_heat_flux_drift/06_expected_analysis.md` | 领域资产与评测 | A/D |
| `docs/zero_agent_eval_cases/case_02_thermal_vacuum_temp_overshoot/00_problem_statement.md` | 领域资产与评测 | A/D |
| `"docs/zero_agent_eval_cases/case_02_thermal_vacuum_temp_overshoot/01_design\346\226\271\346\241\210.md"` | 根目录入口文档 | A/B |
| `"docs/zero_agent_eval_cases/case_02_thermal_vacuum_temp_overshoot/02_test_outline\350\257\225\351\252\214\345\244\247\347\272\262.md"` | 根目录入口文档 | A/B |
| `"docs/zero_agent_eval_cases/case_02_thermal_vacuum_temp_overshoot/03_test_summary\350\257\225\351\252\214\346\200\273\347\273\223\346\212\245\345\221\212.md"` | 根目录入口文档 | A/B |
| `docs/zero_agent_eval_cases/case_02_thermal_vacuum_temp_overshoot/05_historical_or_review_notes.md` | 领域资产与评测 | A/D |
| `docs/zero_agent_eval_cases/case_02_thermal_vacuum_temp_overshoot/06_expected_analysis.md` | 领域资产与评测 | A/D |
| `docs/zero_agent_eval_cases/case_03_arc_heated_ablation_anomaly/00_problem_statement.md` | 领域资产与评测 | A/D |
| `"docs/zero_agent_eval_cases/case_03_arc_heated_ablation_anomaly/01_design\346\226\271\346\241\210.md"` | 根目录入口文档 | A/B |
| `"docs/zero_agent_eval_cases/case_03_arc_heated_ablation_anomaly/02_test_outline\350\257\225\351\252\214\345\244\247\347\272\262.md"` | 根目录入口文档 | A/B |
| `"docs/zero_agent_eval_cases/case_03_arc_heated_ablation_anomaly/03_test_summary\350\257\225\351\252\214\346\200\273\347\273\223\346\212\245\345\221\212.md"` | 根目录入口文档 | A/B |
| `docs/zero_agent_eval_cases/case_03_arc_heated_ablation_anomaly/05_historical_or_review_notes.md` | 领域资产与评测 | A/D |
| `docs/zero_agent_eval_cases/case_03_arc_heated_ablation_anomaly/06_expected_analysis.md` | 领域资产与评测 | A/D |
| `"docs/\345\206\205\347\275\221\346\272\220\347\240\201\345\257\274\345\205\245\345\217\226\350\210\215\345\210\206\346\236\220.md"` | 根目录入口文档 | A/B |
| `"docs/\345\237\272\344\272\216deer-flow\346\241\206\346\236\266\345\274\200\345\217\221\345\275\222\351\233\266\346\216\222\346\225\205\346\231\272\350\203\275\344\275\223\347\232\204\345\210\206\346\236\220\346\226\271\346\241\210.md"` | 根目录入口文档 | A/B |
| `"docs/\345\255\246\344\271\240\350\267\257\347\272\277\345\233\276.md"` | 根目录入口文档 | A/B |
| `"docs/\345\275\222\351\233\266\346\216\222\346\225\205\346\231\272\350\203\275\344\275\223\345\217\257\350\241\214\346\200\247\344\270\216\345\256\236\347\216\260\350\267\257\345\276\204_\344\273\243\347\240\201\346\216\242\347\264\242\347\211\210.md"` | 根目录入口文档 | A/B |
| `"docs/\345\275\222\351\233\266\346\231\272\350\203\275\344\275\223_\345\257\271\346\212\227\345\274\217\345\256\241\346\237\245\350\257\204\344\274\260\346\212\245\345\221\212.md"` | 根目录入口文档 | A/B |
| `"docs/\345\276\205\345\274\200\345\217\221\345\212\237\350\203\275.md"` | 根目录入口文档 | A/B |
| `"docs/\346\226\207\346\241\243\344\275\223\347\263\273\346\242\263\347\220\206\344\270\216\345\267\256\350\267\235\345\210\206\346\236\220.md"` | 根目录入口文档 | A/B |
| `"docs/\346\235\203\351\231\220\346\250\241\345\236\213\351\207\215\346\236\204_\345\276\205\345\256\236\347\216\260\345\212\237\350\203\275\346\270\205\345\215\225.md"` | 根目录入口文档 | A/B |
| `"docs/\346\236\266\346\236\204\346\246\202\350\247\210.md"` | 根目录入口文档 | A/B |
| `findings.md` | 根目录入口文档 | A/B |
| `frontend/AGENTS.md` | 前端组件旁文档 | A/B |
| `frontend/CLAUDE.md` | 前端组件旁文档 | A/B |
| `frontend/README.md` | 前端组件旁文档 | A/B |
| `frontend/public/demo/threads/3823e443-4e2b-4679-b496-a9506eae462b/user-data/outputs/fei-fei-li-podcast-timeline.md` | 前端组件旁文档 | A/B |
| `frontend/public/demo/threads/7f9dc56c-e49c-4671-a3d2-c492ff4dce0c/user-data/outputs/leica-master-photography-article.md` | 前端组件旁文档 | A/B |
| `frontend/public/demo/threads/ad76c455-5bf9-4335-8517-fc03834ab828/user-data/outputs/titanic_summary.txt` | 前端组件旁文档 | A/B |
| `frontend/public/demo/threads/d3e5adaf-084c-4dd5-9d29-94f1d6bccd98/user-data/outputs/diana_hu_research.md` | 前端组件旁文档 | A/B |
| `frontend/public/demo/threads/fe3f7974-1bcb-4a01-a950-79673baafefd/user-data/outputs/research_deerflow_20260201.md` | 前端组件旁文档 | A/B |
| `frontend/src/components/workspace/settings/about.md` | 前端组件旁文档 | A/B |
| `frontend/src/content/en/application/agents-and-threads.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/application/configuration.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/application/deployment-guide.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/application/index.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/application/operations-and-troubleshooting.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/application/quick-start.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/application/workspace-usage.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/harness/configuration.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/harness/customization.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/harness/design-principles.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/harness/index.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/harness/integration-guide.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/harness/lead-agent.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/harness/mcp.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/harness/memory.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/harness/middlewares.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/harness/quick-start.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/harness/sandbox.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/harness/skills.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/harness/subagents.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/harness/tools.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/index.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/introduction/core-concepts.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/introduction/harness-vs-app.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/introduction/why-ideer.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/posts/provider-safety-termination-in-tool-agents.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/posts/releases/2_0_rc.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/posts/weekly/2026-04-06.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/reference/model-providers/ark.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/reference/model-providers/index.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/tutorials/create-your-first-harness.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/tutorials/deploy-your-own-ideer.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/tutorials/first-conversation.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/tutorials/use-tools-and-skills.mdx` | 前端发布文档 | A |
| `frontend/src/content/en/tutorials/work-with-memory.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/application/agents-and-threads.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/application/configuration.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/application/deployment-guide.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/application/index.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/application/operations-and-troubleshooting.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/application/quick-start.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/application/workspace-usage.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/harness/configuration.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/harness/customization.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/harness/design-principles.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/harness/index.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/harness/integration-guide.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/harness/lead-agent.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/harness/mcp.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/harness/memory.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/harness/middlewares.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/harness/quick-start.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/harness/sandbox.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/harness/skills.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/harness/subagents.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/harness/tools.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/index.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/introduction/core-concepts.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/introduction/harness-vs-app.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/introduction/why-ideer.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/posts/provider-safety-termination-in-tool-agents.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/posts/releases/2_0_rc.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/posts/weekly/2026-04-06.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/reference/model-providers/ark.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/reference/model-providers/index.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/tutorials/create-your-first-harness.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/tutorials/deploy-your-own-ideer.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/tutorials/first-conversation.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/tutorials/use-tools-and-skills.mdx` | 前端发布文档 | A |
| `frontend/src/content/zh/tutorials/work-with-memory.mdx` | 前端发布文档 | A |
| `progress.md` | 根目录入口文档 | A/B |
| `scripts/README-intranet.md` | 部署组件文档 | A |
| `task.md` | 根目录入口文档 | A/B |
| `test_log.md` | 测试与验证治理 | A/B/C/D |
| `workflows/README.md` | 自动化与内部工具 | A/B |
