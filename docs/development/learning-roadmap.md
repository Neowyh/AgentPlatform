# iDeer 工程学习路线图

> 本路线图面向**代码基础较弱的初学者**，从零开始系统学习 iDeer 全栈 AI Agent 平台的工程细节。按 5 个阶段递进，每个阶段有明确目标和产出。

---

## 阶段 1：先理解「这是什么」— 读顶层文档

从**使用视角**了解项目全貌，不纠结代码细节。

### 必读材料（按顺序）

| 阅读材料 | 目的 |
|---------|------|
| `README.md`（英文或 `README_zh.md` 中文版） | 项目定位、核心概念、一行命令启动 |
| `backend/docs/ARCHITECTURE.md` | **系统架构总图** — 看懂整体怎么拼起来的 |
| `frontend/README.md` | 前端概览、技术栈 |
| `docs/architecture/overview.md` | 架构概览，辅助理解 |

### 需要理解的关键问题

- iDeer 是什么？解决什么问题？
- 前后端分别用什么框架？
- Agent 是什么？Skill 是什么？Sandbox 是什么？
- 项目的许可证和社区背景（字节跳动开源）

### 阶段产出

> 能用自己的话解释「iDeer 是做什么的」、说出前后端各自用什么框架、列出 3 个核心概念（Agent / Skill / Sandbox）。

---

## 阶段 2：搭建环境，跑起来

**动手实操是最直观的学习方式。** 不跑起来，一切都是纸上谈兵。

### 步骤

1. **阅读** `Install.md` 和 `CONTRIBUTING.md` 的开发环境搭建部分
2. **运行命令**（推荐 Docker 方式，最省心）：

```bash
make setup           # 交互式初始化向导
make docker-start    # Docker 一键启动所有服务
```

3. **验证**：
   - 打开浏览器访问 `http://localhost:2026` 看前端界面
   - 观察后端日志输出，理解服务启动过程
   - 尝试在 `config.example.yaml` 中配置一个 LLM provider（如 OpenAI 或 Ollama 本地模型）

### 可选：本地开发模式（不依赖 Docker）

```bash
make install    # 安装前后端依赖
make dev        # 本地热重载开发模式
```

### 阶段产出

> 能在本地跑起来，看到前端页面，观察到 Agent 的思考流输出；理解 Docker 和本地开发两种模式的区别。

---

## 阶段 3：理解核心概念 — 地图模式

按**数据流方向**逐个理解关键模块。建议对照 `backend/docs/ARCHITECTURE.md` 中的架构图学习。

### 数据流全景

```
用户输入
  ↓
① Next.js 前端 (UI 渲染 + BFF 代理)
  ↓  HTTP / SSE
② FastAPI 网关 (路由、认证、文件上传、技能管理)
  ↓
③ LangGraph Lead Agent (拆解任务、决策、调度)
  ↓
   ├─ Sub-Agent (子任务委托，可并行执行)
   ├─ 工具系统 (搜索、读文件、写代码、数据分析等)
   ├─ 沙箱 (安全隔离的执行环境)
   └─ 记忆系统 (跨会话持久化知识)
  ↓
④ 结果流式返回 → 前端实时展示
```

### 关键文档（推荐按顺序阅读）

| 文档 | 内容 | 建议 |
|------|------|------|
| `backend/CLAUDE.md` | **最全面的后端架构参考**（643 行），涵盖所有子系统 | 分 2-3 次读完，每次读一个子系统 |
| `backend/docs/STREAMING.md` | SSE 流式输出机制 | 理解 Agent 如何实时推送中间步骤 |
| `backend/docs/CONFIGURATION.md` | 配置系统详解（模型、工具、沙箱、记忆） | 配合 `config.example.yaml` 对照看 |
| `backend/docs/MEMORY_SETTINGS_REVIEW.md` | 记忆系统设置 | 理解记忆如何持久化 |
| `backend/docs/GUARDRAILS.md` | 工具调用安全防护 | 理解安全机制 |
| `backend/docs/AUTH_DESIGN.md` | 用户认证与隔离设计 | 理解多用户场景 |
| `backend/docs/MCP_SERVER.md` | MCP 服务器集成 | 理解外部工具扩展方式 |

### 需要理解的关键概念

- **Lead Agent vs Sub-Agent**：主 Agent 和子 Agent 的分工
- **Middleware 链**：一个请求经过的 18 个中间件各自做什么
- **Sandbox 模式**：Local vs Docker vs Kubernetes 三种隔离级别
- **Tool 系统**：内置工具、社区工具、MCP 工具三层架构
- **Skill 系统**：Markdown 格式的技能文件如何被加载和注入
- **Memory**：跨会话记忆如何积累、去重、注入上下文

### 阶段产出

> 能画出从用户输入到回复的完整数据流路径，说出至少 5 个中间件的名称和作用，理解 Sandbox 三种模式的区别。

---

## 阶段 4：深入关键源码文件

选核心入口文件来读，**先看结构注释、类定义和函数签名，不要一开始就抠实现细节**。

### 建议阅读顺序

