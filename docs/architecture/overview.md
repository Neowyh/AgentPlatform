# CLAUDE.md

> audience: developers, architects<br>
> status: current<br>
> owner: engineering maintainers<br>
> last-verified: 2026-07-15<br>
> canonical-path: `docs/architecture/overview.md`

本文件为 Claude Code（claude.ai/code）在本仓库中处理代码时提供指导。

## 项目概览

iDeer 是一个基于 LangGraph 的 AI 超级智能体系统，采用全栈架构。后端提供“超级智能体”能力，包含沙箱执行、持久化记忆、子智能体委托以及可扩展工具集成，且所有能力都运行在线程级隔离环境中。

**架构**：

- **Gateway API**（端口 8001）：REST API 加嵌入式 LangGraph 兼容智能体运行时
- **Frontend**（端口 3000）：Next.js Web 界面
- **Nginx**（端口 2026）：统一反向代理入口
- **Provisioner**（端口 8002，Docker 开发模式下可选）：仅在沙箱配置为 provisioner/Kubernetes 模式时启动

**运行时**：

- `make dev`、Docker 开发环境和生产环境都会通过 Gateway 中的 `RunManager` + `run_agent()` + `StreamBridge`（`packages/harness/ideer/runtime/`）运行智能体运行时。Nginx 将该运行时暴露在 `/api/langgraph/*`，并重写到 Gateway 原生的 `/api/*` 路由。

**项目结构**：

```text
ideer/
├── Makefile                    # 根目录命令（check、install、dev、stop）
├── config.yaml                 # 主应用配置
├── extensions_config.json      # MCP 服务器和技能配置
├── backend/                    # 后端应用（当前目录）
│   ├── Makefile               # 仅后端命令（dev、gateway、lint）
│   ├── langgraph.json         # LangGraph Studio 图配置
│   ├── packages/
│   │   └── harness/           # ideer-harness 包（导入：ideer.*）
│   │       ├── pyproject.toml
│   │       └── ideer/
│   │           ├── agents/            # LangGraph 智能体系统
│   │           │   ├── lead_agent/    # 主智能体（工厂 + 系统提示词）
│   │           │   ├── middlewares/   # 10 个中间件组件
│   │           │   ├── memory/        # 记忆抽取、队列、提示词
│   │           │   └── thread_state.py # ThreadState 模式
│   │           ├── sandbox/           # 沙箱执行系统
│   │           │   ├── local/         # 本地文件系统 provider
│   │           │   ├── sandbox.py     # 抽象 Sandbox 接口
│   │           │   ├── tools.py       # bash、ls、read/write/str_replace
│   │           │   └── middleware.py  # 沙箱生命周期管理
│   │           ├── subagents/         # 子智能体委托系统
│   │           │   ├── builtins/      # general-purpose、bash 智能体
│   │           │   ├── executor.py    # 后台执行引擎
│   │           │   └── registry.py    # 智能体注册表
│   │           ├── tools/builtins/    # 内置工具（present_files、ask_clarification、view_image）
│   │           ├── mcp/               # MCP 集成（工具、缓存、客户端）
│   │           ├── models/            # 支持 thinking/vision 的模型工厂
│   │           ├── skills/            # 技能发现、加载、解析
│   │           ├── config/            # 配置系统（app、model、sandbox、tool 等）
│   │           ├── community/         # 社区工具（tavily、jina_ai、firecrawl、image_search、aio_sandbox）
│   │           ├── reflection/        # 动态模块加载（resolve_variable、resolve_class）
│   │           ├── utils/             # 工具函数（network、readability）
│   │           └── client.py          # 嵌入式 Python 客户端（iDeerClient）
│   ├── app/                   # 应用层（导入：app.*）
│   │   ├── gateway/           # FastAPI Gateway API
│   │   │   ├── app.py         # FastAPI 应用
│   │   │   └── routers/       # FastAPI 路由模块（models、mcp、memory、skills、uploads、threads、artifacts、agents、suggestions、channels）
│   │   └── channels/          # IM 平台集成
│   ├── tests/                 # 测试套件
│   └── docs/                  # 文档
├── frontend/                   # Next.js 前端应用
└── skills/                     # 智能体技能目录
    ├── public/                # 公共技能（提交到仓库）
    └── custom/                # 自定义技能（gitignored）
```

## 重要开发指南

### 文档更新策略

**关键要求：每次代码变更后都必须更新 README.md 和 CLAUDE.md**

进行代码变更时，必须更新相关文档：

- 面向用户的变更（功能、安装、使用说明）更新 `README.md`
- 开发相关变更（架构、命令、工作流、内部系统）更新 `CLAUDE.md`
- 始终保持文档与代码库同步
- 确保所有文档准确且及时

## 命令

**根目录**（完整应用）：

```bash
make check      # 检查系统要求
make install    # 安装所有依赖（前端 + 后端）
make dev        # 启动所有服务（Gateway + Frontend + Nginx），并预检查 config.yaml
make start      # 在本地启动生产模式服务
make stop       # 停止所有服务
```

**后端目录**（仅后端开发）：

```bash
make install    # 安装后端依赖
make dev        # 以 reload 模式运行 Gateway API（端口 8001）
make gateway    # 仅运行 Gateway API（端口 8001）
make test       # 运行全部后端测试
make lint       # 使用 ruff 检查
make format     # 使用 ruff 格式化代码
```

与 Docker/provisioner 行为相关的回归测试：

- `tests/test_docker_sandbox_mode_detection.py`（从 `config.yaml` 识别模式）
- `tests/test_provisioner_kubeconfig.py`（kubeconfig 文件/目录处理）

边界检查（harness 到 app 的导入防火墙）：

