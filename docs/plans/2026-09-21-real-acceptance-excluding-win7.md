# 除 Windows 7 外的真实验收执行计划

日期：2026-09-21。核对基线：develop@094e7cc9。本文件是待执行计划，不是通过报告。

## 目标和边界

串行完成 Gate 7、Gate 8、M9 真实 MCP Evidence、故障归零多附件 TTFT 和必要数据库回归。Windows 7 单独保留 unexecuted；现代 Windows 专属能力若本机不可执行，同样单列，不能用 Linux 代替。即使本计划全部通过，也只能宣布“除 Windows 7 及明确列出的平台项外，真实验收完成”，不能宣布正式收口或自动进入 M10。不实现 M10—M12，不自动发布、部署或清理原工作区。

执行顺序：P0 固定候选及环境 → P1 建立采证资产 → P2 Gate 7 → P3 Gate 8 → P4 M9 → P5 TTFT → P6 统一复核。任一门禁阻塞不阻止独立工作包推进，但 Gate 8 正式通过依赖同一候选 Gate 7 通过。

## 已有证据和必须纠正的口径

- 现有 RAGFlow Gate 7/8 各 1 项 provider probe 通过，另有 artifact 项跳过；这不等于完整 Gate 7/8 通过。
- AIO 1.9.3 已启动真实容器并调用配置中的 DeepSeek，空附件 Run 成功进入澄清流程；这只证明该路径可运行，不证明完整隔离策略和业务产物验收通过。
- 该次运行使用手工对齐目录哈希的数据库副本。正式验收必须使用正常导入/发布形成的资源和一致性检查，不能继续直接改哈希绕过目录一致性问题。
- 历史 AIO 原始结果是首 SSE 852.4 ms、总运行 23503.7 ms、正文 TTFT=null；现报告台账中的“8.5s / 24.3s”与原始输出不一致。执行时修正文档并注明旧原始文件已清理，重新采集可保留证据，不补造旧记录。
- PostgreSQL 5 项实测已通过，保留历史结论；它们只覆盖列出的 schema/OAuth/migration 用例，不代表已有知识版本、快照和评估数据的全量升级保留已经验证。
- M5/M9 专项报告仍引用旧分支；最终更新当前候选部分，保留历史记录及其真实提交号。

## P0：固定候选和可复现环境

1. 记录 git HEAD、status、worktree、镜像 digest、解释器/依赖锁、服务版本。保护所有原工作区；实现验收脚本或修复时使用独立分支/工作区。
2. 执行 `UV_CACHE_DIR=/tmp/deer-flow-uv-cache make doctor`。只报告缺项，不输出 config.yaml、环境变量或 Cookie 全文。读取当前目录配置中的 DeepSeek/RAGFlow，记录模型名和配置摘要；密钥仍留在本地私有配置。
3. 建立独立验收数据库、用户、KB、RAGFlow dataset、Agent/Skill、Local Runtime 设备及输出目录，使用唯一验收批次前缀。通过正式 API/导入/发布路径建立资源，确认重新启动不报 CatalogConsistencyError。若现有导入链有缺陷，先按 TDD 修复，不手写数据库状态伪装正常准备流程。
4. AIO 使用 1.9.3 的确定 digest。检查所有 bind source 存在；遗留 `/home/wangyh/fault-zeroing` 必须指向实际选定测试目录。空目录仅适用于空附件用例，不能充当真实业务资料。
5. 用独立端口启动 Gateway、前端和实际代理路径；本地 socket 受限时在允许 socket 的环境重跑相同命令。由启动进程 PID、端口和配置摘要确认连接的是本轮服务，避免误连原 8001 服务。
6. 执行登录、健康检查、资源一致性、AIO 文件读写/只读 Skill/越界拒绝，以及 DeepSeek 最小请求。AIO 检查覆盖实际工具 API；不能只凭容器启动通过判定隔离完整。

退出：新环境可重启、资源来自正常业务流程、代理可访问、所有资源可追踪并可只清理本轮创建项。

## P1：采证工具和夹具

复用以下真实入口，必要时补充 orchestration 脚本，不新增证据体系：

- `backend/tests/gate7_acceptance.py`、`backend/tests/test_knowledge_gate7_live.py`。
- `backend/tests/gate8_acceptance.py`、`backend/tests/test_knowledge_gate8_live.py`。
- `frontend/tests/e2e/real/knowledge-evidence-gate7.spec.ts` 及 Gate 8 real 浏览器场景。
- `scripts/benchmark/{multi_attachment_ttft,generate_fixtures,summarize_ttft}.py`。
- `docs/local-runtime/{TEST_MATRIX,SECURITY_MODEL,IMPLEMENTATION_INVENTORY}.md`。

