# Knowledge Gate 1 验收报告（Ticket 06 — Receipt / 脱敏 / 断网）

> audience: developers, reviewers, QA, release engineering
> status: binding acceptance record
> last-verified: 2026-09-08
> canonical-path: `docs/testing/knowledge-gate1-acceptance-report.md`
> scope: M1 知识线 Gate 1（AgentPlatform + DeerFlow Runtime + RAGFlow 三环基础链路）,对应 `.scratch/m0-m1-foundation/issues/06-knowledge-smoke-acceptance.md`

## 结论

Gate 1 六项验收中五项通过；第 6 项（后端标准 lane 绿）**incomplete**——全量 lane 被两处与本票
改动无关的既有缺陷阻塞（均在 develop 基线复现，已用 py-spy 定位并记录 §6.1），本票改动的影响面
由聚焦测试（864 passed）覆盖。验收过程中发现并修复一处脱敏缺口（连接错误路径泄漏内部 base URL，见 §2.3）。
断网 leg 在真实断网（公网 DNS 与路由均不可达）下完成全链路验证，chat 模型使用本机 llama.cpp
OpenAI 兼容替身（内网 vLLM/llama.cpp 生产端点尚不可达，替换仅需改 config 的 `base_url`/`model`，协议不变）。

| # | 验收项 | 结果 |
|---|---|---|
| 1 | 每次 `knowledge_search` 调用生成 Tool Receipt 且能在 Run 记录中定位 | PASS |
| 2 | 错误路径脱敏（凭据错误 / dataset 不存在 / 连接错误） | PASS（含一处修复） |
| 3 | 真实断网下启动、登录、Run、知识检索、回答全链路可用 | PASS |
| 4 | 不做项复核：未创建 KnowledgeBase Resource / Revision / Knowledge Center | PASS |
| 5 | 验收报告归档 | 本文档 |
| 6 | 后端标准 lane 绿 | INCOMPLETE（既有缺陷阻塞全量；改动影响面聚焦测试全绿，见 §6） |

## 1. Tool Receipt

验收环境：ticket 04/05 打通的 dev 链路（RAGFlow v0.27.1 compose 栈 + TEI embedding + 原生网关 :8001），
agent 为 canonical Resource `knowledge-smoke-agent`（`e23afe75-b85e-4a84-828d-2748b4524aa5`）。

Run 证据（thread `7a7d1198-c10e-4b05-8aec-e4a2fdfa2819`，`POST /api/threads/{tid}/runs/wait` → HTTP 200）：

- 模型发起 2 次 `knowledge_search` tool call，每个 ToolMessage 的
  `additional_kwargs.deerflow_tool_receipt` 均带完整 receipt：

```json
{"tool_call_id": "call_00_uFNjUkpqAlABViuOktYM3317", "tool_name": "knowledge_search",
 "status": "success", "args_sha256": "ad2ad1b7b1e697e9", "output_sha256": "077099b7c8313934",
 "output_bytes": 725, "created_at": "2026-09-08T15:32:02.166583+00:00"}
```

- Run 记录持久化定位：`GET /api/threads/{tid}/state` → HTTP 200，响应全文含 2 处
  `deerflow_tool_receipt`，与 Run 响应一致（args/output SHA256 逐字节相同）。
- 检索内容真实咬合：ToolMessage 命中 `ideer-knowledge-smoke-facts.md`（score 0.30/0.31），
  最终回答引用 BLUE ORCHID 并带 citation。

错误路径同样有 receipt：§3 的两次错误注入 Run 中，ToolMessage receipt `status=error`。

## 2. 错误路径脱敏

方法：通过 config 热重载注入故障（不重启进程），分别从工具级（venv 直调
`knowledge_search_tool.ainvoke`，模型侧最终可见文本）与 Run 级（完整 Agent Run 载荷）双侧检查。
泄漏扫描针对整份 Run 载荷 JSON，查找：API key（真实/伪造）、内部 base URL、raw dataset ID、
`Traceback`、`SELECT `。

### 2.1 凭据错误（config `api_key` 换成伪造值）

- 模型侧：`Error: <Unauthorized '401: Unauthorized'>`
- 管理员日志：`RAGFlow API rejected a read-only tool request (code=401)`（无 key）
- Run 载荷扫描（thread `f0a93a49-4a7b-4806-8ba5-023bce4dcaf0`）：真实 key、伪造 key、
  base URL、raw dataset ID、Traceback、SQL 全部 clean。

### 2.2 dataset 不存在（config `datasets` 换成全 F UUID）