- `tests/test_harness_boundary.py`：确保 `packages/harness/ideer/` 永远不会从 `app.*` 导入

CI 会通过 [.github/workflows/backend-unit-tests.yml](../../.github/workflows/backend-unit-tests.yml) 在每个 Pull Request 上运行这些回归测试。

## 架构

### Harness / App 分层

后端被拆分为两层，并具有严格的依赖方向：

- **Harness**（`packages/harness/ideer/`）：可发布的智能体框架包（`ideer-harness`）。导入前缀为 `ideer.*`。包含智能体编排、工具、沙箱、模型、MCP、技能、配置等构建和运行智能体所需的一切。
- **App**（`app/`）：不发布的应用代码。导入前缀为 `app.*`。包含 FastAPI Gateway API 和 IM 渠道集成（飞书、Slack、Telegram、钉钉）。

**依赖规则**：App 可以导入 ideer，但 ideer 绝不能导入 app。该边界由 `tests/test_harness_boundary.py` 强制执行，并在 CI 中运行。

**导入约定**：

```python
# Harness 内部
from ideer.agents import make_lead_agent
from ideer.models import create_chat_model

# App 内部
from app.gateway.app import app
from app.channels.service import start_channel_service

# App → Harness（允许）
from ideer.config import get_app_config

# Harness → App（禁止，由 test_harness_boundary.py 强制）
# from app.gateway.routers.uploads import ...  # ← 会导致 CI 失败
```

### 智能体系统

**Lead Agent**（`packages/harness/ideer/agents/lead_agent/agent.py`）：

- 入口：`make_lead_agent(config: RunnableConfig)`，注册在 `langgraph.json`
- 通过 `create_chat_model()` 动态选择模型，支持 thinking/vision
- 通过 `get_available_tools()` 加载工具，组合沙箱、内置、MCP、社区和子智能体工具
- 通过 `apply_prompt_template()` 生成系统提示词，包含技能、记忆和子智能体说明

**ThreadState**（`packages/harness/ideer/agents/thread_state.py`）：

- 在 `AgentState` 基础上扩展：`sandbox`、`thread_data`、`title`、`artifacts`、`todos`、`uploaded_files`、`viewed_images`
- 使用自定义 reducer：`merge_artifacts`（去重）、`merge_viewed_images`（合并/清空）

**运行时配置**（通过 `config.configurable`）：

- `thinking_enabled`：启用模型扩展思考
- `model_name`：选择指定 LLM 模型
- `is_plan_mode`：启用 TodoList 中间件
- `subagent_enabled`：启用任务委托工具

### 中间件链

Lead-agent 中间件在 `packages/harness/ideer/agents/middlewares/tool_error_handling_middleware.py`（`build_lead_runtime_middlewares`）和 `packages/harness/ideer/agents/lead_agent/agent.py`（`_build_middlewares`）中按严格追加顺序组装：

1. **ThreadDataMiddleware**：在用户隔离范围下创建线程级目录（`backend/.ideer/users/{user_id}/threads/{thread_id}/user-data/{workspace,uploads,outputs}`）；通过 `get_effective_user_id()` 解析 `user_id`（无认证模式回退到 `"default"`）；Web UI 删除线程时，现在会在 LangGraph 删除线程之后，由 Gateway 清理本地线程目录
2. **UploadsMiddleware**：跟踪新上传文件并注入对话
3. **SandboxMiddleware**：获取沙箱，并将 `sandbox_id` 存储到状态中
4. **DanglingToolCallMiddleware**：为缺少响应的 AIMessage tool_calls 注入占位 ToolMessage（例如用户中断导致），原始 provider tool-call payload 仅保留在 `additional_kwargs["tool_calls"]`
5. **LLMErrorHandlingMiddleware**：在后续中间件/工具阶段运行前，将 provider/模型调用失败规范化为可恢复、面向 assistant 的错误
6. **GuardrailMiddleware**：通过可插拔 `GuardrailProvider` 协议做工具调用前授权（可选，在配置中 `guardrails.enabled` 时启用）。逐个评估工具调用，拒绝时返回错误 ToolMessage。三类 provider 选项：内置 `AllowlistProvider`（零依赖）、OAP 策略 provider（如 `aport-agent-guardrails`）或自定义 provider。设置、用法和 provider 实现方式见 [docs/GUARDRAILS.md](../../backend/docs/GUARDRAILS.md)
7. **SandboxAuditMiddleware**：在工具执行继续之前，对沙箱 shell/文件操作进行安全审计日志记录
8. **ToolErrorHandlingMiddleware**：将工具异常转换为错误 `ToolMessage`，让运行可以继续而不是中止
9. **SummarizationMiddleware**：接近 token 限制时进行上下文压缩（可选）
10. **TodoListMiddleware**：通过 `write_todos` 工具进行任务跟踪（可选，在 plan_mode 下启用）
11. **TokenUsageMiddleware**：在启用 token 跟踪时记录 token 用量指标（可选）；子智能体用量仅在 token 用量启用时按 `tool_call_id` 缓存，并按消息位置而非消息 id 合并回发起调度的 AIMessage
12. **TitleMiddleware**：在第一次完整交换后自动生成线程标题，并在提示标题模型之前规范化结构化消息内容
13. **MemoryMiddleware**：将对话排队用于异步记忆更新（过滤为用户消息 + 最终 AI 回复）
14. **ViewImageMiddleware**：在 LLM 调用前注入 base64 图片数据（取决于是否支持 vision）
15. **DeferredToolFilterMiddleware**：在启用工具搜索前，对绑定模型隐藏 deferred tool schema（可选）
16. **SubagentLimitMiddleware**：截断模型响应中过量的 `task` 工具调用，以强制执行 `MAX_CONCURRENT_SUBAGENTS` 限制（可选，在 `subagent_enabled` 时启用）
17. **LoopDetectionMiddleware**：检测重复工具调用循环；硬停止响应会同时清空结构化 `tool_calls` 和原始 provider tool-call 元数据，然后强制给出最终文本回答
18. **ClarificationMiddleware**：拦截 `ask_clarification` 工具调用，通过 `Command(goto=END)` 中断（必须放在最后）

