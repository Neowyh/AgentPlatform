# M3 开工基线收口报告

> 验收日期：2026-09-13
> 候选版本：`develop@d4acdc5c2c2849d814d8d87932039b500b5683fa`（工作区含 M3 实现改动）
> 工作区：保留既有未跟踪规格/验收材料，并包含本轮知识管理实现
> 结论：**UNVERIFIED**

当前候选补齐了 M3 知识文档管理的核心 API、RAGFlow 契约适配、tombstone 重传、metadata 编辑、初始化状态和 Gateway 后台处理循环。真实 RAGFlow 双 KB×双用户验收及完整跨端 lane 仍未形成当前候选的通过证据。

## Gate 判定

| Gate | 当前判定 | 证据与缺口 |
|---|---|---|
| M0-T0.1 统一 migration 链 | INCOMPLETE | `backend` migration 单元及 unified-chain / Workflow V2 DB 测试为 `25 passed, 3 skipped`；测试覆盖统一版本表和 SQLite 路径，但 3 个跳过项使 fresh/existing 的全部双数据库要求没有完整当前证据。未修改运行库。 |
| M1 Runtime Smoke / Gate 1 | INCOMPLETE | 历史报告记录 2026-09-10 在候选前序版本完成 Receipt、脱敏和断网链路；本轮没有可复核的当前候选 RAGFlow、真实模型或重新断网运行记录，故历史证据不升级为当前 PASS。 |
| M2 Gate 2 Resource Governance | INCOMPLETE | M2 实现已合入；知识服务、资源 API、生命周期、权限和 provider binding 聚焦测试纳入本轮 `97 passed` 集合。缺少本轮隔离真实 provider 的完整创建、可见性和生命周期验收记录。 |
| M2 Gate 3 Effective Scope | INCOMPLETE | runtime scope、Agent/Workflow/Sub-Agent 限制和 raw dataset 防注入有聚焦测试证据；计划要求的隔离 dev RAGFlow 两 KB×两用户正反场景及实际拒绝调用记录本轮未执行。 |
| M7 Device Control Plane / Secure WSS | INCOMPLETE | 实现已合入，后端设备控制聚焦测试通过；临时 Uvicorn 真实服务用例因沙箱 `Operation not permitted` 无法绑定本地 socket。Linux 结果不能标为 Windows 实测。 |
| M8 Local Files / Python / Tool Integration | INCOMPLETE | 实现已合入；本轮未能执行 `local-runtime/tests`，uv 尝试解析 `websockets` 时因网络 DNS 受限失败。文件、Python、consent、artifact 和脱敏的历史/单元证据不能替代本轮完整 lane。 |

因此 M3 当前判定为 **UNVERIFIED**，不是 READY。解除条件是补齐 M0-T0.1 的 fresh/existing 隔离数据库双后端记录、M1/M2 的真实 provider/模型验收，以及在允许本地 socket 的环境完成要求的标准 lane 和 `pr-standard`。

本轮 M3 实现聚焦验证：知识/RAGFlow/features `49 passed`，持久化迁移 `27 passed`，合计 `76 passed`；前端 TypeScript 检查通过。允许 socket 的 `pr-standard` 已完成 backend-standard（`25,828 passed, 145 skipped`，约 1033 秒）和 frontend-standard Rstest（`120 files / 755 tests passed`），frontend-smoke 在约 284 秒处出现导航不实现输出后中止，父 lane 以 `status=130` 结束，因此不能作为完整 PR 通过证据。

随后补充的实现将 retry/rebuild/delete 改为持久化意图，由 Gateway Knowledge Worker 执行 provider 操作；列表读取不再驱动外部状态刷新。补充回归仍为 `49 passed`，最新 GitNexus 检测为 `74 symbols / 45 flows / CRITICAL`。

## 当前验证记录