现有 validator 不是业务场景执行器。新增脚本放 `scripts/acceptance/`，测试放正式测试目录；建议按 prepare、gate7、gate8、m9、ttft、collect、cleanup 拆分命令。此命令接口是待实现交付物，不能当作现有命令运行。

采证目录使用持久的 `<evidence-root>/<candidate>/<batch>/`，不能只放 dev-log 或随手删除的 /tmp。每项记录 candidate_commit、批次、真实服务标记、场景名、命令、开始/结束 ISO 时间、耗时、退出码、断言、实际步骤、Run/Thread/Tool Call 标识、脱敏响应和附件索引。浏览器保存 trace、截图和必要网络证据；不得保留 Cookie、密钥、完整 Prompt 或业务附件正文。真实证据的留存位置必须可供验收者访问。

Gate 8 严格按现有 schema 生成：证据文件必须存在、同一 candidate_commit、对应 scenario、real_execution=true、非空 observed_steps 和该场景要求的 observations。provider 内部身份/地址不进入业务 artifact；受限环境配置与业务证据分离。Gate 7 矩阵即使 validator 较宽松也必须有实际执行证据，不能靠填写 passed 获得通过。

所有脚本/修复先完成并提交，再固定验收 SHA。采证不修改该 checkout；报告后续提交明确写“验收对象 SHA”。Gate 8 校验在被测 SHA 的 checkout 上运行，避免为追随报告 HEAD 而篡改 artifact 提交号。

## P2：Gate 7 检索证据

准备两个实际角色不同的用户、两个隔离 KB、可区分的 Rev1/Rev2 文档和固定唯一片段。核对真实角色值。通过真实模型的 Agent、Workflow/Sub-Agent 发起检索，并从平台持久化 Evidence/Receipt 读取结果。

严格执行现有 16 行：agent、workflow_subagent、two_users_two_kbs、revoked_access、revision_freeze_provider_outage、empty_hit、truncated、retry、duplicate、archive_failure、forged_citation、history_without_receipt、mixed_web、streaming、loading_error_restricted、keyboard。

重点断言：

- Run → Tool Call → KB → Revision → Document → Chunk 每一跳可持久化回放，委托成功/失败/取消/重试绑定正确，跨 Run 查询不串用。
- Rev2 发布后旧 Run 仍显示 Rev1 归档片段；撤权、伪造引用、缺失回执均受限；模型和浏览器不获得 provider 凭据、内部地址或不必要标识。
- 浏览器实际点击 evidence 引用，片段逐字等于该 Run 归档；键盘开关和焦点恢复通过。
- 故障场景在隔离真实系统上制造受控 provider 不可用、归档写入失败等条件，记录注入点和恢复步骤；不将 mock 代替真实场景。无法安全构造的场景保持 unexecuted。

命令（变量由 P1 执行器填入真实值）：

```bash
DEER_FLOW_RUN_LIVE_TESTS=1 UV_CACHE_DIR=/tmp/deer-flow-uv-cache uv run --project backend pytest backend/tests/test_knowledge_gate7_live.py -q -s
cd frontend
PLAYWRIGHT_SKIP_WEB_SERVER=1 pnpm exec playwright test tests/e2e/real/knowledge-evidence-gate7.spec.ts
```

后端环境包含 RAGFLOW_GATE7_DATASET_ID、RAGFLOW_GATE7_RUN_ID、RAGFLOW_GATE7_SOURCE_CHAIN_JSON、RAGFLOW_GATE7_MATRIX_JSON、RAGFLOW_GATE7_EXPECTED_SNIPPET；浏览器包含 E2E_GATE7_THREAD_ID、E2E_GATE7_RUN_ID、E2E_GATE7_EXPECTED_SNIPPET，并按现有 real harness 配置登录与 base URL。

退出：16 行和真实来源链、浏览器证据均 passed，无 artifact 跳过；输出同候选 Gate 7 总 artifact 供 P3 使用。

## P3：Gate 8 检索质量及发布

依次执行 candidate_preparation、trial_retrieval、eval_case_management、profile_ab_comparison、matching_candidate_evaluation、formal_publish、run_snapshot_freeze、rbac_and_secrecy、failure_recovery、browser_review。

固定问题、预期平台文档 ID 和去重排名，独立重算 Expected Document Hit、Recall@K、MRR，并对照现有实现定义。观察 Revision、manifest、Profile、评估集版本、结果之间绑定；分别改变候选内容、Profile 或评估集验证旧结果不能授权新候选。覆盖失败阻止发布、匹配合格结果允许发布、发布后新旧 Run 快照、权限撤销、任务重试、服务重启和历史评估回放。