### 配置系统

**主配置**（`config.yaml`）：

设置：将 `config.example.yaml` 复制为项目根目录下的 `config.yaml`。

**配置版本管理**：`config.example.yaml` 包含 `config_version` 字段。启动时，`AppConfig.from_file()` 会比较用户版本和示例版本，若用户配置过旧则发出警告。缺失 `config_version` 表示版本 0。运行 `make config-upgrade` 可自动合并缺失字段。变更配置 schema 时，需要提升 `config.example.yaml` 中的 `config_version`。

**配置缓存**：`get_app_config()` 会缓存解析后的配置，但当解析出的配置路径变化或文件 mtime 增大时会自动重新加载。这样 Gateway 和 LangGraph 对 `config.yaml` 的读取可与配置编辑保持一致，无需手动重启进程。

配置优先级：

1. 显式 `config_path` 参数
2. `IDEER_CONFIG_PATH` 环境变量
3. 当前目录（backend/）中的 `config.yaml`
4. 父目录（项目根目录，**推荐位置**）中的 `config.yaml`

以 `$` 开头的配置值会被解析为环境变量（例如 `$OPENAI_API_KEY`）。`ModelConfig` 还声明了 `use_responses_api` 和 `output_version`，因此在继续使用 `langchain_openai:ChatOpenAI` 的同时，也可以显式启用 OpenAI `/v1/responses`。

**扩展配置**（`extensions_config.json`）：

MCP 服务器和技能在项目根目录的 `extensions_config.json` 中共同配置：

配置优先级：

1. 显式 `config_path` 参数
2. `IDEER_EXTENSIONS_CONFIG_PATH` 环境变量
3. 当前目录（backend/）中的 `extensions_config.json`
4. 父目录（项目根目录，**推荐位置**）中的 `extensions_config.json`

### Gateway API（`app/gateway/`）

FastAPI 应用运行在端口 8001，健康检查为 `GET /health`。生产环境可设置 `GATEWAY_ENABLE_DOCS=false` 禁用 `/docs`、`/redoc` 和 `/openapi.json`（默认启用）。

当请求通过端口 2026 的 nginx 进入时，CORS 默认为同源。拆分源或端口转发的浏览器客户端必须通过 `GATEWAY_CORS_ORIGINS`（逗号分隔的精确 origin）显式允许；Gateway 的 `CORSMiddleware` 和 `CSRFMiddleware` 都读取该变量，因此浏览器 CORS 与认证 origin 检查会保持一致。

**路由**：

| Router                                                | Endpoints                                                                                                                                                                                                                                                                                 |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Models**（`/api/models`）                             | `GET /`：列出模型；`GET /{name}`：模型详情                                                                                                                                                                                                                                                           |
| **MCP**（`/api/mcp`）                                   | `GET /config`：获取配置；`PUT /config`：更新配置（保存到 extensions_config.json）                                                                                                                                                                                                                         |
| **Skills**（`/api/skills`）                             | `GET /`：列出技能；`GET /{name}`：详情；`PUT /{name}`：更新启用状态；`POST /install`：从 .skill 归档安装（接受标准可选 frontmatter，如 `version`、`author`、`compatibility`）                                                                                                                                                 |
| **Memory**（`/api/memory`）                             | `GET /`：记忆数据；`POST /reload`：强制重新加载；`GET /config`：配置；`GET /status`：配置 + 数据                                                                                                                                                                                                                 |
| **Uploads**（`/api/threads/{id}/uploads`）              | `POST /`：上传文件（自动转换 PDF/PPT/Excel/Word）；`GET /list`：列表；`DELETE /{filename}`：删除                                                                                                                                                                                                             |
| **Threads**（`/api/threads/{id}`）                      | `DELETE /`：在 LangGraph 删除线程后移除 iDeer 管理的本地线程数据；意外失败会在服务端记录日志，并返回通用 500 detail                                                                                                                                                                                                          |
| **Artifacts**（`/api/threads/{id}/artifacts`）          | `GET /{path}`：提供 artifact；活跃内容类型（`text/html`、`application/xhtml+xml`、`image/svg+xml`）始终强制作为下载附件，以降低 XSS 风险；`?download=true` 对其他文件类型仍会强制下载                                                                                                                                                 |
| **Suggestions**（`/api/threads/{id}/suggestions`）      | `POST /`：生成后续问题；富列表/块模型内容会在 JSON 解析前规范化                                                                                                                                                                                                                                                   |
| **Thread Runs**（`/api/threads/{id}/runs`）             | `POST /`：创建后台 run；`POST /stream`：创建 + SSE 流；`POST /wait`：创建 + 阻塞等待；`GET /`：列出 run；`GET /{rid}`：run 详情；`POST /{rid}/cancel`：取消；`GET /{rid}/join`：加入 SSE；`GET /{rid}/messages`：分页消息 `{data, has_more}`；`GET /{rid}/events`：完整事件流；`GET /../messages`：带反馈的线程消息；`GET /../token-usage`：聚合 token |
| **Feedback**（`/api/threads/{id}/runs/{rid}/feedback`） | `PUT /`：upsert 反馈；`DELETE /`：删除用户反馈；`POST /`：创建反馈；`GET /`：列出反馈；`GET /stats`：聚合统计；`DELETE /{fid}`：删除指定反馈                                                                                                                                                                                   |
| **Runs**（`/api/runs`）                                 | `POST /stream`：无状态 run + SSE；`POST /wait`：无状态 run + 阻塞等待；`GET /{rid}/messages`：按 run_id 获取分页消息 `{data, has_more}`（游标：`after_seq`/`before_seq`）；`GET /{rid}/feedback`：按 run_id 列出反馈                                                                                                        |

