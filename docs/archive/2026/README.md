# 2026 年历史文档

> audience: maintainers, auditors, incident reviewers<br>
> status: current<br>
> owner: repository maintainers<br>
> last-verified: 2026-07-15<br>
> canonical-path: `docs/archive/2026/README.md`

本目录登记已结束的计划、审计和阶段性材料。历史正文已物理迁移到本目录；旧路径不再保留跳转桩。登记项中的 canonical path 是归档后的主题入口。

## 已归档主题

| 主题 | 原始材料 | 结论与当前替代入口 |
| --- | --- | --- |
| 测试体系重组 | [`testing/multi-role-testing.md`](testing/multi-role-testing.md) | 原 QA 说明过时；以 [`docs/testing/coverage-matrix.md`](../../testing/coverage-matrix.md) 和迁移账本为准。 |
| 权限模型审计 | [`permission/permission-model-audit-2026-07-05.md`](permission/permission-model-audit-2026-07-05.md) | 审计证据保留；设计以 [`docs/permission-model-redesign.md`](../../permission-model-redesign.md) 为准。 |
| 企业内网优化方案 | [`optimization/`](optimization/) | 计划与阶段路线归档；当前运维入口为离线部署作业指导书。 |
| 测试计划与验证报告 | [`testing/`](testing/) | 计划、差距分析和验证日志归档；当前责任以测试规范、覆盖矩阵和迁移账本为准。 |
| AI 测试工具评估 | [`testing/ai-test-tools-integration.md`](testing/ai-test-tools-integration.md) | 工具选型和验证证据归档；不作为默认测试门禁。 |
| 离线分支问题与变更报告 | [`offline/`](offline/) 和归档根目录 | 分支历史证据归档；当前分支和发布规则以离线产品线治理方案为准。 |
| 文档盘点与导入决策 | [`governance/document-system-audit-2026-06-28.md`](governance/document-system-audit-2026-06-28.md)、[`decisions/intranet-source-import-decision-2026-07-15.md`](decisions/intranet-source-import-decision-2026-07-15.md) | 历史盘点和决策证据归档；当前入口以 `docs/README.md` 和 `docs/decisions/README.md` 为准。 |

## 归档规则

归档文档保留来源、日期和结论，不作为当前操作步骤。需要删除时，必须先完成全量引用扫描、内容覆盖审查和人工确认。