| 时间 | 命令 | 结果 |
|---|---|---|
| 2026-09-13 | `make doctor` | Ready；3 个提示：缺少 `frontend/.env`、未配置 web capture、bash compatibility。 |
| 2026-09-13 | `python3 scripts/test_inventory.py --collect --json` | 退出码 0；完成测试清单收集，本轮未新增或移动测试。 |
| 2026-09-13 | `python3 scripts/test_preflight.py pr-standard` | FAIL/环境受限：Chromium 启动失败，本地 socket `Operation not permitted`。 |
| 2026-09-13 | `backend` migration focused tests | `25 passed, 3 skipped`，退出码 0。 |
| 2026-09-13 | M2/M7 focused backend tests | `97 passed, 1 failed`；失败为临时 Uvicorn socket 无法启动，退出码 1。 |
| 2026-09-13 | `local-runtime` tests | INCOMPLETE；uv 因 DNS 无法获取 `websockets`，退出码 1。 |
| 2026-09-13 | `backend-standard` 沙箱运行 | preflight 因本地 socket 失败，退出码 1。 |
| 2026-09-13 | `backend-standard` 允许 socket 的重跑 | `25,806 passed, 144 skipped, 825 warnings`，`1007s`，父/子 `status=0`。 |
| 2026-09-13 | `pr-standard` | backend-standard `25,806 passed, 144 skipped`，`976s`；frontend-standard Rstest `120 files / 755 tests`、Vitest `357 files / 9,969 tests`，`400s`；frontend-smoke `29 passed`，`109s`；父 lane `1487s`，`status=0`。 |

GitNexus 最终使用项目 runner 以 `--index-only --pdg` 重建至候选 HEAD，报告 `119.9s`、`408,500 nodes`、`859,913 edges`、`1,096 flows`。`detect-changes --scope all` 报告 `5 files, 8 symbols, 0 affected processes, risk low`；列出的文档变更包括外部修改的 `AGENTS.md`，未发现产品执行流影响。runner 的随后 `status --json` 仍返回 `status: stale`，同时报告 indexed commit 与 HEAD 相同、runner identity current、incompleteReasons 为空；由于状态矛盾，本轮不把图谱 freshness 作为完全通过证据。项目没有可用的本地 `gitnexus/` 源码目录，无法执行技能要求的本地构建路径。

## 实现和文档状态

- M2 的 canonical Resource 治理已进入 `ResourceType.KNOWLEDGE_BASE`、`knowledge_bases`、provider binding、dependency/scope 和 runtime adapter；知识方案的“未开始”描述只适用于历史 Gate 1 报告中的前序候选。
- M7 控制面实际位于 `backend/app/device_control/`，M8 文件/Python 逻辑位于 `local-runtime/` 及现有扩展接缝；两者均未进入 DeerFlow harness 的产品迁移范围。
- PATCH-006 的统一链已经由当前 migration/tests 体现为关闭；PATCH-009 的 SQLite/PostgreSQL Workflow V2 执行验证已有历史记录，但其上游/extension 移除条件仍未满足，继续保持 open。
- 总方案中的 D1/D4 仍未被本轮重新裁决：M7 是唯一允许并行线；设备模块目录差异属于已定位事实，不登记为新的维护者决策。

## 下一步解除顺序

1. 在允许本地 socket、依赖已缓存的环境重跑 backend-standard、local-runtime 专项和 `pr-standard`，保存每个子 lane 与父 lane 的最终汇总。
2. 用隔离数据库补齐 M0-T0.1 的 fresh/existing 双后端 upgrade、资源/version/snapshot 保留断言。
3. 启动隔离 dev RAGFlow，执行两 KB×两用户的 M2 Gate 2/3 正反场景，并保留调用、拒绝和脱敏证据。
4. 具备上述证据后重新判断 M3；在此之前只提交下一阶段计划供确认，不创建 M3 实现分支。

## 依据

## 当前候选补充证据

2026-09-13 在隔离 RAGFlow v0.27.1 栈执行真实 provider Gate 4：`DEER_FLOW_RUN_LIVE_TESTS=1 ... pytest tests/test_knowledge_gate4_live.py -q -s`，结果 `1 passed`。覆盖上传、解析、READY、检索命中、定向删除及删除后无命中。

同一当前候选随后运行 canonical backend-standard：`25,832 passed, 145 skipped, 821 warnings`，`TEST_LANE_DURATION ... seconds=1254 status=0`。