- 模型侧：`Error: The 1st entry of knowledge_search.datasets was not found or is inaccessible; check config.yaml.`
  （只暴露 allowlist 位置索引，不带 raw dataset ID）
- 管理员日志：`Configured RAGFlow dataset binding could not be resolved (position=1, dataset_id=ffff…, code=None)`
  （raw ID 仅日志侧，供管理员追查，符合知识方案 §51）
- Run 载荷扫描（thread `d3264e5d-f143-4853-9431-0d51911e1c4d`）：伪造/真实 dataset ID、
  key、URL、Traceback、SQL 全部 clean。

### 2.3 连接错误（config `base_url` 指向无监听端口）——验收发现并修复

工具级直调发现模型侧返回
`Error: Unable to connect to RAGFlow (http://localhost:9399): ConnectError: All connection attempts failed`
——内部 base URL 违反票面与知识方案 §51（internal base URL 不面向模型/用户）。

修复（本 ticket 代码变更）：

- `backend/packages/harness/deerflow/community/ragflow/tools.py` `_tool_error` 连接错误分支：
  模型侧只返回 sanitized code —— `Error: RAGFlow knowledge retrieval is unavailable (connection_error: {类型名}).`；
  base URL 与 provider 异常细节仅保留在 `logger.warning`（管理员侧可追查）。
- 回归测试：改写 `test_connection_error_is_english_and_does_not_leak_key` 断言；
  新增 `test_connection_error_does_not_leak_internal_base_url`（断言 endpoint/端口/异常细节不出现在返回文本、
  endpoint 仍出现在日志）。`backend/tests/test_ragflow_tools.py` 36 passed。

trace id：网关 HTTP 层已有 request_id 机制（`app/gateway/app.py` 未处理异常返回
`X-Request-ID` + 通用 envelope，日志按 request_id 关联），满足"sanitized code + trace id"口径。

## 3. 真实断网验收

### 3.1 断网方式

宿主 iptables 需要不可用的 sudo 密码，改用 Docker `--internal` 网络承载整条链路的控制面：
internal 网络无默认路由、嵌入 DNS 无公网上游，容器内"公网 DNS 与路由均不可达"为网络栈事实，
且不影响宿主与其他会话。组件：

- `docker network create --internal airgap`；`ideer-ragflow`、`ideer-ragflow-tei`、`llama-airgap`、`gw-airgap` 四容器接入
- `gw-airgap` 复用 intranet 形态镜像 `ideer-gateway:20260908-00b9ec95`（经 md5 抽查其 backend
  代码与 HEAD 一致；仅将本 ticket 修复的 `tools.py` 以单文件挂载覆盖）
- 数据面：SQLite 一致快照（`sqlite3 backup API`）+ `.ideer/resources`、`.ideer/users` 快照挂载
- chat 模型替身：`ghcr.io/ggml-org/llama.cpp:server` + Qwen3-4B-Instruct-2507 Q4_K_M（`--jinja` 启用 tool calling），
  config 仅含该模型（`base_url: http://llama-airgap:8000/v1`，`use: deerflow.models.patched_openai:PatchedChatOpenAI`）
- `knowledge_search.base_url` 指向 `http://ideer-ragflow:9380`（airgap 网络内容器别名）

### 3.2 断网证据（gw-airgap 容器内）

```text
/proc/net/route: 仅 eth0 子网路由（172.18.0.0/16），无 default
default route present: False
8.8.8.8:443 -> unreachable (OSError) — pass
DNS api.deepseek.com -> unresolved (gaierror) — pass
DNS google.com      -> unresolved (gaierror) — pass
```

### 3.3 断网下全链路（验收脚本 `docker exec gw-airgap … /tmp/airgap-acceptance.py`）

```text
GET  /health                     -> 200 {"status":"healthy",...}          # 启动 leg
POST /api/v1/auth/login/local    -> 200                                   # 登录 leg
POST /api/threads                -> thread 840a4f23-1352-4c15-a23a-251b635a17f5
POST /api/threads/{tid}/runs/wait-> 200 in 124s                           # Run leg
  receipt: knowledge_search status=success args_sha=543b9b7e1c9c3e58
           out_sha=63537fa9c69aad01 bytes=725                      # 检索 leg
  answer: "The secret project codename ... is **BLUE ORCHID** ... [citation:ideer-knowledge-smoke-facts.md]"
leak scan over entire run payload: NONE                          # 回答 leg + 脱敏
ALL PASS
```

断网前置（有网时）还验证了替身模型的真实 tool calling：宿主 Run（thread `010bb0f7`，
`model=intranet-qwen3-4b`）中 Qwen3-4B 主动发起 `knowledge_search`（receipt success，725B）并引用 BLUE ORCHID 回答，191.8s。