**RunManager / RunStore 契约**：
- `RunManager.get()` 是异步方法；直接调用方必须使用 `await`。
- 配置持久化 `RunStore` 时，`get()` 和 `list_by_thread()` 会从 store 补水历史 run。对于相同 `run_id`，内存记录优先，因此任务、abort 和流控制状态会继续绑定到活跃的本地 run。
- `cancel()` 和 `create_or_reject(..., multitask_strategy="interrupt"|"rollback")` 会通过 `RunStore.update_status()` 持久化 interrupted 状态，与普通 `set_status()` 状态迁移保持一致。
- 仅从 store 补水出来的 run 是可读历史。如果当前 worker 没有该 run 的内存任务/控制状态，取消 API 可能返回 409，因为这个 worker 无法停止该任务。

经 nginx 代理：`/api/langgraph/*` → Gateway LangGraph 兼容运行时，其他 `/api/*` → Gateway REST API。

### 沙箱系统（`packages/harness/ideer/sandbox/`）

**接口**：抽象 `Sandbox`，包含 `execute_command`、`read_file`、`write_file`、`list_dir`

**Provider 模式**：`SandboxProvider`，包含 `acquire`、`get`、`release` 生命周期

**实现**：

- `LocalSandboxProvider`：本地文件系统执行。`acquire(thread_id)` 返回线程级 `LocalSandbox`（id 为 `local:{thread_id}`），其 `path_mappings` 将 `/mnt/user-data/{workspace,uploads,outputs}` 和 `/mnt/acp-workspace` 解析到该线程的宿主机目录，因此公共 `Sandbox` API 与 AIO 一样统一遵守 `/mnt/user-data` 契约。`acquire()` / `acquire(None)` 保留旧的通用单例（id 为 `local`），用于没有线程上下文的调用方。线程级沙箱保存在一个由 `threading.Lock` 保护的 LRU 缓存中（默认 256 项）。
- `AioSandboxProvider`（`packages/harness/ideer/community/`）：基于 Docker 的隔离

**虚拟路径系统**：

- 智能体看到：`/mnt/user-data/{workspace,uploads,outputs}`、`/mnt/skills`
- 物理路径：`backend/.ideer/users/{user_id}/threads/{thread_id}/user-data/...`、`ideer/skills/`
- 翻译：`LocalSandboxProvider` 在 acquire 时为 user-data 前缀构建线程级 `PathMapping`；`tools.py` 保留 `replace_virtual_path()` / `replace_virtual_paths_in_command()` 作为纵深防御层（也用于路径校验）。AIO 在容器内部将目录挂载到相同虚拟路径，因此两种实现都可以原生接受 `/mnt/user-data/...`。
- 检测：`is_local_sandbox()` 同时接受 `sandbox_id == "local"`（旧模式/无线程）和 `sandbox_id.startswith("local:")`（线程级）

**沙箱工具**（位于 `packages/harness/ideer/sandbox/tools.py`）：

- `bash`：执行命令，并进行路径翻译和错误处理
- `ls`：目录列表（树形格式，最多 2 层）
- `read_file`：读取文件内容，支持可选行范围
- `write_file`：写入/追加文件，创建目录；默认覆盖，并在面向模型的 schema 中暴露 `append` 参数以支持文件末尾写入
- `str_replace`：子串替换（单次或全部出现）；同一路径串行化的作用域为 `(sandbox.id, path)`，因此隔离沙箱在同一进程内即便虚拟路径相同也不会相互竞争

### 子智能体系统（`packages/harness/ideer/subagents/`）

**内置智能体**：`general-purpose`（除 `task` 外的所有工具）和 `bash`（命令专家）

**执行**：双线程池：`_scheduler_pool`（3 个 worker）+ `_execution_pool`（3 个 worker）

**并发**：`MAX_CONCURRENT_SUBAGENTS = 3`，由 `SubagentLimitMiddleware` 强制执行（在 `after_model` 中截断过量工具调用），超时时间 15 分钟

**流程**：`task()` 工具 → `SubagentExecutor` → 后台线程 → 每 5 秒轮询 → SSE 事件 → 结果

**事件**：`task_started`、`task_running`、`task_completed`/`task_failed`/`task_timed_out`

### 工具系统（`packages/harness/ideer/tools/`）

`get_available_tools(groups, include_mcp, model_name, subagent_enabled)` 会组装：

1. **配置定义的工具**：通过 `resolve_variable()` 从 `config.yaml` 解析
2. **MCP 工具**：来自启用的 MCP 服务器（懒初始化，并通过 mtime 失效缓存）
3. **内置工具**：
   - `present_files`：让输出文件对用户可见（仅限 `/mnt/user-data/outputs`）
   - `ask_clarification`：请求澄清（由 ClarificationMiddleware 拦截并中断）
   - `view_image`：将图片读取为 base64（仅在模型支持 vision 时添加）
   - `setup_agent`：仅引导阶段使用，持久化一个全新自定义智能体的 `SOUL.md` 和 `config.yaml`。仅在 `is_bootstrap=True` 时绑定。
   - `update_agent`：仅自定义智能体使用，在普通聊天中从内部持久化当前智能体对自身 `SOUL.md` / `config.yaml` 的更新（部分更新 + 原子写）。当设置了 `agent_name` 且 `is_bootstrap=False` 时绑定。
