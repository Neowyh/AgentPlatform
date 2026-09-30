# 归零智能体工具链切片收口清单（2026-09-30）

切片规格：`docs/plans/2026-09-30-fault-zeroing-toolchain-spec.md`（T1–T5 已实现）。
本清单记录交付后需要运维/部署侧完成的三件事；代码仓库本身无需再改动。

## 1. 本地 config.yaml 的废弃 custom_agents 清理（运维动作）

`config.yaml` 是 git-ignored 的本地配置。历史上归零工作流曾在 `subagents.custom_agents`
下声明 5 个子智能体；工作流 V2 化后，节点提示词与 bundled 的
`resources/agents/fault-zeroing` 已完全接管这些职责，这 5 个声明成为死配置——
它们不会被 bundled 资源引用，但会继续注册为可用子智能体，干扰排障与安全审计。

动作：从本地 `config.yaml` 删除 `subagents.custom_agents` 下的以下 5 个声明：

- `evidence-reader`
- `fault-tree-builder`
- `probability-assessor`
- `root-cause-analyst`
- `report-reviewer`

若 `subagents.custom_agents` 下没有其他条目，可整块移除。`config.example.yaml`
已无此块，仓库文件无需改动。

## 2. 已安装环境需要重新发布归零资源

本切片修改了 bundled 资源内容：`resources/workflows/fault-zeroing.yaml` 节点提示词
收敛（T5）、`resources/skills/fault-zeroing/references/evidence_rules.md` 增补静态告警
分级约束（T5）、Scanner Status 契约披露门（T4）、`code` 工具组与
`analyze_code_evidence` / `read_binary_hex` 注册（T1/T3）、GB18030 编码嗅探（T2）。
bundled 资源按内容哈希版本化：网关启动时会自动 seeding（`conflict_policy="keep"`），
未在本地改过的资源会自动发布新版本；被本地改过的资源会被跳过。

动作：

- 常规环境：重启网关（`make start` / 重新部署）即可，启动 seeding 自动为归零
  Agent / Skill / Workflow 发布新版本；
- bundled 资源被本地改过的环境：显式执行
  `python scripts/seed_bundled_resources.py --manifest bundled-resources.json --source-root . --owner <super_admin_id> --conflict-policy override`
  （内网 Docker 环境可走 `scripts/deploy-intranet.sh` 中的同款 seeding 步骤）。

未重新发布前，运行仍走旧定义，不会获得披露门与新工具。

另外：`backend/Dockerfile` 新增 clang-tidy / cppcheck——需要重建镜像后静态扫描器才
实际可用；未重建前 `scanner_status.json` 会如实披露 `scanners_unavailable`，这是披露门
的设计场景（如实记录“未扫描”），不是故障。

## 3. API 响应形状变化（T3）

代码证据包 manifest 的 `accepted` 条目从纯路径字符串改为对象（T3 二进制白名单落地）：

- 旧：`{"accepted": ["src/main.c", ...]}`
- 新：`{"accepted": [{"path": "src/main.c", "binary": false, "bytes": 1234}, ...]}`

兼容性：旧字符串 manifest 在 Run 物化时仍可 round-trip（读取兼容保留），但新写入的
manifest 一律是对象。直接消费 manifest JSON 的外部脚本需要按“条目可能是字符串或
对象”做兼容读取。
