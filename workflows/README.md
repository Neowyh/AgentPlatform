# iDeer Workflows

此目录存放 YAML 格式的工作流定义文件。

## 快速开始

1. 在工作台页面点击 **工作流 → 新建**
2. 编写 YAML 定义（参考下方示例）
3. 保存后点击 **运行**

## YAML 格式

```yaml
name: my-workflow          # 必填，唯一标识
description: 工作流描述     # 可选
version: "1.0"             # 可选

inputs:                    # 输入参数定义
  param1:
    type: string
    required: true
    default: "默认值"
    description: "参数说明"

steps:                     # 执行步骤
  - id: step1              # 步骤唯一 ID
    type: agent            # 步骤类型
    agent: agent-name      # 使用的 Agent
    prompt: "提示词"        # 支持 {{inputs.xxx}} 和 {{steps.xxx.output}} 模板
```

## 步骤类型

| 类型 | 说明 | 必填字段 |
|------|------|----------|
| `agent` | 调用 AI Agent | `agent`, `prompt` |
| `tool` | 调用工具 | `tool`, `params` |
| `human_review` | 人工审核 | `message` |
| `condition` | 条件分支 | `expression` |
| `parallel` | 并行执行 | `steps` |
| `loop` | 循环遍历 | `items`, `steps` |

## 示例

参考 `example-data-analysis.yaml`。