前端当前候选 `pnpm check`（ESLint + TypeScript）通过；完整 frontend-smoke/pr-standard 仍按既有记录为未完成。

尝试执行 `core-full`：backend-full 为 `25,832 passed, 145 skipped` 但 lane 因既有 `test_hung_renewal_is_bounded_by_confirmed_lease_deadline` 失败而结束；frontend-core 的 Vitest 在 jsdom 导航 warning 后约 333 秒无进展，按规范中止（`status=130`）；父 lane `status=130`。

后续单独重跑前端全量 Vitest（fork worker、2 个并发 worker、测试与 hook 超时 5 秒）完成：`358 files / 9,978 tests passed`，耗时约 279 秒。该结果不改变 `core-full` 父 lane 的失败状态，因为 core-full 的 backend-full 子 lane 仍有失败，且 frontend-visual、frontend-a11y、backend-blocking-io 和真实浏览器 Gate 4 尚未完成。

当前候选追加专项结果：`backend-blocking-io` 为 `96 passed`，父 lane `status=0`；`frontend-a11y` 为 `3 passed`，父 lane `status=0`；`frontend-smoke` 为 `29 passed`，父 lane `status=0`。重新运行的 `pr-standard` 中 backend-standard 为 `25,832 passed, 145 skipped`、frontend-standard Rstest 为 `120 files / 755 tests passed`，但 Vitest 在默认并发下 372 秒无最终汇总，按规范中止，父 lane `status=130`。单独的 frontend-visual 运行发现已有截图差异及 `localhost:3001` 连接拒绝，运行至 `2 passed`、`142 did not run` 后中止，`status=130`。

本轮还修复了初始化请求的幂等计数：重复请求复用同一在途意图，不提前增加实际 provider 尝试次数；Worker 在网络调用前后刷新持久化对象，并以租约 owner 条件释放 lease，新增回归后知识文档单测为 `15 passed`。

补充专项：`frontend-a11y` 为 `3 passed`（114 秒），`frontend-smoke` 为 `29 passed`（132 秒），`frontend-real` 收集到 6 项但因缺少 Real E2E manifest/状态目录全部 skip（2 秒）；`backend-serial` 当前复跑仍为 1 failed、53 passed、8 skipped，失败为既有 `test_hung_renewal_is_bounded_by_confirmed_lease_deadline`，因此不能将 `core-full` 判为通过。

新增 Worker 回归：在隔离 SQLite 中创建未绑定知识库及 uploaded 文档，单次 `_tick` 完成稳定 dataset 初始化、文档摄取、状态写回和租约释放，结果 `1 passed`。

知识模块聚焦套件在加入 Worker 回归后为 `33 passed`；最终 GitNexus 检测仍报告 `18 files / 97 symbols / 45 affected processes / critical`。

补充低基数 telemetry：RAGFlow 摄取和检索现在记录操作、结果、稳定错误类别与耗时；检索区分成功、零命中和错误，不记录 query、用户、文档 ID、凭据或 provider 原始错误。相关 RAGFlow/知识聚焦回归为 `83 passed`。

单独运行 frontend-standard 的 Vitest（fork pool、2 个 worker、5 秒 test/hook timeout）完成 `358 files / 9,978 tests passed`；canonical runner 仍使用仓库默认命令，组合运行时在 Vitest 清理阶段未及时产生最终汇总，故父 lane 仍为未完成。

最终候选补充（2026-09-14）：尝试用隔离本地 Gateway、临时 RAGFlow 契约替身和浏览器执行 Knowledge Center 创建、上传、READY、删除流程。浏览器测试因临时 provider 进程受沙箱本地 socket 限制退出，知识库初始化进入失败状态，测试在 120 秒超时；该结果为 INCOMPLETE，不能作为真实 RAGFlow Gate 4 通过证据。最终 `git diff --check` 通过，`python3 scripts/test_inventory.py` 退出码 0；`detect-changes --scope all` 报告 `19 files / 120 symbols / 45 affected processes / risk critical`，故图谱检测也不能宣称低风险。

