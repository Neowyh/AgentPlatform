# iDeer 开发运维手册

> **版本**: v1.0 | **更新日期**: 2026-06-12

---

## 目录

- [1. 架构概览](#1-架构概览)
- [2. 开发环境搭建](#2-开发环境搭建)
- [3. 前端开发指南](#3-前端开发指南)
- [4. 后端开发指南](#4-后端开发指南)
- [5. 新功能开发流程](#5-新功能开发流程)
- [6. 问题定位指南](#6-问题定位指南)
- [7. 部署运维](#7-部署运维)
- [8. 数据库管理](#8-数据库管理)
- [9. 监控与日志](#9-监控与日志)
- [10. 安全机制](#10-安全机制)
- [11. 测试体系](#11-测试体系)
- [12. 扩展开发](#12-扩展开发)
- [附录](#附录)

---

## 1. 架构概览

### 1.1 系统架构图

```
┌──────────────────────────────────────────────────────────────┐
│                        用户浏览器                             │
└─────────────────────────┬────────────────────────────────────┘
                          │ HTTP/HTTPS
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                     nginx (端口 2026)                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐    │
│  │ / → 前端     │  │ /api/* → 后端│  │ /ws → WebSocket   │    │
│  │ (Next.js)   │  │ (FastAPI)    │  │ (SSE/Streaming)   │    │
│  │ 端口 3000    │  │ 端口 8001    │  │                   │    │
│  └─────────────┘  └──────────────┘  └───────────────────┘    │
└──────────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  LLM APIs    │ │  MCP Servers │ │  Sandbox     │
│  (OpenAI等)  │ │  (工具扩展)   │ │  (代码执行)   │
└──────────────┘ └──────────────┘ └──────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    数据库 (SQLite/PostgreSQL)                 │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 技术栈详解

| 层级 | 技术 | 用途 |
|------|------|------|
| **前端** | Next.js 15, React 19, TypeScript | Web 应用框架 |
| **UI 组件** | shadcn/ui, Radix UI | 组件库 |
| **样式** | Tailwind CSS v4 | CSS 框架 |
| **状态管理** | React Context + Hooks | 客户端状态 |
| **国际化** | 自研 i18n（Cookie 持久化） | 多语言支持 |
| **E2E 测试** | Playwright | 端到端测试 |
| **后端框架** | FastAPI (Python 3.12+) | API 服务 |
| **Agent 框架** | LangGraph | Agent 编排引擎 |
| **ORM** | SQLAlchemy 2.0 (async) | 数据库访问 |
| **数据库迁移** | Alembic | Schema 迁移 |
| **数据库** | SQLite / PostgreSQL | 数据持久化 |
| **容器化** | Docker, Docker Compose | 部署 |
| **反向代理** | nginx | 负载均衡、路由 |

### 1.3 数据流图

```
用户输入 → 前端 (Next.js)
    → POST /api/threads/{id}/runs
    → AuthMiddleware (JWT 验证)
    → CSRFMiddleware (CSRF Token 验证)
    → threads router
    → LangGraph Agent 执行
        → Middleware Chain (17 层)
        → Tool 调用 (内置/社区/MCP)
        → LLM API 调用
        → 流式事件写入
    → SSE 流式响应
    → 前端渲染
```

### 1.4 目录结构说明

```
deer-flow/
├── backend/                     # 后端代码
│   ├── app/gateway/             # API 网关 (FastAPI)
│   │   ├── app.py               # 应用工厂
│   │   ├── routers/             # 路由模块 (20个)
│   │   ├── auth/                # 认证子系统
│   │   ├── auth_middleware.py   # 认证中间件
│   │   ├── csrf_middleware.py   # CSRF 中间件
│   │   └── authz.py            # RBAC 权限控制
│   ├── packages/harness/ideer/  # 核心业务逻辑
│   │   ├── agents/              # Agent 系统
│   │   ├── tools/               # 工具系统
│   │   ├── skills/              # 技能系统
│   │   ├── workflows/           # 工作流引擎
│   │   ├── persistence/         # 数据持久层
│   │   ├── sandbox/             # 代码沙盒
│   │   ├── mcp/                 # MCP 客户端
│   │   ├── subagents/           # 子代理系统
│   │   ├── community/           # 社区工具
│   │   └── config/              # 配置系统
│   └── tests/                   # 后端测试
├── frontend/                    # 前端代码
│   ├── src/app/                 # Next.js 路由页面
│   ├── src/components/          # React 组件
│   │   ├── workspace/           # 工作空间组件
│   │   ├── ai-elements/         # AI 元素组件
│   │   └── ui/                  # 基础 UI 组件
│   ├── src/core/                # 核心模块
│   │   ├── auth/                # 认证模块
│   │   ├── threads/             # 对话管理
│   │   ├── agents/              # Agent API
│   │   ├── workflows/           # 工作流 API
│   │   ├── skills/              # 技能 API
│   │   ├── tools/               # 工具 API
│   │   ├── mcp/                 # MCP API
│   │   ├── memory/              # 记忆 API
│   │   ├── admin/               # 管理 API
│   │   └── i18n/                # 国际化
│   └── tests/                   # 前端测试
├── docker/                      # Docker 配置
│   ├── docker-compose.yaml      # 生产环境编排
│   ├── docker-compose-dev.yaml  # 开发环境编排
│   └── nginx/nginx.conf         # nginx 配置
├── config.yaml                  # 运行时配置
├── config.example.yaml          # 配置模板
└── Makefile                     # 构建命令
```

---

## 2. 开发环境搭建

### 2.1 系统要求

| 依赖 | 最低版本 | 说明 |
|------|----------|------|
| Python | 3.12+ | 后端运行环境 |
| Node.js | 20+ | 前端构建 |
| pnpm | 9+ | 前端包管理 |
| uv | 0.4+ | Python 包管理 |
| Docker | 24+ | 容器化部署（可选） |
| PostgreSQL | 15+ | 生产数据库（可选） |

### 2.2 依赖安装

```bash
# 克隆仓库
git clone <repo-url> deer-flow
cd deer-flow

# 后端依赖
cd backend
uv sync
cd ..

# 前端依赖
cd frontend
pnpm install
cd ..
```

### 2.3 配置文件

**主配置文件**: `config.yaml`

从模板创建配置：

```bash
cp config.example.yaml config.yaml
```

**关键配置项**：

```yaml
# 模型配置
models:
  - provider: openai
    model: gpt-4o
    api_key: $OPENAI_API_KEY

# 数据库配置
database:
  backend: sqlite          # memory | sqlite | postgres
  url: sqlite:///data/ideer.db

# 工具配置
tools:
  - name: web_search
    group: web
    use: community.ddg_search
```

**环境变量** (`.env`):

```bash
# LLM API 密钥
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx

# 系统配置
IDEER_PROJECT_ROOT=/path/to/deer-flow
IDEER_HOME=.ideer

# 前端配置
NEXT_PUBLIC_STATIC_WEBSITE_ONLY=false
BETTER_AUTH_SECRET=your-secret-key
```

### 2.4 启动开发服务

```bash
# 使用 Make 命令启动所有服务
make start

# 或分别启动
# 后端
cd backend && uv run uvicorn app.gateway.app:create_app --factory --port 8001

# 前端
cd frontend && pnpm dev
```

访问 `http://localhost:3000` 即可使用。

### 2.5 IDE 配置

**VS Code 推荐扩展**：

- Python (ms-python)
- Pylance
- Tailwind CSS IntelliSense
- ESLint
- Playwright Test for VS Code

**PyCharm / IntelliJ**：

- 配置 Python 解释器指向 `.venv`
- 安装 Tailwind CSS 插件

---

## 3. 前端开发指南

### 3.1 技术栈

- **框架**: Next.js 15 (App Router)
- **语言**: TypeScript 5.x
- **UI 库**: shadcn/ui + Radix UI
- **样式**: Tailwind CSS v4
- **测试**: Playwright (E2E), Vitest (单元)

### 3.2 目录结构

```
frontend/src/
├── app/                          # Next.js App Router
│   ├── (auth)/                   # 认证路由组
│   │   ├── login/page.tsx        # 登录页
│   │   └── setup/page.tsx        # 初始化页
│   └── workspace/                # 工作空间
│       ├── layout.tsx            # 工作空间布局
│       ├── chats/                # 对话页面
│       ├── agents/               # Agent 页面
│       ├── workflows/            # 工作流页面
│       └── admin/                # 管理后台
├── components/
│   ├── workspace/                # 工作空间组件
│   │   ├── input-box.tsx         # 输入框
│   │   ├── workspace-sidebar.tsx # 侧边栏
│   │   ├── messages/             # 消息组件
│   │   ├── artifacts/            # 工件组件
│   │   ├── settings/             # 设置组件
│   │   ├── agents/               # Agent 组件
│   │   └── workflows/            # 工作流组件
│   ├── ai-elements/              # AI 元素组件
│   │   ├── message.tsx           # 消息渲染
│   │   ├── chain-of-thought.tsx  # 思维链
│   │   ├── model-selector.tsx    # 模型选择器
│   │   └── suggestion.tsx        # 后续建议
│   └── ui/                       # 基础 UI (shadcn)
├── core/
│   ├── api/                      # API 客户端
│   ├── auth/                     # 认证模块
│   ├── threads/                  # 对话管理
│   ├── agents/                   # Agent API
│   ├── workflows/                # 工作流 API
│   ├── skills/                   # 技能 API
│   ├── tools/                    # 工具 API
│   ├── mcp/                      # MCP API
│   ├── memory/                   # 记忆 API
│   ├── admin/                    # 管理 API
│   ├── uploads/                  # 文件上传
│   ├── artifacts/                # 工件管理
│   └── i18n/                     # 国际化
└── hooks/                        # 自定义 Hooks
```

### 3.3 路由系统

使用 Next.js App Router，路由文件即页面：

| 路由 | 页面文件 | 说明 |
|------|----------|------|
| `/login` | `app/(auth)/login/page.tsx` | 登录 |
| `/setup` | `app/(auth)/setup/page.tsx` | 初始化 |
| `/workspace/chats/new` | `app/workspace/chats/new/page.tsx` | 新对话 |
| `/workspace/chats/[thread_id]` | `app/workspace/chats/[thread_id]/page.tsx` | 对话详情 |
| `/workspace/agents` | `app/workspace/agents/page.tsx` | Agent 画廊 |
| `/workspace/agents/new` | `app/workspace/agents/new/page.tsx` | 新建 Agent |
| `/workspace/workflows` | `app/workspace/workflows/page.tsx` | 工作流画廊 |
| `/workspace/admin` | `app/workspace/admin/page.tsx` | 管理后台 |

### 3.4 组件库

基于 shadcn/ui 构建，组件位于 `components/ui/`：

- Button, Input, Dialog, Select, Switch, Tabs
- Card, Badge, Tooltip, DropdownMenu
- Sheet, ScrollArea, Separator

自定义业务组件位于 `components/workspace/` 和 `components/ai-elements/`。

### 3.5 状态管理

- **全局状态**: React Context (`AuthProvider`, `I18nProvider`)
- **页面状态**: React Hooks (`useState`, `useReducer`)
- **服务端状态**: 自研 API 客户端 (`core/api/`)
- **Cookie 状态**: 认证 Token、语言偏好

### 3.6 API 调用

API 客户端位于 `core/api/`，每个业务域有独立的 API 模块：

```typescript
// core/threads/api.ts
export async function createThread(): Promise<Thread> { ... }
export async function getThread(id: string): Promise<Thread> { ... }
export async function deleteThread(id: string): Promise<void> { ... }
```

所有 API 调用通过统一的 `fetch` 封装，自动携带认证 Cookie 和 CSRF Token。

### 3.7 国际化

支持两种语言：`en-US`（默认）和 `zh-CN`。

翻译文件：
- `core/i18n/locales/en-US.ts` — 英文翻译
- `core/i18n/locales/zh-CN.ts` — 中文翻译

使用方式：
```typescript
const { t } = useI18n();
return <h1>{t('workspace.welcome.title')}</h1>;
```

### 3.8 样式系统

- 使用 Tailwind CSS 原子类
- 支持 Light/Dark 主题（CSS 变量）
- 响应式断点：sm(640), md(768), lg(1024), xl(1280), 2xl(1536)

---

## 4. 后端开发指南

### 4.1 技术栈

- **框架**: FastAPI 0.115+
- **语言**: Python 3.12+
- **Agent**: LangGraph 0.3+
- **ORM**: SQLAlchemy 2.0 (async)
- **迁移**: Alembic
- **包管理**: uv

### 4.2 目录结构

```
backend/
├── app/gateway/                    # API 网关
│   ├── app.py                      # FastAPI 应用工厂
│   ├── config.py                   # 网关配置
│   ├── deps.py                     # 依赖注入
│   ├── auth_middleware.py          # 认证中间件
│   ├── csrf_middleware.py          # CSRF 中间件
│   ├── authz.py                    # RBAC 权限
│   ├── routers/                    # 路由模块
│   │   ├── auth.py                 # 认证路由
│   │   ├── threads.py              # 对话路由
│   │   ├── runs.py                 # 运行路由
│   │   ├── agents.py               # Agent 路由
│   │   ├── workflows.py            # 工作流路由
│   │   ├── skills.py               # 技能路由
│   │   ├── tools.py                # 工具路由
│   │   ├── mcp.py                  # MCP 路由
│   │   ├── memory.py               # 记忆路由
│   │   ├── admin.py                # 管理路由
│   │   └── ...                     # 其他路由
│   └── auth/                       # 认证子系统
│       ├── jwt.py                  # JWT 处理
│       ├── local_provider.py       # 本地认证
│       ├── password.py             # 密码哈希
│       └── models.py               # 用户模型
└── packages/harness/ideer/         # 核心业务
    ├── agents/                     # Agent 系统
    │   ├── factory.py              # Agent 工厂
    │   ├── features.py             # 运行时特性
    │   ├── lead_agent/             # 主 Agent
    │   └── middlewares/            # 中间件 (20个)
    ├── tools/                      # 工具系统
    │   ├── registry.py             # 工具注册表
    │   ├── tools.py                # 工具加载
    │   ├── builtins/               # 内置工具
    │   └── community/ → ../community/  # 社区工具
    ├── skills/                     # 技能系统
    │   ├── types.py                # 技能类型
    │   ├── parser.py               # SKILL.md 解析
    │   ├── installer.py            # 技能安装
    │   └── storage/                # 存储层
    ├── workflows/                  # 工作流引擎
    │   ├── schema.py               # YAML DSL Schema
    │   ├── executor.py             # 执行器
    │   ├── parser.py               # YAML 解析
    │   └── steps/                  # 步骤执行器
    ├── persistence/                # 持久层
    │   ├── engine.py               # 数据库引擎
    │   ├── base.py                 # ORM 基类
    │   ├── models/                 # ORM 模型
    │   └── migrations/             # Alembic 迁移
    ├── sandbox/                    # 代码沙盒
    │   ├── sandbox_provider.py     # 沙盒提供者
    │   ├── sandbox.py              # 沙盒抽象
    │   └── local/                  # 本地沙盒
    ├── mcp/                        # MCP 客户端
    │   ├── client.py               # MCP 客户端
    │   ├── tools.py                # MCP 工具加载
    │   └── session_pool.py         # 会话池
    ├── subagents/                  # 子代理系统
    │   ├── config.py               # 子代理配置
    │   ├── registry.py             # 子代理注册表
    │   ├── executor.py             # 子代理执行器
    │   └── builtins/               # 内置子代理
    ├── community/                  # 社区工具
    │   ├── ddg_search/             # DuckDuckGo 搜索
    │   ├── tavily/                 # Tavily 搜索
    │   ├── doc_reader/             # 文档解析
    │   ├── code_interpreter/       # 代码执行
    │   └── data_analyzer/          # 数据分析
    └── config/                     # 配置系统
        ├── app_config.py           # 根配置
        ├── model_config.py         # 模型配置
        ├── database_config.py      # 数据库配置
        └── ...                     # 其他配置
```

### 4.3 API 路由

路由定义在 `backend/app/gateway/routers/`，共 20 个路由模块：

| 路由 | 路径前缀 | 功能 |
|------|----------|------|
| auth | `/api/v1/auth` | 登录、注册、用户信息 |
| threads | `/api/threads` | 对话 CRUD |
| runs | `/api/runs` | 运行管理 |
| agents | `/api/agents` | Agent CRUD |
| workflows | `/api/workflows` | 工作流 CRUD |
| skills | `/api/skills` | 技能 CRUD |
| tools | `/api/tools` | 工具列表、测试 |
| mcp | `/api/mcp` | MCP 服务器配置 |
| memory | `/api/memory` | 记忆 CRUD |
| admin | `/api/admin` | 管理后台 |
| uploads | `/api/uploads` | 文件上传 |
| models | `/api/models` | 模型列表 |
| suggestions | `/api/suggestions` | 后续建议 |
| channels | `/api/channels` | IM 渠道 |

### 4.4 中间件系统

**ASGI 中间件栈**（执行顺序）：

1. `AuthMiddleware` — JWT Cookie 验证，fail-closed
2. `CSRFMiddleware` — Double Submit Cookie 模式
3. `CORSMiddleware` — 跨域资源共享
4. 路由处理器

**Agent 中间件链**（17 层）：

```
0. ThreadDataMiddleware     — 沙盒初始化
1. UploadsMiddleware        — 文件上传处理
2. SandboxMiddleware        — 沙盒集成
3. DanglingToolCallMiddleware — 悬空工具调用处理
4. GuardrailMiddleware      — 安全护栏（可选）
5. ToolErrorHandlingMiddleware — 工具错误处理
6. SummarizationMiddleware  — 上下文摘要（可选）
7. DynamicContextMiddleware — 动态上下文注入
8. TodoMiddleware           — 任务列表管理
9. TokenUsageMiddleware     — Token 使用统计
10. TitleMiddleware         — 标题自动生成
11. MemoryMiddleware        — 记忆管理
12. ViewImageMiddleware     — 图片查看（可选）
13. DeferredToolFilterMiddleware — 延迟工具过滤
14. SubagentLimitMiddleware — 子代理限制
15. LoopDetectionMiddleware — 循环检测
16. SafetyFinishReasonMiddleware — 安全终止
17. ClarificationMiddleware — 澄清请求
```

### 4.5 Agent 系统

**Agent 工厂** (`agents/factory.py`):

```python
agent = create_ideer_agent(
    model=llm,
    tools=tools,
    system_prompt="...",
    features=RuntimeFeatures(
        sandbox=True,
        memory=True,
        summarization=True,
        subagent=True,
    ),
)
```

**RuntimeFeatures** 控制中间件的启用：

```python
@dataclass
class RuntimeFeatures:
    sandbox: Union[bool, AgentMiddleware] = True
    memory: Union[bool, AgentMiddleware] = True
    summarization: Union[bool, AgentMiddleware] = True
    subagent: Union[bool, AgentMiddleware] = True
    vision: Union[bool, AgentMiddleware] = True
    auto_title: Union[bool, AgentMiddleware] = True
    guardrail: Union[bool, AgentMiddleware] = False
    loop_detection: Union[bool, AgentMiddleware] = True
```

### 4.6 工具系统

**工具注册** (`tools/registry.py`):

```python
registry = get_tool_registry()
registry.register(ToolInfo(
    name="my_tool",
    description="My custom tool",
    group="custom",
    requires_network=False,
    use="path.to.my_tool:MyTool",
))
```

**工具组**:

| 组名 | 说明 | 示例 |
|------|------|------|
| `web` | 网络搜索 | ddg_search, tavily |
| `file:read` | 文件读取 | read_file, glob |
| `file:write` | 文件写入 | write_file, str_replace |
| `bash` | 命令执行 | bash |
| `document` | 文档处理 | doc_reader |
| `code` | 代码执行 | code_interpreter |

### 4.7 技能系统

**SKILL.md 格式**：

```markdown
---
name: my-skill
description: 技能描述
license: MIT
allowed-tools:
  - web_search
  - read_file
requires-internet: false
---

# 技能指令

在这里编写技能的详细指令...
```

**技能加载流程**：
1. 扫描 `skills/` 目录下的 `SKILL.md` 文件
2. 解析 YAML frontmatter
3. 注册到技能注册表
4. 根据 `allowed-tools` 过滤可用工具

### 4.8 工作流引擎

**YAML DSL Schema** (`workflows/schema.py`):

```python
class WorkflowDef(BaseModel):
    name: str
    description: str = ""
    version: str = "1.0"
    inputs: list[InputDef] = []
    steps: list[StepDef]
    triggers: list[TriggerDef] = []

class StepDef(BaseModel):
    id: str
    type: StepType  # agent | tool | human_review | condition | parallel | loop | retry
    agent: Optional[str] = None
    prompt: Optional[str] = None
    tool: Optional[str] = None
    params: Optional[dict] = None
    condition: Optional[str] = None
    expression: Optional[str] = None
    then: Optional[list[StepDef]] = None
    else_: Optional[list[StepDef]] = None
    steps: Optional[list[StepDef]] = None
    items: Optional[str] = None
    retry: Optional[RetryPolicy] = None
    timeout: Optional[int] = None
```

**变量插值**：

```yaml
- id: step2
  type: agent
  prompt: "分析 {{steps.step1.output.result}} 的数据"
```

### 4.9 数据库

**ORM 模型**：

| 模型 | 表名 | 说明 |
|------|------|------|
| `UserModel` | `users_ext` | 用户扩展信息 |
| `DepartmentModel` | `departments` | 部门 |
| `RunRow` | `runs` | 运行记录 |
| `ThreadMetaRow` | `threads_meta` | 对话元数据 |
| `WorkflowRunRow` | `workflow_runs` | 工作流运行 |
| `FeedbackRow` | `feedback` | 反馈 |

**数据库后端**：

| 后端 | 适用场景 | 配置 |
|------|----------|------|
| `memory` | 开发测试 | `backend: memory` |
| `sqlite` | 单机部署 | `backend: sqlite` |
| `postgres` | 生产多机 | `backend: postgres` |

---

## 5. 新功能开发流程

### 5.1 前端新页面

1. **创建页面文件**: `frontend/src/app/workspace/xxx/page.tsx`
2. **创建组件**: `frontend/src/components/workspace/xxx/`
3. **创建 API 模块**: `frontend/src/core/xxx/api.ts`
4. **创建类型定义**: `frontend/src/core/xxx/types.ts`
5. **添加路由**: 在 `workspace-nav-menu.tsx` 中添加导航入口
6. **添加翻译**: 在 `locales/en-US.ts` 和 `locales/zh-CN.ts` 中添加翻译键

### 5.2 前端新组件

```tsx
// components/workspace/my-component.tsx
"use client";

import { useI18n } from "@/core/i18n/hooks";

interface MyComponentProps {
  title: string;
}

export function MyComponent({ title }: MyComponentProps) {
  const { t } = useI18n();

  return (
    <div className="flex flex-col gap-4">
      <h2>{title}</h2>
      {/* 组件内容 */}
    </div>
  );
}
```

### 5.3 后端新 API

1. **创建路由文件**: `backend/app/gateway/routers/my_router.py`

```python
from fastapi import APIRouter, Depends
from ..authz import require_auth

router = APIRouter(prefix="/api/my-resource", tags=["my-resource"])

@router.get("/")
@require_auth
async def list_resources(user=Depends(get_current_user)):
    return {"items": []}
```

2. **注册路由**: 在 `app/gateway/app.py` 中添加 `app.include_router(my_router.router)`

### 5.4 新工具开发

1. **创建工具目录**: `backend/packages/harness/ideer/community/my_tool/`
2. **实现工具类**:

```python
# community/my_tool/tool.py
from langchain_core.tools import tool

@tool
def my_tool(input: str) -> str:
    """工具描述，AI 会根据此描述决定何时调用"""
    # 工具实现
    return "result"
```

3. **注册到配置**: 在 `config.yaml` 中添加工具配置

```yaml
tools:
  - name: my_tool
    group: custom
    use: community.my_tool.tool
```

### 5.5 新技能开发

1. **创建 SKILL.md**: `skills/custom/my-skill/SKILL.md`

```markdown
---
name: my-skill
description: 我的自定义技能
allowed-tools:
  - web_search
  - read_file
---

# 技能指令

当用户激活此技能时，按以下步骤执行：
1. ...
2. ...
```

2. **测试技能**: 在设置 → 技能中启用并测试

### 5.6 新 Agent 类型

1. **创建 Agent 配置**: 通过 UI 或 API 创建
2. **配置系统提示词**: 定义 Agent 的 SOUL
3. **配置工具和技能**: 选择 Agent 可用的工具和技能
4. **设置可见性**: 私有/部门内/公开

### 5.7 新工作流步骤

1. **创建步骤执行器**: `backend/packages/harness/ideer/workflows/steps/my_step.py`

```python
async def execute_my_step(step: StepDef, state: WorkflowState) -> dict:
    """执行自定义步骤"""
    # 步骤实现
    return {"output": "result"}
```

2. **注册步骤类型**: 在 `schema.py` 的 `StepType` 枚举中添加
3. **在执行器中路由**: 在 `executor.py` 中添加步骤分发逻辑

---

## 6. 问题定位指南

### 6.1 日志系统

**日志配置**: `config.yaml` 中的 `log_level` 字段

```yaml
log_level: INFO  # DEBUG | INFO | WARNING | ERROR
```

**日志位置**:
- 后端日志: stdout/stderr（Docker 日志或终端输出）
- 前端日志: 浏览器开发者工具 Console

### 6.2 前端调试

**浏览器开发者工具**:

1. **Console**: 查看 JavaScript 错误和日志
2. **Network**: 查看 API 请求和响应
3. **React DevTools**: 组件树和状态检查
4. **Application**: Cookie、LocalStorage 检查

**常见问题**:

| 现象 | 排查方向 |
|------|----------|
| 白屏 | 检查 Console 错误，确认 JS 加载正常 |
| API 401 | 检查 Cookie 中的 `access_token` 是否存在 |
| API 403 | 检查 CSRF Token，确认请求头包含 `X-CSRF-Token` |
| 样式异常 | 检查 Tailwind 类名，确认 CSS 变量正确 |

### 6.3 后端调试

**Python 调试**:

```bash
# 查看后端日志
docker logs -f gateway

# 本地调试
cd backend
uv run python -c "from app.gateway.app import create_app; app = create_app()"
```

**断点调试**:

在 VS Code 中配置 `launch.json`：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Backend Debug",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.gateway.app:create_app", "--factory", "--port", "8001"],
      "cwd": "${workspaceFolder}/backend"
    }
  ]
}
```

### 6.4 API 调试

**Swagger 文档**: 访问 `http://localhost:8001/docs`（需设置 `GATEWAY_ENABLE_DOCS=true`）

**curl 调试**:

```bash
# 获取认证 Cookie
curl -c cookies.txt -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"password"}'

# 使用 Cookie 调用 API
curl -b cookies.txt http://localhost:8001/api/threads
```

### 6.5 Agent 调试

**查看 Agent 执行**:

1. 在对话中观察思维链输出
2. 检查工具调用记录
3. 查看后端日志中的 Agent 执行信息

**Agent 中间件调试**:

在 `config.yaml` 中启用 debug 日志：

```yaml
log_level: DEBUG
```

### 6.6 数据库调试

**SQLite 调试**:

```bash
# 连接数据库
sqlite3 .ideer/data/ideer.db

# 查看表结构
.tables
.schema users_ext

# 查询数据
SELECT * FROM users_ext LIMIT 10;
```

**PostgreSQL 调试**:

```bash
# 连接数据库
psql -h localhost -U ideer -d ideer

# 查看表
\dt

# 查询数据
SELECT * FROM users_ext LIMIT 10;
```

### 6.7 性能分析

**前端性能**:

- 使用 Chrome DevTools Performance 面板
- 检查 Lighthouse 评分
- 分析 Network 请求瀑布图

**后端性能**:

- 使用 `cProfile` 进行 Python 性能分析
- 检查数据库查询（SQLAlchemy echo 模式）
- 监控 API 响应时间

---

## 7. 部署运维

### 7.1 Docker 部署

**生产环境**:

```bash
# 构建镜像
cd docker
docker compose build

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f

# 停止服务
docker compose down
```

**docker-compose.yaml 服务**:

| 服务 | 端口 | 说明 |
|------|------|------|
| nginx | 2026 | 反向代理 |
| frontend | 3000 | Next.js 前端 |
| gateway | 8001 | FastAPI 后端 |
| provisioner | 8002 | 沙盒管理（可选） |

### 7.2 本地部署

```bash
# 使用启动脚本
./scripts/start-local.sh

# 或手动启动
make start
```

**启动脚本检查项**:
- 必需命令（python, node, pnpm, uv）
- config.yaml 存在性
- 环境变量完整性
- 最终执行 `make start`

### 7.3 内网部署

使用专用的内网部署配置：

```bash
docker compose -f docker/docker-compose.intranet.yaml up -d
```

内网部署特点：
- 关闭外部网络访问
- 使用内网 DNS
- 配置内网代理（如需要）

### 7.4 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `IDEER_PROJECT_ROOT` | 项目根目录 | 当前目录 |
| `IDEER_HOME` | 运行时数据目录 | `.ideer` |
| `IDEER_CONFIG_PATH` | 配置文件路径 | `config.yaml` |
| `IDEER_EXTENSIONS_CONFIG_PATH` | 扩展配置路径 | `extensions_config.json` |
| `IDEER_SKILLS_PATH` | 技能目录 | `skills` |
| `BETTER_AUTH_SECRET` | 认证密钥 | （必须设置） |
| `IDEER_INTERNAL_AUTH_TOKEN` | 内部认证 Token | （可选） |
| `GATEWAY_HOST` | 网关监听地址 | `0.0.0.0` |
| `GATEWAY_PORT` | 网关端口 | `8001` |
| `GATEWAY_ENABLE_DOCS` | 启用 API 文档 | `false` |
| `GATEWAY_CORS_ORIGINS` | CORS 允许源 | `*` |

### 7.5 配置管理

**配置版本控制**:

```yaml
config_version: 10  # 当前版本
```

**配置升级**:

```bash
make config-upgrade
```

**配置热更新**: 修改 `config.yaml` 后需重启服务生效。

### 7.6 nginx 配置

核心配置 (`docker/nginx/nginx.conf`):

```nginx
# 前端路由
location / {
    proxy_pass http://frontend:3000;
}

# API 路由
location /api/ {
    proxy_pass http://gateway:8001;
    proxy_buffering off;           # SSE 流式支持
    proxy_read_timeout 600s;       # 长时间请求
    client_max_body_size 100M;     # 文件上传限制
}

# WebSocket / SSE
location /api/threads/ {
    proxy_pass http://gateway:8001;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_cache off;
}
```

### 7.7 SSL/TLS

在 nginx 配置中添加 SSL：

```nginx
server {
    listen 443 ssl;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # ... 其他配置
}
```

---

## 8. 数据库管理

### 8.1 数据库类型

| 类型 | 适用场景 | 持久化 | 并发 |
|------|----------|--------|------|
| `memory` | 开发测试 | ❌ | 单进程 |
| `sqlite` | 单机部署 | ✅ WAL 模式 | 中等 |
| `postgres` | 生产多机 | ✅ | 高 |

### 8.2 迁移管理

```bash
# 查看当前版本
cd backend
uv run alembic current

# 升级到最新版本
uv run alembic upgrade head

# 生成新迁移
uv run alembic revision --autogenerate -m "description"

# 回滚一步
uv run alembic downgrade -1
```

**迁移文件位置**: `backend/packages/harness/ideer/persistence/migrations/versions/`

### 8.3 备份恢复

**SQLite**:

```bash
# 备份
cp .ideer/data/ideer.db .ideer/data/ideer.db.backup

# 恢复
cp .ideer/data/ideer.db.backup .ideer/data/ideer.db
```

恢复或替换数据库后，必须先审计数据库主体与磁盘用户目录是否一致。应用启动时只记录异常，绝不会自动删除目录：

```bash
uv run python scripts/reconcile_user_state.py audit --output /tmp/user-state-audit.json
```

确认清单中的目录确实无数据库引用后再永久删除。命令会在删除前重新检查数据库引用、运行记录、目录摘要、符号链接和根目录边界；交互环境需要确认，自动化环境必须显式传入 `--yes`：

```bash
uv run python scripts/reconcile_user_state.py delete --manifest /tmp/user-state-audit.json
uv run python scripts/reconcile_user_state.py delete --manifest /tmp/user-state-audit.json --include-reserved default
```

删除不可恢复，不提供 quarantine、restore 或延迟 purge。

**PostgreSQL**:

```bash
# 备份
pg_dump -h localhost -U ideer ideer > backup.sql

# 恢复
psql -h localhost -U ideer ideer < backup.sql
```

### 8.4 性能优化

**SQLite**:
- 已默认启用 WAL 模式
- 定期执行 `VACUUM` 命令
- 适当设置 `PRAGMA cache_size`

**PostgreSQL**:
- 配置连接池 (`pool_size`, `max_overflow`)
- 启用 `pool_pre_ping` 检测连接
- 设置 `pool_recycle` 避免连接超时

---

## 9. 监控与日志

### 9.1 日志配置

```yaml
# config.yaml
log_level: INFO
```

### 9.2 日志级别

| 级别 | 使用场景 |
|------|----------|
| `DEBUG` | 详细调试信息，开发环境使用 |
| `INFO` | 一般运行信息，生产环境推荐 |
| `WARNING` | 警告信息，不影响运行但需关注 |
| `ERROR` | 错误信息，需要排查 |

### 9.3 日志分析

**Docker 环境**:

```bash
# 查看所有服务日志
docker compose logs -f

# 查看特定服务日志
docker compose logs -f gateway

# 搜索错误
docker compose logs gateway | grep ERROR
```

**本地环境**:

后端日志输出到 stdout，可重定向到文件：

```bash
uv run uvicorn app.gateway.app:create_app --factory --port 8001 2>&1 | tee gateway.log
```

### 9.4 性能监控

**关键指标**:

| 指标 | 说明 | 监控方式 |
|------|------|----------|
| API 响应时间 | 请求处理耗时 | nginx access log |
| 内存使用 | 进程内存占用 | `docker stats` |
| CPU 使用 | 进程 CPU 占用 | `docker stats` |
| 数据库连接数 | 活跃连接数 | 数据库监控 |
| 错误率 | API 错误比例 | 日志分析 |

### 9.5 错误追踪

**前端错误**:

- 浏览器 Console 错误
- React Error Boundary 捕获
- API 请求失败记录

**后端错误**:

- Python 异常日志
- Agent 执行错误
- 工具调用失败
- 数据库错误

---

## 10. 安全机制

### 10.1 认证系统

**JWT Cookie 认证**:

- Token 存储在 HttpOnly Cookie 中
- 服务端验证，客户端无法读取
- 支持 Token 版本控制（强制失效）
- 自动刷新机制（Tab 可见性变化时）

**密码安全**:

- 使用 bcrypt 哈希
- 密码强度验证（最少 8 位）
- 支持密码修改

### 10.2 CSRF 防护

**Double Submit Cookie 模式**:

1. 服务端设置 CSRF Token Cookie
2. 前端在请求头中携带 `X-CSRF-Token`
3. 服务端验证 Cookie 和 Header 中的 Token 一致

**豁免路径**:

- 认证端点（登录、注册）免 Token 匹配，但仍检查 Origin

### 10.3 RBAC 权限

**四级角色体系**:

| 角色 | 权限 |
|------|------|
| `super_admin` | 全局管理 |
| `department_admin` | 部门管理 |
| `user` | 普通使用 |
| `viewer` | 只读访问 |

**资源可见性**:

- `private`: 仅创建者
- `department`: 同部门
- `public`: 所有人

**权限检查装饰器**:

```python
@require_auth
@require_role("super_admin", "department_admin")
@require_permission("threads", "read")
async def my_endpoint(user=Depends(get_current_user)):
    ...
```

### 10.4 沙盒安全

**本地沙盒**:

- 默认禁止主机 bash 执行
- 文件操作锁定
- 工具输出截断限制

**容器沙盒**:

- Docker 容器隔离
- 可配置资源限制
- 文件系统挂载控制

### 10.5 API 安全

- CORS 配置
- 请求大小限制（100M）
- 超时控制（600s）
- 认证 fail-closed 策略

---

## 11. 测试体系

### 11.1 单元测试

**后端测试**:

```bash
cd backend
uv run pytest tests/ -v
```

**测试文件位置**: `backend/tests/`

| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_schema_parser.py` | 工作流 YAML 解析 |
| `test_template.py` | 模板变量插值 |
| `test_doc_reader.py` | 文档解析工具 |
| `test_code_interpreter.py` | 代码执行工具 |
| `test_data_analyzer.py` | 数据分析工具 |
| `test_channels_router_e2e.py` | 渠道路由 |
| `test_mcp_config_router_e2e.py` | MCP 配置路由 |
| `test_memory_router.py` | 记忆路由 |

### 11.2 集成测试

集成测试验证多个模块的协作：

- API 端点完整流程
- 数据库读写
- Agent 执行链路
- 工具调用链路

### 11.3 E2E 测试

**前端 E2E 测试**:

```bash
cd frontend
npx playwright test
```

**测试文件位置**: `frontend/tests/e2e/`

**Playwright 配置**: `frontend/playwright.config.ts`

### 11.4 性能测试

- API 响应时间基准测试
- 并发请求压力测试
- 内存泄漏检测
- 数据库查询性能

### 11.5 CI/CD

建议的 CI/CD 流程：

```yaml
# .github/workflows/ci.yml
steps:
  - name: Backend Tests
    run: |
      cd backend
      uv sync
      uv run pytest tests/

  - name: Frontend Tests
    run: |
      cd frontend
      pnpm install
      pnpm test

  - name: E2E Tests
    run: |
      cd frontend
      npx playwright test
```

---

## 12. 扩展开发

### 12.1 自定义 LLM Provider

在 `config.yaml` 中配置新的模型提供者：

```yaml
models:
  - provider: my_provider
    model: my-model
    api_key: $MY_PROVIDER_API_KEY
    base_url: https://api.my-provider.com/v1
```

### 12.2 自定义工具

参见 [5.4 新工具开发](#54-新工具开发)。

### 12.3 自定义技能

参见 [5.5 新技能开发](#55-新技能开发)。

### 12.4 自定义中间件

```python
# backend/packages/harness/ideer/agents/middlewares/my_middleware.py
from ..middleware import AgentMiddleware

class MyMiddleware(AgentMiddleware):
    async def __call__(self, state, config, *, next):
        # 前置处理
        result = await next(state, config)
        # 后置处理
        return result
```

注册到中间件链（使用 `@Next` / `@Prev` 装饰器定位）。

### 12.5 MCP 服务器

在 `extensions_config.json` 中配置 MCP 服务器：

```json
{
  "mcpServers": {
    "my-server": {
      "transport": "stdio",
      "command": "node",
      "args": ["path/to/server.js"],
      "env": {}
    },
    "remote-server": {
      "transport": "sse",
      "url": "https://my-mcp-server.com/sse",
      "headers": {
        "Authorization": "Bearer token"
      }
    }
  }
}
```

**传输类型**:

| 类型 | 说明 | 配置 |
|------|------|------|
| `stdio` | 标准输入输出 | `command` + `args` |
| `sse` | Server-Sent Events | `url` + `headers` |
| `http` | HTTP Streamable | `url` + `headers` |

### 12.6 IM 渠道集成

系统支持 IM 渠道接入（如企业微信、钉钉等），通过 `channels` 路由管理：

```yaml
# config.yaml
channels:
  - name: wechat
    type: wecom
    enabled: true
    config:
      corp_id: $WECOM_CORP_ID
      agent_id: $WECOM_AGENT_ID
      secret: $WECOM_SECRET
```

---

## 附录

### A. API 参考文档

启用 Swagger 文档：

```bash
GATEWAY_ENABLE_DOCS=true make start
```

访问 `http://localhost:8001/docs` 查看完整 API 文档。

### B. 配置文件参考

完整的配置模板参见 `config.example.yaml`（1162 行），涵盖：

- `config_version` — 配置版本
- `models` — 模型配置
- `tools` — 工具配置
- `tool_groups` — 工具组配置
- `sandbox` — 沙盒配置
- `subagents` — 子代理配置
- `skills` — 技能配置
- `database` — 数据库配置
- `memory` — 记忆配置
- `summarization` — 摘要配置
- `guardrails` — 安全护栏配置
- `channels` — IM 渠道配置

### C. 环境变量参考

| 变量 | 必需 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | 可选 | OpenAI API 密钥 |
| `ANTHROPIC_API_KEY` | 可选 | Anthropic API 密钥 |
| `BETTER_AUTH_SECRET` | **必需** | 前端认证密钥 |
| `IDEER_PROJECT_ROOT` | 可选 | 项目根目录 |
| `IDEER_HOME` | 可选 | 运行时数据目录 |
| `IDEER_CONFIG_PATH` | 可选 | 配置文件路径 |
| `GATEWAY_HOST` | 可选 | 网关监听地址 |
| `GATEWAY_PORT` | 可选 | 网关端口 |
| `GATEWAY_ENABLE_DOCS` | 可选 | 启用 API 文档 |
| `GATEWAY_CORS_ORIGINS` | 可选 | CORS 允许源 |

### D. 错误代码表

| HTTP 状态码 | 说明 | 排查方向 |
|-------------|------|----------|
| 400 | 请求参数错误 | 检查请求体格式 |
| 401 | 未认证 | 检查 Cookie 和 JWT |
| 403 | 权限不足 | 检查 CSRF Token 或角色权限 |
| 404 | 资源不存在 | 检查 URL 路径 |
| 422 | 验证失败 | 检查请求数据格式 |
| 500 | 服务端错误 | 查看后端日志 |

### E. 术语表

| 术语 | 说明 |
|------|------|
| **Agent** | AI 智能体，具有独立配置的 AI 助手 |
| **AgentMiddleware** | Agent 中间件，控制 Agent 执行流程 |
| **Artifact** | 工件，AI 生成的文件 |
| **CSRF** | Cross-Site Request Forgery，跨站请求伪造 |
| **LangGraph** | Agent 编排框架 |
| **MCP** | Model Context Protocol，模型上下文协议 |
| **RBAC** | Role-Based Access Control，基于角色的访问控制 |
| **RuntimeFeatures** | Agent 运行时特性配置 |
| **Sandbox** | 代码执行沙盒 |
| **Skill** | 技能，扩展 AI 能力的指令集 |
| **SOUL** | Agent 系统提示词 |
| **SSE** | Server-Sent Events，服务端推送事件 |
| **Thread** | 对话线程 |
| **Workflow** | 工作流，多步骤自动化流程 |