4. **子智能体工具**（启用时）：
   - `task`：委托给子智能体（description、prompt、subagent_type）

**社区工具**（`packages/harness/ideer/community/`）：

- `tavily/`：Web 搜索（默认 5 条结果）和网页抓取（4KB 限制）
- `jina_ai/`：通过 Jina reader API 抓取网页，并做 readability 提取
- `firecrawl/`：通过 Firecrawl API 抓取网页

**ACP 智能体工具**：

- `invoke_acp_agent`：调用 `config.yaml` 中配置的外部 ACP 兼容智能体
- ACP launcher 必须是真正的 ACP adapter。标准 `codex` CLI 本身不兼容 ACP；需要配置 wrapper，例如 `npx -y @zed-industries/codex-acp` 或已安装的 `codex-acp` 二进制
- 缺失 ACP 可执行文件时，现在会返回可操作的错误信息，而不是原始 `[Errno 2]`
- 每个 ACP 智能体使用线程级工作区 `{base_dir}/users/{user_id}/threads/{thread_id}/acp-workspace/`。主智能体可通过虚拟路径 `/mnt/acp-workspace/` 以只读方式访问该工作区。在 docker 沙箱模式下，该目录会以只读方式挂载到容器的 `/mnt/acp-workspace`；在本地沙箱模式下，路径翻译由 `tools.py` 处理
- `image_search/`：通过 DuckDuckGo 进行图片搜索

### MCP 系统（`packages/harness/ideer/mcp/`）

- 使用 `langchain-mcp-adapters` 的 `MultiServerMCPClient` 管理多服务器
- **懒初始化**：首次使用时通过 `get_cached_mcp_tools()` 加载工具
- **缓存失效**：通过 mtime 对比检测配置文件变更
- **传输方式**：stdio（基于命令）、SSE、HTTP
- **OAuth（HTTP/SSE）**：支持 token endpoint 流程（`client_credentials`、`refresh_token`），带自动 token 刷新和 Authorization header 注入
- **运行时更新**：Gateway API 保存到 extensions_config.json；LangGraph 通过 mtime 检测

### 技能系统（`packages/harness/ideer/skills/`）

- **位置**：`ideer/skills/{public,custom}/`
- **格式**：包含 `SKILL.md` 的目录（YAML frontmatter：name、description、license、allowed-tools）
- **加载**：`load_skills()` 递归扫描 `skills/{public,custom}` 中的 `SKILL.md`，解析元数据，并从 extensions_config.json 读取启用状态
- **注入**：已启用技能会连同容器路径一起列入智能体系统提示词
- **安装**：`POST /api/skills/install` 将 .skill ZIP 归档解压到 custom/ 目录

### 模型工厂（`packages/harness/ideer/models/factory.py`）

- `create_chat_model(name, thinking_enabled)` 通过反射从配置实例化 LLM
- 支持 `thinking_enabled` 标志和按模型设置的 `when_thinking_enabled` 覆盖
- 支持 vLLM 风格 thinking 开关：通过 `when_thinking_enabled.extra_body.chat_template_kwargs.enable_thinking` 启用 Qwen 推理模型；同时会规范化旧版 `thinking` 配置以保持向后兼容
- 支持 `supports_vision` 标志，用于图片理解模型
- 以 `$` 开头的配置值会被解析为环境变量
- 缺失 provider 模块时，reflection resolver 会给出可操作的安装提示（例如 `uv add langchain-google-genai`）

### vLLM Provider（`packages/harness/ideer/models/vllm_provider.py`）

- `VllmChatModel` 继承 `langchain_openai:ChatOpenAI`，用于 vLLM 0.19.0 OpenAI 兼容端点
- 在完整响应、流式 delta 和后续工具调用轮次中保留 vLLM 非标准的 assistant `reasoning` 字段
- 面向在 vLLM 0.19.0 Qwen 推理模型上通过 `extra_body.chat_template_kwargs.enable_thinking` 启用 thinking 的配置设计，同时也接受旧版 `thinking` 别名

### IM 渠道系统（`app/channels/`）

该系统将外部消息平台（飞书、Slack、Telegram、钉钉）通过 LangGraph Server 连接到 iDeer 智能体。

**架构**：渠道通过 `langgraph-sdk` HTTP 客户端（与前端相同）与 Gateway 通信，确保线程在服务端创建和管理。内部 SDK 客户端会注入进程本地内部认证，以及匹配的 CSRF cookie/header 对，使 Gateway 可以接受来自渠道 worker 的状态变更线程/run 请求，而不依赖浏览器 session cookie。

**组件**：

- `message_bus.py`：异步发布/订阅 hub（`InboundMessage` → queue → dispatcher；`OutboundMessage` → callbacks → channels）
- `store.py`：JSON 文件持久化，将 `channel_name:chat_id[:topic_id]` 映射到 `thread_id`（根会话键为 `channel:chat`，线程会话键为 `channel:chat:topic`）
- `manager.py`：核心 dispatcher：通过 `client.threads.create()` 创建线程，路由命令，使 Slack/Telegram 使用 `client.runs.wait()`，并让飞书通过 `client.runs.stream(["messages-tuple", "values"])` 做增量外发更新
- `base.py`：抽象 `Channel` 基类（start/stop/send 生命周期）
- `service.py`：从 `config.yaml` 管理所有已配置渠道的生命周期
- `slack.py` / `feishu.py` / `telegram.py` / `dingtalk.py`：平台专用实现（`feishu.py` 在内存中跟踪运行中的卡片 `message_id`，并原地 patch 同一张卡片；配置 `card_template_id` 时，`dingtalk.py` 可选使用 AI Card streaming 进行原地更新）

