# Workflow 引擎

## 概述

Workflow 模块提供基于 YAML DSL 的声明式工作流编排引擎，支持多步骤、条件分支、并行执行、循环、人工审批，并通过 API 网关对外暴露完整的 CRUD 与运行管理接口。

---

## YAML DSL 语法参考

### 顶层字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | string | 是 | — | 工作流名称，全局唯一 |
| `description` | string | 否 | `""` | 工作流描述 |
| `version` | string | 否 | `"1.0"` | 版本号 |
| `inputs` | map | 否 | `{}` | 输入参数定义，见下方 |
| `steps` | list | 否 | `[]` | 步骤列表，按顺序执行 |
| `triggers` | list | 否 | null | 触发器定义（预留） |

### inputs 参数定义

`inputs` 是一个 `name -> param` 的映射。`param` 支持简写和完整写法：

```yaml
inputs:
  # 简写：只指定类型
  topic: string

  # 完整写法
  max_results:
    type: integer
    required: true
    default: 10
    description: "最大返回条数"
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | string | `"string"` | 参数类型（string / integer / boolean 等） |
| `required` | bool | `false` | 是否必填 |
| `default` | any | null | 默认值 |
| `description` | string | `""` | 参数描述 |

### Step 公共字段

每个 step 都有以下公共字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 步骤唯一标识，用于变量引用 |
| `type` | string | 是 | 步骤类型，见下方 6 种类型 |
| `condition` | string | 否 | 执行条件表达式，为 falsy 时跳过该步骤 |
| `timeout` | int | 否 | 超时时间（秒） |
| `retry` | object | 否 | 重试策略，见下方 |
| `on_error` | string | 否 | 错误处理策略，`"skip"` 表示跳过继续 |

### retry 重试策略

```yaml
retry:
  max: 3            # 最大重试次数，默认 3
  backoff: 5.0      # 退避基数（秒），实际等待 = backoff * attempt
  on_errors: ["*"]  # 匹配的错误类型，默认 "*" 匹配所有
```

---

### 6 种 Step 类型

#### 1. agent -- 调用 Agent

调用一个已注册的 Agent 执行任务。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent` | string | 是 | Agent 名称 |
| `prompt` | string | 否 | 发送给 Agent 的提示词，支持模板变量 |

```yaml
- id: research
  type: agent
  agent: researcher
  prompt: "请调研以下主题：{{inputs.topic}}"
```

#### 2. tool -- 调用工具

直接调用一个工具，不经过 Agent。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tool` | string | 是 | 工具名称 |
| `params` | object | 否 | 工具参数，支持模板变量 |

```yaml
- id: fetch_data
  type: tool
  tool: web_search
  params:
    query: "{{inputs.topic}}"
    max_results: "{{inputs.max_results}}"
```

#### 3. human_review -- 人工审批

暂停工作流，等待人工审批后继续。执行时状态变为 `waiting_human`。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message` | string | 否 | 展示给审批人的消息 |
| `input_schema` | object | 否 | 审批表单的 JSON Schema |
| `approvers` | list[string] | 否 | 审批人列表 |

```yaml
- id: review
  type: human_review
  message: "请审批以下内容"
  approvers:
    - admin@example.com
```

#### 4. condition -- 条件分支

根据表达式结果执行 `then` 或 `else` 分支。分支可以是内联步骤定义或 `goto:step_id` 跳转。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `expression` | string | 是 | 条件表达式，支持模板变量 |
| `then` | string/object | 否 | 条件为真时执行：step id 或内联步骤 |
| `else` | string/object | 否 | 条件为假时执行：step id 或内联步骤 |

```yaml
# 内联分支
- id: check_score
  type: condition
  expression: "{{steps.grade.output.score}} > 80"
  then:
    id: high_score
    type: agent
    agent: congratulator
  else: notify_improve

# 跳转分支
- id: notify_improve
  type: tool
  tool: send_notification
```

#### 5. parallel -- 并行执行

并行执行一组子步骤，所有子步骤完成后汇总结果。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `steps` | list[StepDef] | 是 | 并行执行的子步骤列表 |

```yaml
- id: parallel_tasks
  type: parallel
  steps:
    - id: task_a
      type: agent
      agent: worker_a
    - id: task_b
      type: agent
      agent: worker_b
```

#### 6. loop -- 循环执行

遍历一个列表，对每个元素执行子步骤。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `items` | string | 是 | 待遍历的列表表达式，支持模板变量 |
| `steps` | list[StepDef] | 是 | 每次迭代执行的子步骤 |

```yaml
- id: process_items
  type: loop
  items: "{{steps.prepare.output.items}}"
  steps:
    - id: handle_item
      type: agent
      agent: processor
      prompt: "处理：{{inputs.current_item}}"
```

---

## 变量引用

模板引擎支持 `{{expression}}` 语法，在 `prompt`、`params`、`expression`、`items` 等字段中使用。