| 文件路径 | 为什么读它 | 难度 |
|---------|-----------|------|
| `backend/packages/harness/ideer/client.py` | `iDeerClient` 把整个 Agent 系统封装成一个 Python 类，是**最易理解的入口** | ⭐ |
| `backend/packages/harness/ideer/agents/lead_agent/agent.py` | Agent 系统的**心脏** — Lead Agent 如何组装中间件、模型、工具 | ⭐⭐⭐ |
| `backend/app/gateway/app.py` | FastAPI 应用的入口，看**路由注册总表**，理解 HTTP 请求如何进入 Agent | ⭐⭐ |
| `backend/packages/harness/ideer/agents/thread_state.py` | 理解 Agent 的**状态数据结构**（ThreadState），这是贯穿整个系统的核心类型 | ⭐⭐ |
| `backend/packages/harness/ideer/models/factory.py` | Model Factory — 如何创建不同 Provider 的 LLM 实例 | ⭐⭐ |
| `backend/packages/harness/ideer/tools/__init__.py` | 工具装配点 — 所有可用工具如何汇聚 | ⭐⭐ |
| `backend/packages/harness/ideer/sandbox/` 目录 | 沙箱接口定义 + 两种实现的对比 | ⭐⭐ |
| `backend/packages/harness/ideer/mcp/manager.py` | MCP 多服务器管理 | ⭐⭐⭐ |
| `backend/packages/harness/ideer/skills/loader.py` | 技能发现和加载逻辑 | ⭐⭐ |
| `backend/packages/harness/ideer/config/app_config.py` | 配置系统核心 | ⭐⭐ |

### 读源码技巧

1. **先读测试文件** — 测试文件展示了一个功能「应该怎么用」，比直接看实现更容易理解
   - 例如：读 `backend/tests/test_client.py` 前先读 `client.py`
2. **关注 Interface / Protocol 类** — 项目中大量使用 `Protocol` 和抽象基类，理解接口设计比具体实现更重要
3. **用 grep 追踪调用链** — 比如想了解「工具怎么被调用」就搜索 `call_tool` 或 `execute_tool`
4. **善用 IDE** — 跳转定义、查看引用

### 阶段产出

> 能指出 Lead Agent 在哪个文件、Gateway 注册了哪些路由类别、技能文件如何被加载、iDeerClient 的基本用法。

---

## 阶段 5：读配置 + 玩技能

动手修改和实验，从使用者变成参与者。

### 5.1 读完整配置

- 通读 `config.example.yaml`（1161 行完整配置参考）
- 理解每个配置大段的含义：`models`、`tools`、`sandbox`、`memory`、`subagents`、`mcp_servers`

### 5.2 探索技能系统

- 浏览 `skills/public/` 下的 21 个内置技能，每个都包含一个 `SKILL.md`
- 选择一个简单的技能（如 `data-analysis`），完整阅读，理解技能的 Markdown 格式规范
- 尝试编写一个自定义技能放在 `skills/custom/` 下

### 5.3 动手实验

- 修改配置切换 LLM Provider
- 添加/禁用某个工具
- 修改 Sandbox 隔离级别
- 观察系统行为的变化

### 阶段产出

> 能自己配置一个新的 LLM Provider、编写一个简单的技能、理解配置文件中每个主要段的用途。

---

## 推荐时间安排

| 阶段 | 预计时间 | 节奏建议 |
|------|---------|---------|
| 阶段 1：理解定位 | 1 天 | 通读 README 和架构文档，做笔记 |
| 阶段 2：搭建环境 | 0.5-1 天 | 跟着文档一步步操作 |
| 阶段 3：核心概念 | 3-5 天 | 每天读 1-2 个专题文档，画数据流图 |
| 阶段 4：读源码 | 5-10 天 | 每天读 1-2 个核心文件，配合测试理解 |
| 阶段 5：动手实验 | 持续 | 边用边学，实践中深入 |

总计约 **2-3 周** 可从零基础到对项目有系统理解。

---

## 学习原则

1. **不要一次性读完所有文档** — 按阶段来，每阶段动手操作后再进入下一阶段
2. **带着问题读代码** — 比如「Agent 怎么调用工具的？」然后去 grep 相关代码流
3. **关注接口设计** — 理解 Protocol 和抽象类，比理解具体实现更重要
4. **用 Docker 环境做实验** — 改代码 → 热重载 → 观察结果，形成快反馈循环
5. **动手 > 阅读** — 代码只有跑起来才能真正理解

---

## 补充资源

### 关键文件速查表

| 文件路径 | 一句话说明 |
|---------|-----------|
| `config.example.yaml` | 完整配置模板 |
| `skills/public/*/SKILL.md` | 内置技能定义 |
| `backend/packages/harness/ideer/` | iDeer 核心库 |
| `backend/app/gateway/` | FastAPI 网关代码 |
| `frontend/src/core/` | 前端业务逻辑 |
| `frontend/src/components/` | 前端 UI 组件 |
| `docker/docker-compose.yaml` | 生产环境 Docker Compose |
| `workflows/` | YAML 工作流定义 |

### 常用命令

```bash
make setup                 # 初始化设置
make dev                   # 本地热重载开发
make docker-start          # Docker 启动
make docker-stop           # Docker 停止
make doctor                # 环境和配置检查
cd backend && make test    # 运行后端测试
cd backend && make lint    # 运行后端 lint
cd frontend && pnpm check  # 前端类型检查 + lint
```
