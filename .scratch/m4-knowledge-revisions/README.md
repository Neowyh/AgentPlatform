# M4 Revision、Publish 与 Run Snapshot

**Type:** ticket index
**Status:** ready-for-agent
**Labels:** ready-for-agent
**Execution prerequisite:** M3 完成并通过 Gate 4；执行前核实当前候选的验收证据。

本拆分已由用户确认。依据后续工作总方案 M4 任务卡、知识专项方案的 Revision／发布门禁／Run Snapshot／对账章节，以及知识双层真源 ADR。沿用 canonical KnowledgeBase、Knowledge Revision、LIVE／PINNED 和 Effective Knowledge Scope 术语。

## 任务索引

| 票 | 阻塞于 | 交付 |
| --- | --- | --- |
| [01：创建与查看 Revision 候选](issues/01-revision-candidate.md) | M3 Gate 4 | 固定文档与配置的候选及版本页 |
| [02：发布不可变 Revision](issues/02-immutable-revision-publish.md) | 01 | 独立 Published Dataset 与发布门禁 |
| [03：LIVE Run 冻结](issues/03-live-run-snapshot.md) | 02 | Agent／Workflow 运行使用启动时版本 |
| [04：PINNED 版本运行](issues/04-pinned-revision-run.md) | 03 | 指定已发布版本的依赖与运行 |
| [05：对账与漂移可见性](issues/05-revision-reconciliation.md) | 02 | 定期／按需检查与管理员异常视图 |
| [06：Gate 5／6 验收](issues/06-gate5-gate6-acceptance.md) | 04、05 | 真实 provider 版本冻结与跨层验收 |

每票只在其阻塞解除后进入可执行集合。05 不依赖 03／04，但总方案的串行排期仍有效，默认按编号执行；依赖图不授予并行实施权限。

## 共通验收约束

每张功能票包含必要的持久化、canonical API、相关界面及聚焦行为验证。以 API 可观察行为为主，浏览器操作和真实 RAGFlow 验收为辅；每个切片执行聚焦测试，06 汇总最终候选证据。遵循仓库 TDD、GitNexus impact、测试 inventory/preflight 和 lane 规则。

`ready-for-agent` 表示任务描述已就绪，不代表 M3 前置已通过。此次只发布任务票，不执行产品变更或验收，不修改 M3 父级任务。M5 完整 Retrieval Receipt／Evidence UI、M6 Eval 引擎及自动 orphan 清理不在本任务包范围内。