```bash
DEER_FLOW_RUN_LIVE_TESTS=1 UV_CACHE_DIR=/tmp/deer-flow-uv-cache uv run --project backend pytest backend/tests/test_knowledge_gate8_live.py -q -s
bash scripts/run-test-lane.sh frontend-real
```

填写 RAGFLOW_GATE8_DATASET_ID、RAGFLOW_GATE8_ARTIFACT_JSON，以及 E2E_GATE8_KB_SLUG、E2E_GATE8_EXPECTED_SNIPPET、E2E_GATE8_EXPECTED_EVIDENCE、E2E_GATE8_EXPECTED_COMPARISON、E2E_GATE8_EXPECTED_GATE_FEEDBACK。浏览器须观察真实 evidence、A/B、门禁反馈、loading/empty/error/restricted 与键盘状态。

退出：10 场景、同候选 Gate 7 前置、严格 artifact validator 和浏览器均通过。完整 frontend-real 中其他跳过项单列，不能声称全 lane 已通过。

## P4：M9 真实 Local Runtime → MCP → Evidence

1. 启动实际 Local Runtime 进程，经平台正常配对和用户同意绑定测试设备；使用真实 MCP 服务进程/HTTP 服务，其工具操作隔离测试目录，并可用唯一执行标记验证有没有真的运行。stdio 与项目支持的 HTTP 路径分别验证。
2. 真实模型 Agent 发起 MCP 工具调用，必须走 Server → Local Task → Local Runtime → MCP；核对任务、设备回执、Tool Receipt、Run Evidence 的身份及持久化重放。直接调用 MCP 或单测内部 broker 不算本项通过。
3. 覆盖无设备、离线、撤销、能力不匹配、本地 DENY、用户拒绝，以及批准/取消竞争、超时、重复请求、重启。除观察拒绝回执，还要检查 MCP 执行标记证明未执行、未重复执行。
4. 使用专用测试秘密验证设置/读取/轮换/删除和跨输出分片脱敏，扫描参数、日志、回执、浏览器；不使用生产秘密作泄漏实验。Linux 仅证明其实际存储后端；Credential Manager 留给现代 Windows/Win7 平台实测。
5. Python 成功、非零退出、超时、取消、后代进程清理；Tray 在可用真实桌面上操作连接状态、roots、同意/拒绝、暂停、审计、关闭窗口和显式退出。无桌面时列为独立外部依赖，不能用 Tk mock 算通过。
6. 追加同一 Run 内先知识检索、再本地工具调用的组合场景，核对权限交集、两类回执、取消后的状态和重启历史回放。不扩展 Workflow ExecutionTarget。

回归：`bash scripts/run-test-lane.sh local-runtime`。Windows CI 结果独立记录；本机 Linux 通过不等于现代 Windows CI/原生桌面通过。

退出：完整真实派发链、拒绝/竞争矩阵和混合 Run 证据通过；平台未执行项逐条列出。

## P5：故障归零附件 TTFT

先完成测量有效性，再进行成本较高的批量真实模型实验。

1. 核对固定 benchmark Prompt 与故障归零实际工作流。当前脚本没有 --prompt 参数；如需可配置业务问题，先按 TDD 增补诊断接口，不能在计划中假设现有参数存在。空附件澄清必须记录为无正文样本；不把 SSE、工具结果或澄清事件当正文。
2. 核对事件分类：本次助手非空正文才计入；用户/空片段/工具结果/其他 Run 不计；HTTP 200 中 SSE error 为失败。记录上传、准备、首 SSE、首工具、首正文、浏览器首次显示，逐一说明计时起点。日志中的 llm_ttft 不能直接当端到端 TTFT。
3. 用生成夹具检验上传/转换/测量链，但先验证每种文件可被真实解析器读取。现有 generator 的极简 PDF 不能直接视为有效 PDF 证据。准备 TXT/MD/PDF/DOCX/XLSX 和重名文件，保存清单、大小、哈希、预期可读标记。
4. 真实慢问题使用用户指定故障归零资料及相同业务问题、模型参数、Agent/Skill 版本和实际代理路径。先确认可使用的确切文件集合；历史自动审批曾阻止未明确授权的附件外发，如仍受阻，仅对具体文件清单与配置中的 DeepSeek 目的地请求确认，继续独立验收工作。
5. 先 0/1 文件试跑，验证附件可访问且测量可解释，再执行 0/1/5/10，每个条件至少 5 个有效样本。产品附件上限固定为 10；20 文件不属于本轮产品验收范围，也不修改该上限。每次创建新 Thread/Run，固定资料组合、模型和 Agent 版本；冷/热 AIO、缓存、连接状态分别记录，不能混成一组。所有失败和无正文样本保留并计入尝试数，不靠反复重试隐去失败率。
6. 预先约定显著波动判据（建议正文 TTFT 最大/最小 >2 或变异系数 >0.3），触发后扩到 20 个有效样本，记录扩样理由。持续澄清没有有效正文时停止补样，诊断原因并报告未获得该条件 TTFT。
7. 只在复现慢样本后考虑优化；若比较优化，固定 baseline/candidate，按 AB/BA 交错配对，每条件至少 5 对，同时验证附件访问和结果正确性。未有配对收益的上传并发/预上传继续延期。

