# iDeer Workflows

此目录存放 schema v2 的 YAML 格式工作流定义文件。捆绑工作流（含
fault-zeroing）通过 canonical bundled resource module 幂等发布
（`scripts/seed_bundled_resources.py` + `bundled-resources.json`），
不使用独立的 seed 脚本。

## 快速开始

1. 工作台页面点击 **工作流 → 新建**（捆绑的 fault-zeroing 已由
   canonical bundle 自动发布）
2. 编写 YAML 定义（参考下方格式与 `resources/workflows/fault-zeroing.yaml`）
3. 保存后点击 **运行**，填入输入参数

## YAML 格式（schema_version: 2）

```yaml
schema_version: 2
name: my-workflow          # 必填，唯一标识
description: 工作流描述     # 可选
inputs:                    # 输入参数定义
  upload_dir:
    type: string
    required: true
    description: "上传目录（沙箱虚拟路径）"
entrypoint: start
nodes:
  - id: start              # 节点唯一 ID
    type: action           # action | route | fork | join | interrupt
    action:
      kind: agent          # 仅 agent 支持 file_access
      name: some-agent
      file_access:
        read:
          - "/mnt/user-data/uploads"            # 或 {{inputs.xxx}} 模板
        write:
          - "{{inputs.output_base_dir}}/artifacts/a.json"
    writes:                # 节点输出写入的 state 字段
      - "$.state.result"
edges:
  - from: start
    to: next_node
```

## 虚拟路径与产物门禁

工作流沙箱只允许 **虚拟路径**，宿主路径（如 `/tmp/...`、`/home/...`）在提交运行
时直接返回 400：

| 前缀 | 语义 | 可写 |
|------|------|------|
| `/mnt/user-data/{workspace,uploads,outputs}` | 该次运行专属数据目录 | 是 |
| `/mnt/skills/<skill>` | 公共技能目录 | 否 |
| `/mnt/acp-workspace` | ACP 工作区 | 否 |
| 配置的自定义 mount 容器路径 | 按 `config.yaml` 的 `mount.read_only` | 视配置 |

file_access 的 write 根是 **产物门禁**：节点执行结束后，若声明的文件根不存在或
为空、目录根不存在，运行进入 `paused` 状态等待人工处理；恢复（resume）后重新
验证，直到产物齐备或人工取消。运行详情页可以浏览、预览和下载 write 根下的产物
文件。

## 节点类型

| 类型 | 说明 | 必填字段 |
|------|------|----------|
| `action` | 调用 agent / tool（agent 可声明 file_access） | `action` |
| `route` | 按表达式分支 | `expression`, `routes` |
| `fork` | 并行启动分支 | `branches`, `join` |
| `join` | 等待 fork 分支汇合 | `fork` |
| `interrupt` | 人工审批断点（触发 paused 等待 resume） | `roles` |

## 示例

- `fault-zeroing.yaml`：归零排故全流程（fork 并行 → 审查 → 评估 → 纠正 → 文档），
  完整的 file_access 与产物门禁用法
- `example-data-analysis.yaml`：简单数据分析示例