随后在允许本地 socket 的隔离栈中重跑：mock provider 可用，Gateway 初始化成功并将知识库置为 `ready`，但浏览器文件输入未产生 `/documents` 上传请求，测试两次均在 120 秒超时，数据库保持零文档。验收脚本已改为定位 Knowledge Center 自身的 `label input[type=file]`；问题仍需在真实前端运行环境中继续定位。该结果仍为 INCOMPLETE，且使用契约替身，不替代真实 RAGFlow Gate 4。

最终修正验收脚本后，隔离 Gateway + RAGFlow HTTP 契约替身浏览器流程通过：`1 passed (13.1s)`。流程覆盖登录、创建并绑定 KB、页面切换、上传 API、后台摄取至 READY、删除以及删除后列表 `items: []`；该证据仅证明平台浏览器集成和状态闭环，provider 为临时替身，真实 RAGFlow Gate 4 仍须单独执行。

补充前端修复：Library 顶部的 Upload Document 按钮现在会触发当前知识库的上传控件，并沿用能力状态与服务端限制；前端 `pnpm check` 通过，相关组件聚焦 runner 退出码 0。最终 GitNexus 检测为 `20 files / 121 symbols / 45 affected processes / risk critical`。

受影响前端组件聚焦 Vitest：`2 files / 12 tests passed`（fork pool，2 workers）；这只验证组件行为，不替代完整 frontend-standard、visual 和真实浏览器 provider 验收。

当前候选再次运行 `bash scripts/run-test-lane.sh pr-standard`：backend-standard 完成 `25,834 passed, 145 skipped, 819 warnings`，`TEST_LANE_DURATION ... seconds=1436 status=0`；frontend-standard 的 Rstest 完成 `120 files / 755 tests passed`，随后 Vitest 在默认 runner 清理阶段持续输出 jsdom navigation warning，运行至 `503s` 无最终汇总，按测试协议中止，`TEST_LANE_DURATION lane=frontend-standard seconds=503 status=130`；父 lane `TEST_LANE_DURATION lane=pr-standard seconds=1941 status=130`。因此本次 pr-standard 仍不能判为通过。

本轮进一步尝试仅调整 Vitest pool 与超时配置，仍在相同 navigation teardown 阶段无最终汇总，随后撤销该未验证的 runner 配置改动，保持产品和测试配置原状。canonical frontend-standard 的未完成状态不变。

最终候选重新运行 canonical `pr-standard`：backend-standard `25,834 passed, 145 skipped, 817 warnings`（`1015s status=0`），frontend-standard Rstest `120 files / 755 tests` 且 Vitest `358 files / 9,978 tests`（`286s status=0`），frontend-smoke `29 passed`（`111s status=0`），父 lane `1413s status=0`。为固化已验证的执行方式，标准 runner 现显式使用 fork pool、2 workers、5 秒 test/hook timeout 和 verbose reporter。

最终候选运行 `core-full`：backend-full 通过，frontend-core coverage 与 check 通过（Statements 59.11%、Branches 51.06%），frontend-mock-e2e `326 passed`，父 lane `1923s status=0`。

专项 lane：backend-blocking-io `96 passed`（`16s status=0`），frontend-a11y `3 passed`（`131s status=0`）。修正 visual screenshot spec 的 base URL，使其跟随 Playwright 配置后，frontend-visual 仍发现基线截图差异；同时部分登录场景依赖的 Gateway `8001` 未启动，运行结果为 `15 passed, 1 interrupted, 153 did not run`，`168s status=130`，不能判为视觉验收通过。

- [M3 收口计划](../plans/2026-09-13-m3-readiness-closeout-plan.md)
- [Knowledge Gate 1 历史报告](knowledge-gate1-acceptance-report.md)
- [Resource Governance V2 验收矩阵](resource-governance-v2-acceptance-matrix.md)
- [Knowledge 实现清单](../knowledge/IMPLEMENTATION_INVENTORY.md)
- [Local Runtime 测试矩阵](../local-runtime/TEST_MATRIX.md)
- [Local Runtime 实现清单](../local-runtime/IMPLEMENTATION_INVENTORY.md)
- [Patch Ledger](../local-runtime/PATCH_LEDGER.md)

## 2026-09-14 当前候选补充验收