**消息流程**：

1. 外部平台 → Channel 实现 → `MessageBus.publish_inbound()`
2. `ChannelManager._dispatch_loop()` 从队列消费
3. 对于聊天：通过 Gateway 的 LangGraph 兼容 API 查找/创建线程
4. 飞书聊天：`runs.stream()` → 累积 AI 文本 → 发布多次外发更新（`is_final=False`）→ 发布最终外发（`is_final=True`）
5. Slack/Telegram 聊天：`runs.wait()` → 提取最终响应 → 发布外发
6. 飞书渠道先发送一张运行中回复卡片，然后对每次外发更新 patch 同一张卡片（卡片 JSON 设置 `config.update_multi=true` 以满足飞书 patch API 要求）
7. 钉钉 AI Card 模式（配置了 `card_template_id` 时）：`runs.stream()` → 使用初始文本创建卡片 → 通过 `PUT /v1.0/card/streaming` 流式更新 → 在 `is_final=True` 时结束。若创建卡片或 streaming 失败，则回退到 `sampleMarkdown`
8. 对命令（`/new`、`/status`、`/models`、`/memory`、`/help`）：本地处理或查询 Gateway API
9. 外发 → channel callbacks → 平台回复

**配置**（`config.yaml` → `channels`）：

- `langgraph_url`：LangGraph 兼容 Gateway API 基础 URL（默认：`http://localhost:8001/api`）
- `gateway_url`：用于辅助命令的 Gateway API URL（默认：`http://localhost:8001`）
- 在 Docker Compose 中，IM 渠道运行在 `gateway` 容器内，因此 `localhost` 指回该容器。`langgraph_url` 使用 `http://gateway:8001/api`，`gateway_url` 使用 `http://gateway:8001`，或设置 `IDEER_CHANNELS_LANGGRAPH_URL` / `IDEER_CHANNELS_GATEWAY_URL`
- 各渠道配置：`feishu`（app_id、app_secret）、`slack`（bot_token、app_token）、`telegram`（bot_token）、`dingtalk`（client_id、client_secret，可选 `card_template_id` 用于 AI Card streaming）

### 记忆系统（`packages/harness/ideer/agents/memory/`）

**组件**：

- `updater.py`：基于 LLM 的记忆更新，包含事实抽取、空白规范化后的事实去重（比较前裁剪首尾空白）和原子文件 I/O
- `queue.py`：防抖更新队列（按线程去重，可配置等待时间）；入队时捕获 `user_id`，使其可跨越 `threading.Timer` 边界
- `prompt.py`：记忆更新提示词模板
- `storage.py`：基于文件的存储，支持按用户隔离；缓存键为 `(user_id, agent_name)` 元组

**按用户隔离**：

- 记忆按用户存储在 `{base_dir}/users/{user_id}/memory.json`
- 每个智能体的用户级记忆存储在 `{base_dir}/users/{user_id}/agent-memory/{agent_name}/memory.json`
- 自定义智能体定义（`SOUL.md` + `config.yaml`）按用户存储在 `{base_dir}/users/{user_id}/agents/{agent_name}/`，与 `agent-memory/` 中的记忆状态分离。旧的共享布局 `{base_dir}/agents/{agent_name}/` 仍作为未迁移安装的只读回退
- `user_id` 通过 `ideer.runtime.user_context` 中的 `get_effective_user_id()` 解析
- 无认证模式下，`user_id` 默认为 `"default"`（常量 `DEFAULT_USER_ID`）
- 配置中的绝对 `storage_path` 会退出按用户隔离
- **迁移**：运行 `PYTHONPATH=. python scripts/migrate_user_isolation.py`，将旧的 `memory.json`、`threads/` 和 `agents/` 移动到按用户隔离布局。支持 `--dry-run`（预览变更）和 `--user-id USER_ID`（将无归属旧数据分配给某个用户，默认 `default`）。

**数据结构**（存储在 `{base_dir}/users/{user_id}/memory.json`）：

- **用户上下文**：`workContext`、`personalContext`、`topOfMind`（1-3 句摘要）
- **历史**：`recentMonths`、`earlierContext`、`longTermBackground`
- **事实**：离散事实，包含 `id`、`content`、`category`（preference/knowledge/context/behavior/goal）、`confidence`（0-1）、`createdAt`、`source`

**工作流**：

1. `MemoryMiddleware` 过滤消息（用户输入 + 最终 AI 回复），通过 `get_effective_user_id()` 捕获 `user_id`，并将对话连同捕获的 `user_id` 入队
2. 队列防抖（默认 30 秒）、批量更新、按线程去重
3. 后台线程调用 LLM 抽取上下文更新和事实，使用存储的 `user_id`（而不是 contextvar，因为 timer 线程中不可用）
4. 以原子方式应用更新（临时文件 + rename），并使缓存失效；追加前跳过重复事实内容
5. 下一次交互会将前 15 条事实 + 上下文注入系统提示词的 `<memory>` 标签

updater 的聚焦回归覆盖位于 `backend/tests/test_memory_updater.py`。

**配置**（`config.yaml` → `memory`）：

- `enabled` / `injection_enabled`：主开关
- `storage_path`：memory.json 路径（绝对路径会退出按用户隔离）
- `debounce_seconds`：处理前等待时间（默认：30）
- `model_name`：用于更新的 LLM（null = 默认模型）
- `max_facts` / `fact_confidence_threshold`：事实存储限制（100 / 0.7）
- `max_injection_tokens`：提示词注入 token 限制（2000）

