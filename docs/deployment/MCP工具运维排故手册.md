# MCP 工具运维排故手册

> 面向需要注册、安装新 MCP Server 的用户和运维人员。
> 基于实际排障经验整理，覆盖从配置到运行的全链路。

---

## 目录

1. [架构概览](#1-架构概览)
2. [MCP 配置逻辑](#2-mcp-配置逻辑)
3. [MCP 运行机制](#3-mcp-运行机制)
4. [安装新 MCP Server 操作步骤](#4-安装新-mcp-server-操作步骤)
5. [排障流程总览](#5-排障流程总览)
6. [分层排查详解](#6-分层排查详解)
7. [典型故障案例](#7-典型故障案例)
8. [常用排查命令速查](#8-常用排查命令速查)

---

## 1. 架构概览

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户对话                                  │
│                           ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Agent（LLM）                          │    │
│  │            model.bind_tools(tools)                       │    │
│  │                  ↓ tool_call                             │    │
│  │              ToolNode 执行                               │    │
│  └──────────────┬──────────────────────────────────────────┘    │
│                 ↓                                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              get_available_tools()                        │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │   │
│  │  │ 配置工具  │ │ 内置工具  │ │ MCP 工具  │ │ ACP 工具  │    │   │
│  │  │(bash等)  │ │(present  │ │(来自MCP   │ │(跨agent  │    │   │
│  │  │          │ │ file等)  │ │ server)  │ │ 调用)    │    │   │
│  │  └──────────┘ └──────────┘ └────┬─────┘ └──────────┘    │   │
│  │                                 ↓                        │   │
│  │                    ┌─────────────────────┐               │   │
│  │                    │ Skill allowed-tools │               │   │
│  │                    │     白名单过滤       │               │   │
│  │                    └─────────────────────┘               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               MCP 工具加载层                               │   │
│  │  get_cached_mcp_tools()                                  │   │
│  │       ↓                                                  │   │
│  │  get_mcp_tools()                                         │   │
│  │       ↓                                                  │   │
│  │  MultiServerMCPClient → 连接所有 MCP Server              │   │
│  │       ↓                                                  │   │
│  │  load_mcp_tools() → 发现工具定义                          │   │
│  │       ↓                                                  │   │
│  │  _make_session_pool_tool() → stdio 工具持久会话包装       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↓                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               MCP Server 层                               │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐            │   │
│  │  │ Server A   │ │ Server B   │ │ Server C   │            │   │
│  │  │ (stdio)    │ │ (sse)      │ │ (http)     │            │   │
│  │  └────────────┘ └────────────┘ └────────────┘            │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 关键组件

| 组件 | 文件路径 | 职责 |
|------|---------|------|
| 配置加载 | `config/extensions_config.py` | 读取 `extensions_config.json`，解析 MCP server 配置 |
| 连接构建 | `mcp/client.py` | 将配置转换为 `MultiServerMCPClient` 连接参数 |
| 工具加载 | `mcp/tools.py` | 连接 MCP server、发现工具、会话池包装 |
| 工具缓存 | `mcp/cache.py` | 全局缓存 + mtime 感知自动失效 |
| 会话池 | `mcp/session_pool.py` | 按 `(server_name, thread_id)` 维护持久 MCP session |
| 工具聚合 | `tools/tools.py` | 合并配置工具 + 内置工具 + MCP 工具 + ACP 工具 |
| 工具过滤 | `skills/tool_policy.py` | 按 skill `allowed-tools` 白名单过滤工具 |
| Agent 构建 | `agents/lead_agent/agent.py` | 组装工具列表、绑定到 LLM、创建 agent graph |

### 1.3 传输方式对比

| 传输方式 | 特点 | 会话管理 | 适用场景 |
|---------|------|---------|---------|
| `stdio` | 启动子进程通信 | 持久会话池（按 thread 隔离） | 本地工具、有状态服务 |
| `sse` | HTTP 长连接 Server-Sent Events | 每次调用新建 session | 远程服务、Docker 容器间通信 |
| `http` | HTTP Streamable | 每次调用新建 session | 远程服务、RESTful 风格 |

---

## 2. MCP 配置逻辑

### 2.1 配置文件位置

配置文件为 `extensions_config.json`，查找优先级：

```
1. 环境变量 IDEER_EXTENSIONS_CONFIG_PATH 指定的路径
2. 项目根目录/extensions_config.json
3. 项目根目录/mcp_config.json（兼容旧名）
4. backend/extensions_config.json
5. 仓库根目录/extensions_config.json
```

**Docker 部署时**：通过 volume 挂载到容器内 `/app/backend/extensions_config.json`，
同时设置环境变量 `IDEER_EXTENSIONS_CONFIG_PATH=/app/backend/extensions_config.json`。

### 2.2 配置文件格式

```json
{
  "mcpInterceptors": [],
  "mcpServers": {
    "your-server-name": {
      "enabled": true,
      "type": "sse",
      "url": "http://host.docker.internal:8100/sse",
      "description": "你的 MCP Server 描述"
    },
    "another-server": {
      "enabled": true,
      "type": "stdio",
      "command": "python",
      "args": ["-m", "your_package.mcp_server"],
      "env": {},
      "description": "另一个 MCP Server"
    }
  },
  "skills": {}
}
```

### 2.3 配置字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `enabled` | bool | 否 | 是否启用，默认 `true` |
| `type` | string | 是 | 传输方式：`stdio` / `sse` / `http` |
| `command` | string | stdio 必填 | 启动命令（仅 stdio） |
| `args` | list | 否 | 命令参数（仅 stdio） |
| `env` | dict | 否 | 环境变量（仅 stdio） |
| `url` | string | sse/http 必填 | 服务端点 URL |
| `headers` | dict | 否 | 自定义 HTTP 头 |
| `oauth` | object | 否 | OAuth 认证配置（仅 sse/http） |
| `description` | string | 否 | 人类可读描述 |

### 2.4 环境变量解析

配置中的 `$VAR_NAME` 格式会被自动解析为环境变量值。例如：

```json
{
  "env": {
    "API_KEY": "$MY_API_KEY"
  }
}
```

如果 `MY_API_KEY` 环境变量未设置，会抛出 `ValueError`。

---

## 3. MCP 运行机制

### 3.1 启动时初始化流程

```
应用启动（或首次请求时懒加载）
    ↓
initialize_mcp_tools()                    # mcp/cache.py
    ↓
get_mcp_tools()                           # mcp/tools.py
    ↓
ExtensionsConfig.from_file()              # 读取配置
    ↓
build_servers_config()                    # 构建连接参数
    ↓
get_initial_oauth_headers()               # OAuth token（如有）
    ↓
MultiServerMCPClient(servers_config)      # 创建多服务器客户端
    ↓
client.get_tools()                        # 并发连接所有 server，发现工具
    ↓ （对每个 server）
create_session() → session.initialize() → load_mcp_tools()
    ↓
_make_session_pool_tool()                 # stdio 工具包装持久会话
    ↓
make_sync_tool_wrapper()                  # 附加同步调用支持
    ↓
缓存到 _mcp_tools_cache                   # 全局单例
```

### 3.2 工具聚合流程

```
get_available_tools()                     # tools/tools.py
    ↓
① 配置工具：config.tools 按 tool_groups 过滤
    ↓
② 内置工具：present_file, ask_clarification, task 等
    ↓
③ MCP 工具：get_cached_mcp_tools()
    ↓
④ ACP 工具：invoke_acp_agent（如有配置）
    ↓
⑤ 去重：按工具名去重，配置工具优先
    ↓
⑥ Skill 过滤：filter_tools_by_skill_allowed_tools()
    ↓
返回最终工具列表
```

### 3.3 运行时调用流程

```
用户消息 → Agent（LLM）→ 生成 tool_call
    ↓
ToolNode 接收 tool_call
    ↓
按 tool.name 查找 tools_by_name
    ↓
调用 tool.invoke(args)
    ↓
┌─── stdio 工具 ───────────────────────────────────┐
│ call_with_persistent_session()                    │
│   → pool.get_session(server_name, thread_id)      │
│   → session.call_tool(original_name, arguments)   │
│   → _convert_call_tool_result()                   │
└───────────────────────────────────────────────────┘
┌─── sse/http 工具 ────────────────────────────────┐
│ 直接调用（无持久会话）                              │
│   → session.call_tool(name, arguments)            │
│   → _convert_call_tool_result()                   │
└───────────────────────────────────────────────────┘
    ↓
ToolMessage 返回给 Agent → LLM 继续推理
```

### 3.4 缓存失效机制

MCP 工具缓存通过 `extensions_config.json` 文件的 **mtime**（修改时间）检测变更：

- 每次 `get_cached_mcp_tools()` 检查 mtime 是否变化
- 如果文件被修改（如通过 Gateway API 更新配置），自动重置缓存并重新加载
- `reset_mcp_tools_cache()` 同时关闭所有持久 MCP session

### 3.5 Tool Search 延迟暴露

当 `config.yaml` 中 `tool_search.enabled: true` 时：

```
MCP 工具注册到 DeferredToolRegistry（默认不可见）
    ↓
Agent 初始只看到 tool_search 工具
    ↓
用户请求 → LLM 调用 tool_search 搜索
    ↓
匹配的工具被 promote() 为可见
    ↓
DeferredToolFilterMiddleware 过滤未 promote 的工具 schema
    ↓
promoted 的工具在后续轮次中可被 LLM 直接调用
```

---

## 4. 安装新 MCP Server 操作步骤

### 4.1 stdio 模式（本地进程）

**步骤 1：确认工具可用**

```bash
# 测试 MCP server 能否正常启动
python -m your_package.mcp_server
# 应该看到等待 stdin 输入的状态（stdio 模式）
# Ctrl+C 退出
```

**步骤 2：编辑配置文件**

```json
{
  "mcpServers": {
    "your-server": {
      "enabled": true,
      "type": "stdio",
      "command": "python",
      "args": ["-m", "your_package.mcp_server"],
      "env": {
        "API_KEY": "$YOUR_API_KEY"
      },
      "description": "你的工具描述"
    }
  }
}
```

**步骤 3：重启服务**

```bash
# Docker 部署
docker restart ideer-gateway

# 本地部署
make restart
```

**步骤 4：验证加载**

```bash
docker logs ideer-gateway 2>&1 | grep -i "mcp" | tail -5
# 应看到: Successfully loaded N tool(s) from MCP servers
```

### 4.2 SSE 模式（远程服务）

**步骤 1：确认 SSE 端点可达**

```bash
# 从运行 gateway 的环境中测试
# Docker 容器内：
docker exec -w /app/backend ideer-gateway /app/backend/.venv/bin/python3 -c "
import urllib.request
r=urllib.request.urlopen('http://your-host:port/sse', timeout=5)
print('OK', r.status)
"
```

**步骤 2：编辑配置文件**

```json
{
  "mcpServers": {
    "your-server": {
      "enabled": true,
      "type": "sse",
      "url": "http://host.docker.internal:8100/sse",
      "description": "你的远程 MCP 工具"
    }
  }
}
```

**URL 选择规则：**

| MCP Server 部署位置 | url 填写 |
|---------------------|---------|
| 同一 Docker network 中的容器 | `http://容器名:端口/sse` |
| 宿主机上运行（有端口映射） | `http://host.docker.internal:端口/sse` |
| 内网其他机器 | `http://内网IP:端口/sse` |

**步骤 3：重启并验证**（同上）

### 4.3 为自定义 Agent 配置 MCP 工具权限

如果需要在自定义 Agent（如归零智能体）中使用 MCP 工具，需要在 SKILL.md 的 `allowed-tools` 中加入 MCP 工具名。

**关键：必须使用工具加载后的实际名称，而非注册名称。**

```bash
# 获取实际工具名
docker exec -w /app/backend -e PYTHONPATH=. ideer-gateway /app/backend/.venv/bin/python3 -c "
from ideer.mcp.cache import get_cached_mcp_tools
for t in get_cached_mcp_tools():
    print(repr(t.name))
"
```

将输出的工具名写入 `resources/skills/your-skill/SKILL.md`：

```yaml
allowed-tools:
  - glob
  - grep
  - read_file
  - write_file
  - your-server_your_tool_name    # ← 使用上面输出的实际名称
```

---

## 5. 排障流程总览

当 MCP 工具无法正常调用时，按以下顺序逐层排查：

```
┌─────────────────────────────────────────────────────────┐
│                    第一层：配置文件                        │
│  extensions_config.json 是否被正确加载？                   │
│  排查命令：查看日志 "No enabled MCP servers"               │
│  修复：确认文件路径、环境变量、enabled=true                │
└───────────────────────┬─────────────────────────────────┘
                        ↓ OK
┌─────────────────────────────────────────────────────────┐
│                    第二层：拦截器配置                       │
│  mcpInterceptors 是否指向不存在的模块？                    │
│  排查命令：日志搜 "cannot import module"                   │
│  修复：清空 mcpInterceptors: []                          │
└───────────────────────┬─────────────────────────────────┘
                        ↓ OK
┌─────────────────────────────────────────────────────────┐
│                    第三层：网络连通性                       │
│  MCP Server 从 gateway 容器内是否可达？                    │
│  排查命令：容器内 urllib 测试 SSE URL                      │
│  修复：改用 host.docker.internal 或容器名                  │
└───────────────────────┬─────────────────────────────────┘
                        ↓ OK
┌─────────────────────────────────────────────────────────┐
│                    第四层：工具可见性                       │
│  工具加载成功但 Agent 看不到？                              │
│  排查：tool_search 配置 / agent graph 缓存 /              │
│       skill allowed-tools 名称匹配                        │
│  修复：关闭 tool_search / 重启新对话 / 修正工具名           │
└───────────────────────┬─────────────────────────────────┘
                        ↓ OK
┌─────────────────────────────────────────────────────────┐
│                    第五层：模型能力                         │
│  LLM 是否支持 function calling？                          │
│  排查命令：日志搜 "tool_calls"，或直接测试 bind_tools       │
│  修复：vLLM 加 --enable-auto-tool-choice                  │
│        --tool-call-parser hermes                          │
└─────────────────────────────────────────────────────────┘
```

---

## 6. 分层排查详解

### 6.1 第一层：配置文件加载

**现象：** 日志中完全没有 MCP 相关信息，或显示 `No enabled MCP servers configured`。

**排查命令：**

```bash
# 检查环境变量
docker exec ideer-gateway env | grep IDEER_EXTENSIONS_CONFIG_PATH

# 检查文件是否存在
docker exec ideer-gateway ls -la /app/backend/extensions_config.json

# 模拟配置加载
docker exec -w /app/backend ideer-gateway /app/backend/.venv/bin/python3 -c "
from ideer.config.extensions_config import ExtensionsConfig
c=ExtensionsConfig.from_file()
print(list(c.mcp_servers.keys()), [(s.enabled,s.type,s.url) for s in c.mcp_servers.values()])
"
```

**常见原因：**

| 原因 | 表现 | 修复 |
|------|------|------|
| 环境变量未设置 | 文件存在但日志显示空配置 | 设置 `IDEER_EXTENSIONS_CONFIG_PATH` 或依赖 fallback |
| 文件未挂载到容器 | `ls` 显示文件不存在 | 检查 docker-compose volumes 配置 |
| `enabled: false` | 配置加载正常但 server 未启用 | 改为 `enabled: true` |
| JSON 格式错误 | 加载报错 | 校验 JSON 语法 |

**Docker 环境变量传递链：**

```
宿主机 .env 文件
    ↓ docker compose --env-file
docker-compose.yaml 中 ${} 变量替换（宿主机路径）
    ↓ volumes 挂载
容器内文件路径
    ↓ environment 设置
容器内环境变量（容器内路径）
    ↓ os.getenv()
Python 代码读取
```

### 6.2 第二层：拦截器配置

**现象：** 日志报错 `cannot import module my_package.mcp.auth`。

**根因：** `extensions_config.example.json` 中的示例拦截器指向不存在的模块。

**修复：**

```json
{
  "mcpInterceptors": []
}
```

**注意：** 拦截器加载失败会影响整个 MCP 初始化链路，导致所有工具加载失败。

### 6.3 第三层：网络连通性

**现象：** 日志报错 `httpcore.ConnectError: All connection attempts failed` 或 `ConnectionRefusedError: [Errno 111] Connection refused`。

**排查命令：**

```bash
# 从容器内测试连通性（必须用 .venv 中的 python）
docker exec -w /app/backend ideer-gateway /app/backend/.venv/bin/python3 -c "
import urllib.request
r=urllib.request.urlopen('http://your-mcp-host:port/sse', timeout=5)
print('OK', r.status)
"
```

**常见错误及含义：**

| 错误 | 含义 | 修复 |
|------|------|------|
| `Connection refused` | 目标不可达 | 检查 URL、端口、网络 |
| `Connection refused` (127.0.0.1) | 容器内 localhost 不是宿主机 | 改用 `host.docker.internal` |
| `timeout` | 连接超时 | 检查防火墙、MCP server 状态 |
| `HTTP 404` | SSE 端点路径错误 | 检查 URL 路径（如 `/sse`） |
| `HTTP 401` | 认证失败 | 检查 headers 或 OAuth 配置 |

**Docker 网络要点：**

- 容器内 `127.0.0.1` 指的是**容器自己**，不是宿主机
- 宿主机有端口映射时用 `host.docker.internal`（gateway 已配置 `extra_hosts`）
- 同一 Docker network 内的容器可直接用**容器名**作为 hostname
- `asyncio.gather` 并发连接所有 server，**任一失败则全部失败**

### 6.4 第四层：工具可见性

**现象：** 日志显示 `Successfully loaded N tool(s)`、`MCP tools: N`，但 Agent 对话中无法调用。

**排查步骤：**

**4a. 检查 tool_search 配置**

```bash
docker exec ideer-gateway cat /app/backend/config.yaml | grep -A 2 tool_search
```

如果 `tool_search.enabled: true`，MCP 工具默认不可见，需要 LLM 主动搜索。
排查时可临时关闭。

**4b. Agent graph 缓存**

LangGraph 的 agent graph 在首次请求时构建并缓存。如果 MCP 工具在 graph 构建后才加载完成，旧 graph 不会更新。

```bash
# 重启 gateway，发起全新对话（不要用旧对话）
docker restart ideer-gateway
```

**4c. Skill allowed-tools 名称不匹配**

自定义 Agent 的 skill 中 `allowed-tools` 白名单可能不包含 MCP 工具名，或名称写错。

```bash
# 获取实际工具名
docker exec -w /app/backend -e PYTHONPATH=. ideer-gateway /app/backend/.venv/bin/python3 -c "
from ideer.mcp.cache import get_cached_mcp_tools
for t in get_cached_mcp_tools():
    print(repr(t.name))
"
```

**关键：MCP 工具加载时会自动加 server name 前缀。**

```
配置中的 server 名: time-series-analyzer
工具注册名:         time_series_analyzer
实际加载后的名称:   time-series-analyzer_time_series_analyzer
```

SKILL.md 中必须使用**实际加载后的完整名称**。

**4d. 验证工具是否绑定到 Agent**

```bash
docker exec -w /app/backend -e PYTHONPATH=. ideer-gateway /app/backend/.venv/bin/python3 -c "
from ideer.tools.tools import get_available_tools
tools = get_available_tools()
for t in tools:
    print(t.name)
"
```

### 6.5 第五层：模型能力

**现象：** 工具加载成功、绑定到 Agent，但 LLM 从不生成 `tool_call`，直接用文本回复"该工具未连接"或"没有配置 MCP"。

**排查命令：**

```bash
# 检查日志中是否有 tool_call
docker logs ideer-gateway 2>&1 | grep -iE "tool_calls|ToolCall|ToolNode" | tail -10
```

如果完全没有 tool_call 日志，说明 LLM 没有尝试调用工具。

**验证模型是否支持 function calling：**

```bash
# 从容器内用和 Agent 一致的客户端测试
docker exec -w /app/backend -e PYTHONPATH=. ideer-gateway /app/backend/.venv/bin/python3 -c "
import asyncio
from ideer.models.vllm_provider import VllmChatModel
from langchain_core.tools import tool

async def test():
    llm = VllmChatModel(model='你的模型名', base_url='http://你的模型地址/v1', api_key='你的key')
    @tool(description='get weather by city')
    def get_weather(city: str) -> str:
        return city + ' sunny'
    resp = await llm.bind_tools([get_weather]).ainvoke('check beijing weather')
    print('tool_calls:', resp.tool_calls)

asyncio.run(test())
```

**如果 `tool_calls` 为空列表：** vLLM 服务端未开启 function calling。

**修复：** 在 vLLM 启动参数中添加：

```bash
--enable-auto-tool-choice --tool-call-parser hermes
```

| 模型系列 | tool-call-parser |
|---------|-----------------|
| Qwen 系列 | `hermes` |
| Llama 系列 | `llama3_json` |
| Mistral 系列 | `mistral` |

---

## 7. 典型故障案例

### 案例 1：配置文件未挂载到 Docker 容器

**现象：** MCP 工具完全不生效，日志无 MCP 信息。

**根因：** `docker-compose.yaml` 中 `${IDEER_EXTENSIONS_CONFIG_PATH}` 变量未在 `.env` 文件中定义，导致 volume 挂载失败。

**排查过程：**
```bash
docker exec ideer-gateway ls -la /app/backend/extensions_config.json
# 文件不存在
```

**修复：** 在 `.env` 中添加 `IDEER_EXTENSIONS_CONFIG_PATH=/path/to/extensions_config.json`。

---

### 案例 2：mcpInterceptors 引用不存在的模块

**现象：** 日志报错 `cannot import module my_package.mcp.auth`，MCP 工具数为 0。

**根因：** 复制了 `extensions_config.example.json`，其中 `mcpInterceptors` 指向示例模块。

**修复：** `mcpInterceptors: []`

---

### 案例 3：Docker 容器内 127.0.0.1 不可达

**现象：** `httpcore.ConnectError: All connection attempts failed`。

**根因：** MCP server 的 `url` 配置为 `http://127.0.0.1:8100/sse`，但 `127.0.0.1` 在 gateway 容器内指的是容器自己。

**修复：**
- MCP server 在同一 Docker network → 用容器名：`http://mcp-container:8100/sse`
- MCP server 在宿主机（有端口映射） → 用 `http://host.docker.internal:8100/sse`

---

### 案例 4：asyncio.gather 一个失败全部失败

**现象：** 配置了 3 个 MCP server，其中一个连接失败，结果 `MCP tools: 0`。

**根因：** `MultiServerMCPClient.get_tools()` 使用 `asyncio.gather(*tasks)` 并发连接，任一异常会导致整个 gather 失败。

**修复：** 确保所有 server 的 URL 都可达，或禁用不可达的 server（`enabled: false`）。

---

### 案例 5：Skill allowed-tools 名称不匹配

**现象：** 默认 Agent 能调用 MCP 工具，但自定义 Agent（如归零智能体）无法调用。

**根因：** MCP 工具加载时自动加 server name 前缀，导致实际名称与 SKILL.md 中写的不一致。

**排查过程：**
```bash
# 获取实际工具名
docker exec -w /app/backend -e PYTHONPATH=. ideer-gateway /app/backend/.venv/bin/python3 -c "
from ideer.mcp.cache import get_cached_mcp_tools
for t in get_cached_mcp_tools():
    print(repr(t.name))
"
# 输出: 'time-series-analyzer_time_series_analyzer'
# SKILL.md 中写的是: 'time_series_analyzer'（缺少前缀）
```

**修复：** 将实际工具名写入 SKILL.md 的 `allowed-tools`。

---

### 案例 6：模型不支持 function calling

**现象：** 工具加载成功、绑定成功，但 LLM 从不调用工具，回复"该工具未连接"。

**根因：** vLLM 部署时未加 `--enable-auto-tool-choice --tool-call-parser` 参数。

**验证：**
```bash
docker exec -w /app/backend -e PYTHONPATH=. ideer-gateway /app/backend/.venv/bin/python3 -c "
import asyncio
from ideer.models.vllm_provider import VllmChatModel
from langchain_core.tools import tool
async def test():
    llm = VllmChatModel(model='qwen3.5-122b', base_url='http://192.168.x.x:port/v1', api_key='key')
    @tool(description='test')
    def f(x: str) -> str: return x
    resp = await llm.bind_tools([f]).ainvoke('test')
    print('tool_calls:', resp.tool_calls)
asyncio.run(test())
"
# 如果 tool_calls: [] → 模型服务端不支持 function calling
```

**修复：** vLLM 启动参数加 `--enable-auto-tool-choice --tool-call-parser hermes`。

---

## 8. 常用排查命令速查

### 配置相关

```bash
# 查看容器内配置文件
docker exec ideer-gateway cat /app/backend/extensions_config.json

# 模拟配置加载
docker exec -w /app/backend ideer-gateway /app/backend/.venv/bin/python3 -c "
from ideer.config.extensions_config import ExtensionsConfig
c=ExtensionsConfig.from_file()
print(list(c.mcp_servers.keys()), [(s.enabled,s.type,s.url) for s in c.mcp_servers.values()])
"
```

### 网络相关

```bash
# 从容器内测试 MCP server 连通性
docker exec -w /app/backend ideer-gateway /app/backend/.venv/bin/python3 -c "
import urllib.request
r=urllib.request.urlopen('http://host.docker.internal:8100/sse', timeout=5)
print('OK', r.status)
"

# 查看 Docker network 中的容器
docker network inspect ideer --format='{{range .Containers}}{{.Name}} {{end}}'

# 查看容器端口映射
docker inspect 容器名 --format='{{json .HostConfig.PortBindings}}'
```

### 工具相关

```bash
# 查看 MCP 工具实际名称
docker exec -w /app/backend -e PYTHONPATH=. ideer-gateway /app/backend/.venv/bin/python3 -c "
from ideer.mcp.cache import get_cached_mcp_tools
for t in get_cached_mcp_tools():
    print(repr(t.name))
"

# 查看 Agent 可用工具列表
docker exec -w /app/backend -e PYTHONPATH=. ideer-gateway /app/backend/.venv/bin/python3 -c "
from ideer.tools.tools import get_available_tools
for t in get_available_tools():
    print(t.name)
"

# 测试 MCP 工具能否被 LLM 调用
docker exec -w /app/backend -e PYTHONPATH=. ideer-gateway /app/backend/.venv/bin/python3 -c "
import asyncio
from ideer.models.vllm_provider import VllmChatModel
from ideer.mcp.cache import get_cached_mcp_tools
async def test():
    tools = get_cached_mcp_tools()
    llm = VllmChatModel(model='模型名', base_url='http://地址/v1', api_key='key')
    resp = await llm.bind_tools(tools).ainvoke('使用工具查询')
    print('tool_calls:', resp.tool_calls)
asyncio.run(test())
"
```

### 日志相关

```bash
# 查看 MCP 相关日志
docker logs ideer-gateway 2>&1 | grep -iE "mcp|tool" | tail -20

# 查看工具加载结果
docker logs ideer-gateway 2>&1 | grep "Total tools loaded"

# 查看是否有 tool_call（验证 function calling）
docker logs ideer-gateway 2>&1 | grep -iE "tool_calls|ToolCall|ToolNode" | tail -10

# 查看错误日志
docker logs ideer-gateway 2>&1 | grep -iE "error|exception|failed" | tail -20
```

### 模型相关

```bash
# 测试模型 function calling 支持
docker exec -w /app/backend -e PYTHONPATH=. ideer-gateway /app/backend/.venv/bin/python3 -c "
import asyncio
from ideer.models.vllm_provider import VllmChatModel
from langchain_core.tools import tool
async def test():
    llm = VllmChatModel(model='模型名', base_url='http://地址/v1', api_key='key')
    @tool(description='get weather')
    def get_weather(city: str) -> str: return city + ' sunny'
    resp = await llm.bind_tools([get_weather]).ainvoke('查北京天气')
    print('tool_calls:', resp.tool_calls)
asyncio.run(test())
"
```

---

## 附录：容器内注意事项

| 项目 | 说明 |
|------|------|
| Python 路径 | 必须用 `/app/backend/.venv/bin/python3`，系统 Python 缺少依赖 |
| PYTHONPATH | 需要设置为 `.` 或 `/app/backend`，否则 import 路径不对 |
| curl | 容器内通常没有 curl，用 Python `urllib.request` 替代 |
| 工作目录 | 用 `-w /app/backend` 或 `-e PYTHONPATH=.` 确保 import 正确 |
| 环境变量 | 用 `-e KEY=VALUE` 传递，或从容器已有的 environment 中读取 |

---

> 本文档基于 2026 年 6 月实际排障经验整理，覆盖 iDeer 平台 Docker 内网部署场景。
> 如遇本文档未覆盖的问题，请按排障流程逐层检查日志定位根因。