### 两种引用来源

| 语法 | 含义 | 示例 |
|------|------|------|
| `{{inputs.xxx}}` | 引用工作流输入参数 | `{{inputs.topic}}` |
| `{{steps.xxx.output}}` | 引用某步骤的输出 | `{{steps.research.output}}` |
| `{{steps.xxx.output.field}}` | 引用输出的嵌套字段 | `{{steps.research.output.summary}}` |
| `{{steps.xxx.status}}` | 引用某步骤的状态 | `{{steps.review.status}}` |

### 类型保留规则

- **全字符串模板**：整个值是单个 `{{expr}}` 时，返回原始类型（dict / list / int 等不丢失）
- **部分模板**：模板中混有其他文本时，所有 `{{expr}}` 被替换为字符串拼接

```yaml
# 全字符串模板 -- params 保持 dict 类型
params: "{{steps.fetch.output}}"

# 部分模板 -- 结果是 string
prompt: "请调研以下主题：{{inputs.topic}}，最多返回 {{inputs.max_results}} 条"
```

---

## 快速上手

### 1. 编写 YAML

创建文件 `hello_workflow.yaml`：

```yaml
name: hello_world
description: 最简单的工作流示例
version: "1.0"

inputs:
  name:
    type: string
    required: true
    description: "用户名称"

steps:
  - id: greet
    type: agent
    agent: greeter
    prompt: "请向 {{inputs.name}} 打招呼"
```

### 2. 通过 API 创建

```bash
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "name": "hello_world",
    "yaml_content": "name: hello_world\ndescription: 最简单的工作流示例\nversion: \"1.0\"\ninputs:\n  name:\n    type: string\n    required: true\nsteps:\n  - id: greet\n    type: agent\n    agent: greeter\n    prompt: \"请向 {{inputs.name}} 打招呼\"\n"
  }'
```

### 3. 运行工作流

```bash
curl -X POST http://localhost:8000/api/workflows/hello_world/run \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"name": "张三"}}'
```

返回：

```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "workflow": "hello_world"
}
```

### 4. 查询运行状态

```bash
curl http://localhost:8000/api/workflows/hello_world/runs/550e8400-e29b-41d4-a716-446655440000
```

---

## API 端点列表

所有端点前缀为 `/api/workflows`，认证通过 RBAC 用户体系。

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| `GET` | `/api/workflows` | 列出所有工作流 | 公开 |
| `GET` | `/api/workflows/{name}` | 获取工作流详情（含 YAML 和解析结果） | 公开 |
| `POST` | `/api/workflows` | 创建工作流（提交 YAML） | 部门管理员 / 超级管理员 |
| `PUT` | `/api/workflows/{name}` | 更新工作流 YAML | 部门管理员 / 超级管理员 |
| `DELETE` | `/api/workflows/{name}` | 删除工作流 | 超级管理员 |
| `POST` | `/api/workflows/{name}/run` | 启动一次工作流执行 | 公开 |
| `GET` | `/api/workflows/{name}/runs` | 列出该工作流的运行历史 | 公开 |
| `GET` | `/api/workflows/{name}/runs/{run_id}` | 查询单次运行的状态详情 | 公开 |
| `POST` | `/api/workflows/{name}/runs/{run_id}/review` | 提交人工审批结果，恢复暂停的工作流 | 需登录 |

---

## 状态流转

### RunStatus 枚举值

| 状态 | 说明 |
|------|------|
| `pending` | 已创建，尚未开始执行 |
| `running` | 正在执行中 |
| `waiting_human` | 暂停等待人工审批 |
| `completed` | 所有步骤执行成功，工作流完成 |
| `failed` | 某步骤执行失败且未设置 `on_error: skip` |
| `cancelled` | 工作流被取消 |

### 状态转换规则

```
pending
  |
  v
running ------------------------------------+
  |                                         |
  | (遇到 human_review 步骤)                | (遇到异常)
  v                                         v
waiting_human                            failed
  |                                         ^
  | (提交审批结果)                            |
  v                                         |
running --- (所有步骤完成) ---> completed    |
  |                                         |
  | (某步骤失败 + on_error != skip) ---------+
  |
  +--- (某步骤失败 + on_error == skip) --> 继续下一步
```

关键规则：

1. 工作流启动后状态从 `pending` 变为 `running`
2. 遇到 `human_review` 步骤时状态变为 `waiting_human`，通过 review API 提交结果后恢复为 `running`
3. 所有步骤执行成功后状态变为 `completed`
4. 步骤失败时：若 `on_error` 设置为 `"skip"`，跳过该步骤继续执行；否则状态变为 `failed`
5. 每个步骤执行完毕后状态会持久化到数据库，支持断点恢复
6. 重试策略生效时，失败步骤会按 `retry.backoff * attempt` 的间隔重试，直到 `retry.max` 次数用尽