### 反射系统（`packages/harness/ideer/reflection/`）

- `resolve_variable(path)`：导入模块并返回变量（例如 `module.path:variable_name`）
- `resolve_class(path, base_class)`：导入并按基类校验类

### 配置 Schema

**`config.yaml`** 关键部分：

- `models[]`：LLM 配置，包含 `use` 类路径、`supports_thinking`、`supports_vision`、provider 专用字段
- vLLM 推理模型应使用 `ideer.models.vllm_provider:VllmChatModel`；对于 Qwen 风格 parser，优先使用 `when_thinking_enabled.extra_body.chat_template_kwargs.enable_thinking`，iDeer 也会规范化旧版 `thinking` 别名
- `tools[]`：工具配置，包含 `use` 变量路径和 `group`
- `tool_groups[]`：工具逻辑分组
- `sandbox.use`：沙箱 provider 类路径
- `skills.path` / `skills.container_path`：技能目录的宿主机路径和容器路径
- `title`：自动标题生成（enabled、max_words、max_chars、prompt_template）
- `summarization`：上下文摘要（enabled、触发条件、保留策略）
- `subagents.enabled`：子智能体委托主开关
- `memory`：记忆系统（enabled、storage_path、debounce_seconds、model_name、max_facts、fact_confidence_threshold、injection_enabled、max_injection_tokens）

**`extensions_config.json`**：

- `mcpServers`：服务器名称到配置的映射（enabled、type、command、args、env、url、headers、oauth、description）
- `skills`：技能名称到状态（enabled）的映射

两者都可通过 Gateway API 端点或 `iDeerClient` 方法在运行时修改。

### 嵌入式客户端（`packages/harness/ideer/client.py`）

`iDeerClient` 提供不经过 HTTP 服务、在进程内直接访问全部 iDeer 能力的方式。所有返回类型都与 Gateway API 响应 schema 对齐，因此消费代码在 HTTP 和嵌入模式下可以保持一致。

**架构**：导入与 Gateway API 相同的 `ideer` 模块。共享同一套配置文件和数据目录。没有 FastAPI 依赖。

**智能体对话**：

- `chat(message, thread_id)`：同步方法，按 message-id 累积流式 delta，并返回最终 AI 文本
- `stream(message, thread_id)`：订阅 LangGraph `stream_mode=["values", "messages", "custom"]` 并产出 `StreamEvent`：
  - `"values"`：完整状态快照（title、messages、artifacts）；通过 `messages` 模式已经交付的 AI 文本不会在这里重新合成，以避免重复交付
  - `"messages-tuple"`：逐 chunk 更新；对 AI 文本而言这是 **delta**（按 `id` 拼接可重建完整消息）；工具调用和工具结果各发出一次
  - `"custom"`：从 `StreamWriter` 转发
  - `"end"`：流结束（携带按 message id 去重统计的累计 `usage`）
- 智能体通过 `create_agent()` + `_build_middlewares()` 懒创建，与 `make_lead_agent` 相同
- 支持 `checkpointer` 参数，用于跨轮次持久化状态
- `reset_agent()` 强制重建智能体（例如记忆或技能变更后）
- 完整设计见 [docs/STREAMING.md](../../backend/docs/STREAMING.md)：说明 Gateway 和 iDeerClient 为什么是并行路径、LangGraph 的 `stream_mode` 语义、按 id 去重的不变量以及回归测试策略

**Gateway 等价方法**（替代 Gateway API）：

| Category  | Methods                                                                                         | Return format                                                      |
| --------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Models    | `list_models()`、`get_model(name)`                                                               | `{"models": [...]}`、`{name, display_name, ...}`                    |
| MCP       | `get_mcp_config()`、`update_mcp_config(servers)`                                                 | `{"mcp_servers": {...}}`                                           |
| Skills    | `list_skills()`、`get_skill(name)`、`update_skill(name, enabled)`、`install_skill(path)`           | `{"skills": [...]}`                                                |
| Memory    | `get_memory()`、`reload_memory()`、`get_memory_config()`、`get_memory_status()`                    | dict                                                               |
| Uploads   | `upload_files(thread_id, files)`、`list_uploads(thread_id)`、`delete_upload(thread_id, filename)` | `{"success": true, "files": [...]}`、`{"files": [...], "count": N}` |
| Artifacts | `get_artifact(thread_id, path)` → `(bytes, mime_type)`                                          | tuple                                                              |

**与 Gateway 的关键区别**：Upload 接受本地 `Path` 对象而不是 HTTP `UploadFile`，在复制前拒绝目录路径，并且当文档转换必须在活动事件循环中运行时复用单个 worker。Artifact 返回 `(bytes, mime_type)` 而不是 HTTP Response。新的 Gateway-only 线程清理路由会在 LangGraph 删除线程后删除 `.ideer/threads/{thread_id}`；目前还没有对应的 `iDeerClient` 方法。`update_mcp_config()` 和 `update_skill()` 会自动使缓存的智能体失效。

**测试**：`tests/test_client.py`（77 个单元测试，包含 `TestGatewayConformance`）、`tests/test_client_live.py`（实时集成测试，需要 config.yaml）

**Gateway 一致性测试**（`TestGatewayConformance`）：验证每个返回 dict 的客户端方法都符合对应的 Gateway Pydantic 响应模型。每个测试都会用 Gateway 模型解析客户端输出。如果 Gateway 新增了客户端未提供的必填字段，Pydantic 会抛出 `ValidationError`，CI 会捕获漂移。覆盖：`ModelsListResponse`、`ModelResponse`、`SkillsListResponse`、`SkillResponse`、`SkillInstallResponse`、`McpConfigResponse`、`UploadResponse`、`MemoryConfigResponse`、`MemoryStatusResponse`。