### 3.4 生产替身说明

内网 vLLM/llama.cpp 大模型已部署但从本机不可达（10.96.0.x 网段为 VPN 虚拟网卡代答，
HTTP 层无真实服务；Windows 侧探测同样不通）。断网 leg 以同协议本机 llama.cpp 替身执行；
生产切换只改 config 的模型条目（`base_url`/`model`/`api_key`），链路代码无差异。

## 4. 不做项复核

- `ResourceType` 枚举仅 `{skill, agent, workflow}`（`backend/app/agentplatform/resource_models.py:18`），无 knowledge_base 类型
- dev DB `SELECT DISTINCT type FROM resources` → `['agent']`；sqlite_master 无 knowledge/revision 相关表
- 本分支变更集不含任何 Resource Governance / Knowledge Center 文件（ticket 04-06 仅 compose、ragflow 引导、tools 脱敏修复与本报告）

## 5. 归档

本报告即验收归档（docs/testing/）。验收脚手架（airgap 网络与容器）验收后拆除，
复现按 §3.1 配方；llama-server 容器与模型文件保留在本机供复核。

## 6. 测试 lane

- 聚焦（改动影响面）：`tests/test_ragflow_tools.py` + `tests/test_ragflow_client.py` + `tests/unit/models/` → **864 passed**（含新增/改写的连接错误脱敏回归）
- 标准全量 lane：**incomplete**（既有缺陷，详见 §6.1）

### 6.1 标准全量 lane 的执行记录与既有缺陷定性

执行方式与过程（本机，`CI=true` 等价 `make test`，pytest-timeout 180s 硬超时兜底）：

1. `make test` 全量（verbose）→ 停滞 35 分钟无进展，py-spy 定位：
   `tests/test_client_e2e.py::test_stream_completes_without_middleware_errors`（`@requires_llm`）真实调用外部 LLM，
   TLS 握手挂死于慢网络窗口。
2. 重跑 → 卡在同一测试。py-spy 复核为 openai SDK 600s 超时 × 重试。
3. `CI=true`（官方 skip 语义）全量 → 36% 处再次挂死于
   `tests/test_multi_worker_run_ownership.py::test_http_stream_action_non_owner_without_shared_bridge_returns_202`
   （starlette TestClient 等待不结束的流式响应，**单跑同样挂死 = 确定性挂死**）。
4. 排除该文件后 → 又挂死于同区域的 `tests/test_stream_get_action_rejected.py::test_get_with_cancel_action_is_rejected`。
5. 最终轮（pytest-timeout 兜底）跑至 36% 后在上述同区域超时退出。

**基线对照（证明与本票改动无关）**：`git stash` 本票全部改动后，在 develop 工作树上复跑
`test_multi_worker_run_ownership.py -k non_owner_without_shared_bridge`（150s timeout 杀死，同样挂死）与
`tests/integration/api/test_client_e2e.py`（同样 Timeout，exit 1）——**两处失败均为既有缺陷**：

- 缺陷 A：stream action HTTP 层多个测试确定性挂死（TestClient 等待永不结束的流式响应）。
- 缺陷 B：`client e2e` 系列约 14+ 个测试真实调用外部 LLM 但缺少 `requires_llm` 标注
  （文件 docstring 声明"Tests that call the LLM are marked requires_llm"，实际未标注），
  无网络/无凭据环境下必败。另有一个收集期环境泄漏使 `requires_llm` skipif 在全量收集下失效
  （单文件收集时正确 skip），该机制问题需独立修复。

以上均不在 Gate 1 范围内，建议作为独立缺陷工单（缺陷 A 建议补 `requires_llm`/mock 标注，
缺陷 B 建议修复环境泄漏或为标准 lane 提供 `-p no:cacheprovider` 级别的隔离）。本票改动的影响面
由聚焦测试（864 passed）与影响分析（`_tool_error` 单一上游调用方，LOW risk）覆盖。

## 附录：验收命令与退出码

```text
工具级注入（venv 直调）           exit 0，输出见 §2.1-2.3
Run 级注入 runs/wait             HTTP 200（thread f0a93a49 / d3264e5d），泄漏扫描 clean
断网验收脚本（容器内）            exit 0，VERDICT: ALL PASS
聚焦测试（改动影响面）            864 passed, 21.76s
基线对照（stash 后 develop 树）   挂点1 单测 143（超时杀死）、client_e2e exit 1（同败）
标准全量 lane                    exit 1 / 挂死（既有缺陷，§6.1）
config 还原                      diff 与验收前备份一致
```