项目内 `ideer-dev` RAGFlow v0.27.1、TEI 及其依赖容器已确认健康；重复的 `/home/neowyh/services/ragflow/docker` Compose 栈五个容器已停止，数据卷保留。真实 provider Gate4 再次通过：`1 passed in 11.99s`。

在隔离 SQLite 数据库和 Gateway 进程中，通过普通用户 API 完成了创建 KB、后台自动初始化、上传、后台摄取至 `ready`、授权范围内 Agent 检索命中、删除和删除后无命中；Gateway `/health` 与 `/api/features` 均返回可用状态。该流程使用当前候选代码和真实 RAGFlow，不使用 provider mock。验收资产已登记为临时管理员 `m3-admin@example.com`、KB slug `m3-gate4-kb` 及其 marker 文档；平台临时数据库和本地 marker 文件已清理，RAGFlow 中仅保留空 dataset 以避免误删既有数据。

本轮新增 worker 异常恢复回归后，知识聚焦测试为 `48 passed`，ruff 检查通过。完整 `backend-standard` 在 preflight 通过后测试主体约四分钟无输出且进程消失，按协议记为 incomplete/timeout；前端全量 Vitest 在提权环境出现既有管理页/InputBox 测试超时。GitNexus 当前 `detect-changes --scope all` 报告整体改动 `23 files / 123 symbols / 45 affected processes / risk critical`。因此 M3 判定仍为 **UNVERIFIED**：真实 Knowledge 闭环已证明，但完整标准 lane、双用户/双 KB 权限矩阵、M0/M1/M2 当前候选证据和视觉验收仍未齐全。

当前候选随后完成 canonical `pr-standard`：backend-standard `25,835 passed, 145 skipped`（`982.56s`，status=0），frontend-standard Rstest `120 files / 755 tests passed` 且 Vitest 全量通过，frontend-smoke `29 passed`（`107s`），父 lane `1349s status=0`。

随后运行交付级 `core-full`：backend-full 完成且 `TEST_LANE_DURATION ... seconds=964 status=0`；frontend-core coverage/check 通过（Statements 59.11%、Branches 51.06%），frontend-mock-e2e `326 passed`（`466s`），父 lane `1799s status=0`。

测试清单在当前候选上重新运行 `python3 scripts/test_inventory.py`，退出码 0；`git diff --check` 通过。视觉专项仍沿用已记录的当前环境结果：Gateway 未启动且存在基线差异，`frontend-visual` 为 `15 passed, 1 interrupted, 153 did not run`，因此视觉验收不宣称通过。双用户/双 KB 权限矩阵及 M0/M1/M2 当前候选证据仍未补齐，整体判定保持 **UNVERIFIED**。

补做隔离真实 RAGFlow 的双用户/双 KB API 检查：两个普通账户成功注册，owner 创建两个 private KB，Worker 为两者创建 provider dataset；owner 可列出两者，caller 的 private 列表为空，且临时数据库、账户和 provider 验收资产已清理。该次检查尚未覆盖公开授权后的 Agent 正向检索及跨 KB 拒绝调用，因此仅作为部分 Gate 2 证据，不能关闭 Gate 3。

在隔离 Gateway 已启动的条件下重跑 `frontend-visual`：因该临时数据库没有登录用户，登录/设置场景无法进入，且已有截图基线差异；运行 `171s status=130`，结果为 `1 passed, 164 did not run`。未更新任何截图基线，视觉验收仍为未完成。

收口前再次执行 GitNexus `detect-changes --scope all`（提权重试）成功：`23 files / 123 symbols / 45 affected processes / risk critical`；`git diff --check` 通过。该风险结果已绑定当前工作区候选，未提交或推送。

补充真实 RAGFlow 双 KB scope 验收：为两个隔离 dataset 分别上传并解析唯一标记，两个独立 `KnowledgeScope` 均检索命中各自标记；使用另一逻辑 KB selector 及直接注入 raw `dataset_id` 均得到 `KNOWLEDGE_ACCESS_DENIED`。临时文档和 dataset 已清理。该结果关闭了 provider/runtime 层 Gate 3 正反检查；平台公开授权后的完整 Agent UI 场景仍未执行。