## 开发工作流

### 测试驱动开发（TDD）——强制

**每个新功能或 bug 修复都必须附带单元测试。没有例外。**

- 按现有命名约定 `test_<feature>.py` 在 `backend/tests/` 中编写测试
- 变更前后都运行完整测试套件：`make test`
- 测试必须通过，功能才算完成
- 对轻量级配置/工具模块，优先使用无外部依赖的纯单元测试
- 如果某个模块在测试中导致循环导入问题，在 `tests/conftest.py` 中添加 `sys.modules` mock（参考 `ideer.subagents.executor` 的现有示例）

```bash
# 运行全部测试
make test

# 运行指定测试文件
PYTHONPATH=. uv run pytest tests/test_<feature>.py -v
```

### 运行完整应用

从**项目根目录**执行：

```bash
make dev
```

这会启动所有服务，并在 `http://localhost:2026` 提供应用访问。

**所有启动模式：**

|          | **本地前台**                                     | **本地守护进程**                                                   | **Docker Dev**                                      | **Docker Prod**                     |
| -------- | -------------------------------------------- | ------------------------------------------------------------ | --------------------------------------------------- | ----------------------------------- |
| **Dev**  | `./scripts/serve.sh --dev`<br/>`make dev`    | `./scripts/serve.sh --dev --daemon`<br/>`make dev-daemon`    | `./scripts/docker.sh start`<br/>`make docker-start` | —                                   |
| **Prod** | `./scripts/serve.sh --prod`<br/>`make start` | `./scripts/serve.sh --prod --daemon`<br/>`make start-daemon` | —                                                   | `./scripts/deploy.sh`<br/>`make up` |

| Action      | Local                                       | Docker Dev                                        | Docker Prod                                |
| ----------- | ------------------------------------------- | ------------------------------------------------- | ------------------------------------------ |
| **Stop**    | `./scripts/serve.sh --stop`<br/>`make stop` | `./scripts/docker.sh stop`<br/>`make docker-stop` | `./scripts/deploy.sh down`<br/>`make down` |
| **Restart** | `./scripts/serve.sh --restart [flags]`      | `./scripts/docker.sh restart`                     | —                                          |

**Nginx 路由**：

- `/api/langgraph/*` → Gateway 嵌入式运行时（8001），重写到 `/api/*`
- `/api/*`（其他）→ Gateway API（8001）
- `/`（非 API）→ Frontend（3000）

### 单独运行后端服务

从 **backend** 目录执行：

```bash
# Gateway API
make gateway
```

直接访问（不经过 nginx）：

- Gateway：`http://localhost:8001`

### 前端配置

前端使用环境变量连接后端服务：

- `NEXT_PUBLIC_LANGGRAPH_BASE_URL`：默认 `/api/langgraph`（经 nginx）
- `NEXT_PUBLIC_BACKEND_BASE_URL`：默认空字符串（经 nginx）

从根目录使用 `make dev` 时，前端会自动通过 nginx 连接。

## 关键功能

### 文件上传

支持多文件上传和自动文档转换：

- 端点：`POST /api/threads/{thread_id}/uploads`
- 支持：PDF、PPT、Excel、Word 文档（通过 `markitdown` 转换）
- 复制前拒绝目录输入，因此上传保持全有或全无
- 从活动事件循环调用时，每个请求复用一个转换 worker
- 文件存储在线程隔离目录中
- 单个上传请求中的重复文件名会自动追加 `_N` 后缀重命名，避免后面的文件截断前面的文件
- 智能体通过 `UploadsMiddleware` 接收上传文件列表

详情见 [docs/FILE_UPLOAD.md](../../backend/docs/FILE_UPLOAD.md)。

### Plan Mode

用于复杂多步骤任务的 TodoList 中间件：

- 通过运行时配置控制：`config.configurable.is_plan_mode = True`
- 提供 `write_todos` 工具用于任务跟踪
- 同一时间只有一个任务处于 in_progress，并实时更新

详情见 [docs/plan_mode_usage.md](../../backend/docs/plan_mode_usage.md)。

### 上下文摘要

接近 token 限制时自动进行对话摘要：

- 在 `config.yaml` 的 `summarization` key 下配置
- 触发类型：tokens、messages 或最大输入比例
- 摘要较早消息，同时保留最近消息

详情见 [docs/summarization.md](../../backend/docs/summarization.md)。

### 视觉支持

对于 `supports_vision: true` 的模型：

- `ViewImageMiddleware` 处理对话中的图片
- 将 `view_image_tool` 添加到智能体工具集
- 图片自动转换为 base64 并注入状态

## 代码风格

- 使用 `ruff` 进行 lint 和格式化
- 行长度：240 字符
- Python 3.12+，使用类型标注
- 双引号、空格缩进

## 文档

详细文档见 `docs/` 目录：

- [CONFIGURATION.md](../../backend/docs/CONFIGURATION.md)：配置选项
- [ARCHITECTURE.md](../../backend/docs/ARCHITECTURE.md)：架构详情
- [API.md](../../backend/docs/API.md)：API 参考
- [SETUP.md](../../backend/docs/SETUP.md)：安装指南
- [FILE_UPLOAD.md](../../backend/docs/FILE_UPLOAD.md)：文件上传功能
- [PATH_EXAMPLES.md](../../backend/docs/PATH_EXAMPLES.md)：路径类型和用法
- [summarization.md](../../backend/docs/summarization.md)：上下文摘要
- [plan_mode_usage.md](../../backend/docs/plan_mode_usage.md)：带 TodoList 的 Plan 模式
