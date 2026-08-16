# 架构概览

本文档提供 iDeer 后端架构的全面概述。

## 系统架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              客户端 (浏览器)                               │
└─────────────────────────────────┬────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          Nginx (端口 2026)                                │
│                    统一反向代理入口                                         │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  /api/langgraph/*  →  Gateway LangGraph 兼容运行时 (8001)         │  │
│  │  /api/*            →  Gateway REST API (8001)                      │  │
│  │  /*                →  前端 (3000)                                   │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┬────────────────────────────────────────┘
                                   │
           ┌───────────────────────┴───────────────────────┐
           │                                               │
           ▼                                               ▼
┌─────────────────────────────────────────────┐ ┌─────────────────────┐
│              Gateway API                    │ │     前端             │
│              (端口 8001)                     │ │    (端口 3000)      │
│                                             │ │                     │
│  - LangGraph 兼容的 runs/threads API        │ │  - Next.js 应用     │
│  - 嵌入式 Agent 运行时                       │ │  - React UI         │
│  - SSE 流式传输                              │ │  - 聊天界面          │
│  - 检查点持久化                              │ │                     │
│  - 模型 / MCP / 技能 / 上传 / 产物           │ │                     │
│  - 线程清理                                  │ │                     │
└─────────────────────────────────────────────┘ └─────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         共享配置                                           │
│  ┌─────────────────────────┐  ┌────────────────────────────────────────┐ │
│  │      config.yaml        │  │      extensions_config.json            │ │
│  │  - 模型                  │  │  - MCP 服务器                         │ │
│  │  - 工具                  │  │  - 技能状态                           │ │
│  │  - 沙箱                  │  │                                        │ │
│  │  - 摘要                  │  │                                        │ │
│  └─────────────────────────┘  └────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

## 组件详情

### Gateway 嵌入式 Agent 运行时

Agent 运行时嵌入在 FastAPI Gateway 中，基于 LangGraph 构建，用于稳健的多 Agent 工作流编排。Nginx 将 `/api/langgraph/*` 重写为 Gateway 原生 `/api/*` 路由，因此公共 API 无需独立运行 LangGraph 服务器就能兼容 LangGraph SDK 客户端。

**入口点**: `packages/harness/ideer/agents/lead_agent/agent.py:make_lead_agent`

**主要职责**:
- Agent 创建与配置
- 线程状态管理
- 中间件链执行
- 工具执行编排
- SSE 流式实时响应

**图谱注册**: `langgraph.json` 保留供工具、Studio 或直接 LangGraph 服务器兼容使用。它不是默认服务入口点；脚本和 Docker 部署运行 Gateway 嵌入式运行时。

```json
{
  "agent": {
    "type": "agent",
    "path": "ideer.agents:make_lead_agent"
  }
}
```

### Gateway API

提供 REST 端点以及公共 LangGraph 兼容的 `/api/langgraph/*` 运行时路由的 FastAPI 应用。

**入口点**: `app/gateway/app.py`

**路由模块**:
- `models.py` - `/api/models` - 模型列表与详情
- `thread_runs.py` / `runs.py` - `/api/threads/{id}/runs`, `/api/runs/*` - LangGraph 兼容的运行与流式传输
- `mcp.py` - `/api/mcp` - MCP 服务器配置
- `resources.py` - `/api/resources` - 技能、智能体、工作流统一资源目录（canonical；旧 `/api/skills`、`/api/agents`、`/api/workflows` 路由已删除）
- `uploads.py` - `/api/threads/{id}/uploads` - 文件上传
- `threads.py` - `/api/threads/{id}` - LangGraph 删除后本地 iDeer 线程数据清理
- `artifacts.py` - `/api/threads/{id}/artifacts` - 产物服务
- `suggestions.py` - `/api/threads/{id}/suggestions` - 跟进建议生成

Web 对话删除流程：首先通过 LangGraph 兼容路由删除 Gateway 管理的线程状态，然后 Gateway 的 `threads.py` 路由通过 `Paths.delete_thread_dir()` 删除 iDeer 管理的文件系统数据。

### Agent 架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           make_lead_agent(config)                        │
└────────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                             中间件链                                      │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ 1. ThreadDataMiddleware  - 初始化 workspace/uploads/outputs      │   │
│  │ 2. UploadsMiddleware     - 处理上传文件                          │   │
│  │ 3. SandboxMiddleware     - 获取沙箱环境                          │   │
│  │ 4. SummarizationMiddleware - 上下文缩减（如启用）                │   │
│  │ 5. TitleMiddleware       - 自动生成标题                          │   │
│  │ 6. TodoListMiddleware    - 任务跟踪（plan_mode 时启用）          │   │
│  │ 7. ViewImageMiddleware   - 视觉模型支持                          │   │
│  │ 8. ClarificationMiddleware - 处理澄清请求                        │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              Agent 核心                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐   │
│  │      模型        │  │      工具        │  │     系统提示词        │   │
│  │  (来自工厂)      │  │  (已配置 + MCP +  │  │  (含技能)            │   │
│  │                  │  │   内置)          │  │                      │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 线程状态

`ThreadState` 继承 LangGraph 的 `AgentState` 并添加额外字段：

```python
class ThreadState(AgentState):
    # AgentState 中的核心状态
    messages: list[BaseMessage]

    # iDeer 扩展
    sandbox: dict             # 沙箱环境信息
    artifacts: list[str]      # 生成的文件路径
    thread_data: dict         # {workspace, uploads, outputs} 路径
    title: str | None         # 自动生成的对话标题
    todos: list[dict]         # 任务跟踪（计划模式）
    viewed_images: dict       # 视觉模型图像数据
```

### 沙箱系统

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           沙箱架构                                        │
└─────────────────────────────────────────────────────────────────────────┘

                      ┌─────────────────────────┐
                      │    SandboxProvider      │ （抽象）
                      │  - acquire()            │
                      │  - get()                │
                      │  - release()            │
                      └────────────┬────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                                         │
              ▼                                         ▼
┌─────────────────────────┐              ┌─────────────────────────┐
│  LocalSandboxProvider   │              │  AioSandboxProvider     │
│  (packages/harness/ideer/sandbox/local.py) │  (packages/harness/ideer/community/)       │
│                         │              │                         │
│  - 单例实例             │              │  - 基于 Docker           │
│  - 直接执行             │              │  - 隔离容器              │
│  - 开发使用             │              │  - 生产使用              │
└─────────────────────────┘              └─────────────────────────┘

                      ┌─────────────────────────┐
                      │        Sandbox          │ （抽象）
                      │  - execute_command()    │
                      │  - read_file()          │
                      │  - write_file()         │
                      │  - list_dir()           │
                      └─────────────────────────┘
```

**虚拟路径映射**:

| 虚拟路径 | 物理路径 |
|---------|---------|
| `/mnt/user-data/workspace` | `backend/.ideer/threads/{thread_id}/user-data/workspace` |
| `/mnt/user-data/uploads` | `backend/.ideer/threads/{thread_id}/user-data/uploads` |
| `/mnt/user-data/outputs` | `backend/.ideer/threads/{thread_id}/user-data/outputs` |
| `/mnt/skills` | `ideer/skills/` |

### 工具系统

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            工具来源                                       │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│    内置工具          │  │  配置工具           │  │    MCP 工具         │
│  (packages/harness/ideer/tools/)       │  │  (config.yaml)      │  │  (extensions.json)  │
├─────────────────────┤  ├─────────────────────┤  ├─────────────────────┤
│ - present_files     │  │ - web_search        │  │ - github            │
│ - ask_clarification │  │ - web_fetch         │  │ - filesystem        │
│ - view_image        │  │ - bash              │  │ - postgres          │
│                     │  │ - read_file         │  │ - brave-search      │
│                     │  │ - write_file        │  │ - puppeteer         │
│                     │  │ - str_replace       │  │ - ...               │
│                     │  │ - ls                │  │                     │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
           │                       │                       │
           └───────────────────────┴───────────────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │   get_available_tools() │
                       │  (packages/harness/ideer/tools/__init__)  │
                       └─────────────────────────┘
```

### 模型工厂

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           模型工厂                                        │
│                   (packages/harness/ideer/models/factory.py)            │
└─────────────────────────────────────────────────────────────────────────┘

config.yaml:
┌─────────────────────────────────────────────────────────────────────────┐
│ models:                                                                  │
│   - name: gpt-4                                                         │
│     display_name: GPT-4                                                 │
│     use: langchain_openai:ChatOpenAI                                    │
│     model: gpt-4                                                        │
│     api_key: $OPENAI_API_KEY                                            │
│     max_tokens: 4096                                                    │
│     supports_thinking: false                                            │
│     supports_vision: true                                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │   create_chat_model()   │
                       │  - name: str            │
                       │  - thinking_enabled     │
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │   resolve_class()       │
                       │  (反射系统)              │
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │   BaseChatModel         │
                       │  (LangChain 实例)       │
                       └─────────────────────────┘
```

**支持的供应商**:
- OpenAI (`langchain_openai:ChatOpenAI`)
- Anthropic (`langchain_anthropic:ChatAnthropic`)
- DeepSeek (`langchain_deepseek:ChatDeepSeek`)
- 通过 LangChain 集成的自定义供应商

### MCP 集成

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          MCP 集成                                        │
│                    (packages/harness/ideer/mcp/manager.py)              │
└─────────────────────────────────────────────────────────────────────────┘

extensions_config.json:
┌─────────────────────────────────────────────────────────────────────────┐
│ {                                                                        │
│   "mcpServers": {                                                       │
│     "github": {                                                         │
│       "enabled": true,                                                  │
│       "type": "stdio",                                                  │
│       "command": "npx",                                                 │
│       "args": ["-y", "@modelcontextprotocol/server-github"],           │
│       "env": {"GITHUB_TOKEN": "$GITHUB_TOKEN"}                          │
│     }                                                                   │
│   }                                                                     │
│ }                                                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │  MultiServerMCPClient   │
                       │  (langchain-mcp-adapters)│
                       └────────────┬────────────┘
                                    │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
        ┌───────────┐        ┌───────────┐        ┌───────────┐
        │  stdio    │        │   SSE     │        │   HTTP    │
        │ 传输方式  │        │ 传输方式  │        │ 传输方式  │
        └───────────┘        └───────────┘        └───────────┘
```

### 技能系统

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           技能系统                                        │
│                     (packages/harness/ideer/skills/loader.py)           │
└─────────────────────────────────────────────────────────────────────────┘

目录结构:
┌─────────────────────────────────────────────────────────────────────────┐
│ skills/                                                                  │
│ ├── public/                        # 公共技能（Git 管理）                 │
│ │   ├── pdf-processing/                                                 │
│ │   │   └── SKILL.md                                                    │
│ │   ├── frontend-design/                                                │
│ │   │   └── SKILL.md                                                    │
│ │   └── ...                                                             │
│ └── custom/                        # 自定义技能（gitignored）            │
│     └── user-installed/                                                 │
│         └── SKILL.md                                                    │
└─────────────────────────────────────────────────────────────────────────┘

SKILL.md 格式:
┌─────────────────────────────────────────────────────────────────────────┐
│ ---                                                                      │
│ name: PDF 处理                                                          │
│ description: 高效处理 PDF 文档                                            │
│ license: MIT                                                            │
│ allowed-tools:                                                          │
│   - read_file                                                           │
│   - write_file                                                          │
│   - bash                                                                │
│ ---                                                                      │
│                                                                          │
│ # 技能指令                                                               │
│ 注入到系统提示词中的内容...                                               │
└─────────────────────────────────────────────────────────────────────────┘
```

### 请求流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        请求流程示例                                       │
│                    用户发送消息给 Agent                                   │
└─────────────────────────────────────────────────────────────────────────┘

1. 客户端 → Nginx
   POST /api/langgraph/threads/{thread_id}/runs
   {"input": {"messages": [{"role": "user", "content": "你好"}]}}

2. Nginx → Gateway API (8001)
   `/api/langgraph/*` 被重写为 Gateway 的 LangGraph 兼容 `/api/*` 路由

3. Gateway 嵌入式运行时
   a. 加载/创建线程状态
   b. 执行中间件链：
      - ThreadDataMiddleware: 设置路径
      - UploadsMiddleware: 注入文件列表
      - SandboxMiddleware: 获取沙箱
      - SummarizationMiddleware: 检查 token 限制
      - TitleMiddleware: 如需要则生成标题
      - TodoListMiddleware: 加载待办事项（计划模式）
      - ViewImageMiddleware: 处理图片
      - ClarificationMiddleware: 检查是否需要澄清

   c. 执行 Agent：
      - 模型处理消息
      - 可能调用工具（bash, web_search 等）
      - 工具通过沙箱执行
      - 结果添加到消息中

   d. 通过 SSE 流式响应

4. 客户端接收流式响应
```

## 数据流

### 文件上传流程

```
1. 客户端上传文件
   POST /api/threads/{thread_id}/uploads
   Content-Type: multipart/form-data

2. Gateway 接收文件
   - 验证文件
   - 存储到 .ideer/threads/{thread_id}/user-data/uploads/
   - 如果是文档：通过 markitdown 转换为 Markdown

3. 返回响应
   {
     "files": [{
       "filename": "doc.pdf",
       "path": ".ideer/.../uploads/doc.pdf",
       "virtual_path": "/mnt/user-data/uploads/doc.pdf",
       "artifact_url": "/api/threads/.../artifacts/mnt/.../doc.pdf"
     }]
   }

4. 下次 Agent 运行
   - UploadsMiddleware 列出文件
   - 将文件列表注入到消息中
   - Agent 可通过 virtual_path 访问
```

### 线程清理流程

```
1. 客户端通过 LangGraph 兼容的 Gateway 路由删除对话
   DELETE /api/langgraph/threads/{thread_id}

2. Web UI 执行 Gateway 清理
   DELETE /api/threads/{thread_id}

3. Gateway 删除本地 iDeer 管理文件
   - 递归删除 .ideer/threads/{thread_id}/
   - 目录不存在时视为无操作
   - 无效的线程 ID 在访问文件系统前被拒绝
```

### 配置重载

```
1. 客户端更新 MCP 配置
   PUT /api/mcp/config

2. Gateway 写入 extensions_config.json
   - 更新 mcpServers 部分
   - 文件 mtime 变化

3. MCP 管理器检测到变化
   - get_cached_mcp_tools() 检查 mtime
   - 如已变化：重新初始化 MCP 客户端
   - 加载更新后的服务器配置

4. 下次 Agent 运行使用新工具
```

## 安全考虑

### 沙箱隔离

- Agent 代码在沙箱边界内执行
- 本地沙箱：直接执行（仅开发使用）
- Docker 沙箱：容器隔离（推荐生产使用）
- 文件操作中的路径遍历防护

### API 安全

- 线程隔离：每个线程有独立的数据目录
- 文件验证：上传检查路径安全性
- 环境变量解析：密钥不存储在配置文件中

### MCP 安全

- 每个 MCP 服务器运行在独立进程中
- 环境变量在运行时解析
- 可独立启用/禁用每个服务器

## 性能考虑

### 缓存

- MCP 工具缓存，通过文件 mtime 失效
- 配置加载一次，文件变更时重新加载
- 技能在启动时解析一次，缓存到内存

### 流式传输

- SSE 用于实时响应流式传输
- 减少首 token 延迟
- 使长时间操作可见进度

### 上下文管理

- 摘要中间件在接近限制时缩减上下文
- 可配置触发条件：token 数、消息数或比例
- 保留最新消息，同时摘要较旧的消息