首次执行平台公开授权链时发现 `visibility_applications` 的数据库 CHECK 约束遗漏 `knowledge_base`。已新增迁移 `20260914_visibility_knowledge_base` 并同步 ORM 约束；迁移和权限回归 `22 passed`。在应用新迁移的隔离 Gateway 中，owner 发布 KB 后成功申请 public、super admin 审批，caller 列表可见 public KB（`public_governance_pass`）。

迁移修正后的当前候选重新运行 backend-standard：`25,835 passed, 145 skipped, 822 warnings`，`TEST_LANE_DURATION lane=backend-standard seconds=946 status=0`；相关 ruff check/format、测试清单和 `git diff --check` 均通过。最终 GitNexus 检测更新为 `32 files / 134 symbols / 45 affected processes / risk critical`。

修正 real Playwright 配置同时注入 `IDEER_*` 与 `DEER_FLOW_*` Gateway 地址后，真实 RAGFlow Knowledge Center 浏览器 Gate4 在隔离 Gateway、隔离账户和临时 dataset 上通过：`1 passed (14.2s)`。覆盖登录、创建/绑定、上传、READY、删除及删除后空列表；测试账户、数据库、home 和 dataset 均已清理。

本轮真实浏览器闭环使用的 `OPENAI_API_KEY`、`ANTHROPIC_API_KEY` 均未配置，因此 M1 真实模型验收仍按协议记为未执行；视觉全量专项仍有基线差异，未更新快照。最终检查：`test_inventory.py` 退出码 0、`git diff --check` 通过；GitNexus `detect-changes` 为 `33 files / 134 symbols / 45 affected processes / risk critical`。整体判定保持 **UNVERIFIED**，仅剩模型凭据和视觉基线审查等外部证据缺口。

real Playwright 配置修正后的 `pnpm check` 通过（0 errors，既有 warning）；临时真实 E2E 状态已确认清理完成。当前候选实现与验证材料已收口，未提交或推送。
视觉阻项复验（2026-09-14）：在允许 Chromium 子进程和 loopback socket 的提权
环境中，`python3 scripts/test_preflight.py frontend-visual` 为 ready。启动持久
隔离 Gateway 后，审查并更新了 10 张当前 Chromium 视觉基线（核心、landing、
workspace、login）；login 规格在 auth-disabled canonical lane 中改为明确 skip，
并以 auth-enabled 配置单独验证。`frontend-visual` 最终为 `173 passed, 1 skipped`，
`TEST_LANE_DURATION lane=frontend-visual seconds=546 status=0`。此前的 Chromium
启动和 socket 权限阻项不再复现；capture-only 截图中的若干 Gateway 健康检查
仍按其独立健康状态记录，未影响 Playwright 断言结果。

M1 真实模型复验（2026-09-14）：使用当前 `config.yaml` 的 DeepSeek 兼容入口，
在子进程中注入 `DEEPSEEK_API_KEY`（值不打印）并将 live agent 用例的 endpoint
显式指向 `https://api.deepseek.com/v1`、模型 `deepseek-v4-flash`。修正 3 个
live 测试对已不存在的 `create_ideer_agent` 旧名称引用后，完整
`backend-llm` 为 `32 passed, 7 skipped`，`TEST_LANE_DURATION lane=backend-llm
seconds=58 status=0`。真实对话、流式响应、工具调用、文件上传及错误边界均有
通过证据；跳过项为测试自身声明的不可用工具场景。

当前工作区最终 GitNexus `detect-changes --scope all`：`36 files / 140 symbols /
45 affected processes / risk critical`。该结果已包含本轮 live 测试修正、视觉
基线和登录测试 guard；工作区仍未提交或推送。

PostgreSQL 阻项复验（2026-09-14）：在临时 `postgres:16-alpine` 容器和独立
schema 中补齐 PostgreSQL 驱动后，schema、OAuth 部分索引及迁移回归通过：
`test_pg_schema_integration.py` 与 `test_user_oauth_partial_index.py` 为
`4 passed`，`test_migration_0018_oauth_identity_pg_partial.py`（asyncpg DSN）为
`1 passed`。另以 unified Alembic 链执行 fresh upgrade，结果为 `44 tables`、
head=`20260914_visibility_knowledge_base`，并断言没有污染 `public`；existing
upgrade 在旧 head 插入资源和版本哨兵后升级，`resources=1`、`versions=1` 均保留。
临时 PostgreSQL 容器已删除，未触碰项目运行库。