现有命令模板：

```bash
UV_CACHE_DIR=/tmp/deer-flow-uv-cache uv run --project backend python scripts/benchmark/multi_attachment_ttft.py --base-url "$BASE_URL" --thread-id "$THREAD_ID" --assistant-id "$AGENT_ID" --count "$COUNT" --fixture-dir "$FIXTURE_DIR" --label "$LABEL" --output "$RESULT_JSON" --timeout 240
python3 scripts/benchmark/summarize_ttft.py "$MERGED_RESULT_JSON"
```

认证由私有 TTFT_COOKIE 和所需 CSRF header 注入，禁用命令追踪，报告不展开秘密。AGENT_ID 应正常导入后实际查询，不能假设临时库保留原 UUID。每次单独执行并合并原始 results。现有 summarizer 不能假定支持配对统计/浏览器指标，必要时补充。输出中位数、范围、失败率、无正文比例、每对差值和附件访问断言；保留真实路径浏览器显示时间。

退出：诊断正确性、文件矩阵和真实样本/阻塞结论可复测。没有慢样本或有效配对不得宣布性能已解决；优化可延期而诊断能力完成。

## P6：最终复核、数据库和交接

- SQLite fresh/existing、单 migration head、旧版本/快照/评估结果保留；PostgreSQL 使用专用容器复核适用项，asyncpg 用 postgresql+asyncpg DSN，psycopg 用 postgresql DSN。只有产品代码或数据库变化才扩展重跑历史已通过用例；未覆盖的数据升级保留补真实观察。
- 新增/移动测试后 `python3 scripts/test_inventory.py`；lane 自动 preflight。行为修复执行 RED → 最小修改 → GREEN → 聚焦 lint/typecheck，编辑符号前 GitNexus impact，HIGH/CRITICAL 先报告，UNKNOWN 补源码核验。提交前 detect_changes，不接受未展开 truncation。
- 最终候选执行 `bash scripts/run-test-lane.sh pr-standard`，分别记录 local-runtime、backend-standard、frontend-standard、frontend-smoke 和父级 TEST_LANE_DURATION/退出状态，以 runner 当时定义为准。
- 执行 backend-blocking-io；受影响引用/质量页的 frontend-visual、frontend-a11y、真实浏览器场景；涉及类型/构建修改执行 `cd frontend && pnpm test:full`。不默认执行 core-full。
- 产品代码变化后重跑受影响真实场景；Gate 8 严格绑定新 SHA，同候选 Gate 7 前置必须实际重采，不能只替换报告提交号。无关报告更新保留被测 SHA，不声称测试了后来的 HEAD。
- 更新 current-branches-closeout-report、M5/M6/M9 当前候选记录、architecture 进展表和相关补丁台账；PATCH-009 保持“数据库前置已验证、补丁 open”。
- 先验证脱敏证据包可被重新校验，再按创建资源清单清理临时服务/设备/dataset/目录。只删除本轮资源；证据包不随环境删除。

最终输出表：Gate 7、Gate 8、M9 真实链及桌面平台项、混合 Run、TTFT 诊断/性能、SQLite/PostgreSQL、各 lane 分别列 passed/failed/unexecuted/incomplete。记录精确命令、候选 SHA、耗时、证据位置、阻塞原因及复测步骤。草稿 PR 可审查，正式收口和进入 M10 仍受 Windows 7 等未完成门禁约束。

## 执行分工与外部输入

Agent 可完成环境安装配置、隔离数据、采证脚本、真实 API/模型/浏览器、MCP 进程、故障注入与恢复、测试、报告和清理。默认单执行者串行。

需要用户或环境提供的内容限定为：真实故障归零材料的确切路径和允许使用范围；遇到既有外发审批限制时的具体授权；若本机缺少真实桌面/现代 Windows，则提供相应访问环境。Win7 完全不进入本计划执行。

按阶段检查点交付，不预承诺服务时延和通过结果：P0/P1 后交付可执行入口与环境清单；P2/P3 后交付知识门禁证据；P4 后交付设备和混合 Run 证据；P5/P6 后交付最终结论。发现缺陷只做本轮验收必需修复，其余另列待办。