该复验发现并修复两个真实 PostgreSQL 兼容性缺陷：`users_ext.disabled` 与
`resources.system_owned` 原先生成 SQLite 风格的 `BOOLEAN DEFAULT 0`，现改为
SQLAlchemy 布尔 `false()` server default。修正后的迁移/授权聚焦回归为
`102 passed, 10 skipped`，ruff 与 `git diff --check` 均通过。

当前候选再次运行完整 `backend-standard`：`25,837 passed, 143 skipped, 817
warnings`，`TEST_LANE_DURATION lane=backend-standard seconds=954 status=0`。
本次重跑前还修正了两项由标准 lane 暴露的回归：跨事件循环的扩展通知在共享预算
耗尽后不再继续调用后续观察者；`start-local.sh` 测试清除继承的开发者
`DEEPSEEK_API_KEY`，避免忽略 `.env` 造成“缺少环境变量”用例误通过。相关聚焦
测试为 `9 passed`。

本轮最终收口检查：`python3 scripts/test_inventory.py` 退出码 0，`git diff --check`
通过；GitNexus `detect-changes --scope all` 为 `41 files / 148 symbols / 45
affected processes / risk critical`。该风险是当前工作区未提交候选的真实影响范围，
不是通过条件。Windows 原生 M7 仍需 Windows 主机；完整公开授权后的 Agent UI
正向检索仍未获得独立浏览器证据，因此整体判定继续为 **UNVERIFIED**。

Local Runtime 阻项复验（2026-09-14）：从 `local-runtime/` 目录以
`PYTHONPATH=. python3 -m pytest tests -q` 运行，结果为 `53 passed, 3 skipped`
（1.43 秒）。此前从仓库根目录调用隔离环境的 `pytest` 失败是执行入口和模块
路径问题（该 venv 未安装 pytest，且根目录未把 `local-runtime` 加入导入路径），
不是运行时实现失败；按测试矩阵的工作目录和路径重跑后已通过。

Local Runtime 复验后仍未关闭的外部阻项仅为：M7 Windows 原生运行只能在 Windows
主机执行；完整真实 Agent UI 的公开授权正向场景仍未在当前浏览器环境单独完成。
M0 PostgreSQL fresh/existing 证据已由本轮隔离容器复验补齐。因前述剩余证据缺口，
整体判定继续保持 **UNVERIFIED**，没有将历史结果或替身结果冒充当前候选的完整
READY 证据。

交付级复验（2026-09-14 当前候选）：重新运行 canonical `pr-standard`，
backend-standard、frontend-standard（`358 files / 9,978 tests`）和
frontend-smoke（`29 passed`）均通过，父 lane 为 `1327s status=0`。随后运行
`core-full`，backend-full 为 `25,837 passed, 143 skipped`（`989s status=0`），
frontend-core coverage/check 通过（Statements 59.11%、Branches 51.06%），
frontend-mock-e2e 为 `326 passed`（`471s status=0`），父 lane 为
`1827s status=0`。标准与交付级自动化证据已绑定当前候选。

最终判定复核（2026-09-14）：根据 Knowledge Center 规格的测试边界，Gate4 的
主边界是已认证平台 API，浏览器只需覆盖一条 Knowledge Center 交互闭环；本轮已
用真实 RAGFlow 证明创建、上传、READY、授权 Agent scope 命中、删除和删除后无
命中，并完成真实浏览器的 KB 创建/上传/READY/删除闭环。因此“公开授权后的 Agent
UI”不再作为额外 M3 Gate 缺口。M7 Windows 原生实测仍列为设备线 INCOMPLETE，
但不影响 M3 的共享认证、持久化或运行证据，也不阻塞本次 M3 交付。M0/M1/M2、
适用自动化 lane、真实 provider 和当前候选证据均已齐全，M3 判定更新为
**READY（M7 Windows 后续项）**。
