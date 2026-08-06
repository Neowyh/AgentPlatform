# 工程文档入口

> audience: developers, operators, testers, maintainers<br>
> status: current<br>
> owner: repository maintainers<br>
> last-verified: 2026-07-15<br>
> canonical-path: `docs/README.md`

这里是开发、运维、测试和内部治理文档的入口。面向最终用户和公开开发者的产品说明，请从[公开文档站](/zh/docs)或[英文文档站](/en/docs)开始；`skills/**` 及其专用资料不属于本入口的治理范围。

## 按读者进入

- [开发人员](development/README.md)：开发环境、架构、后端参考、扩展和设计决策。
- [运维人员](operations/README.md)：安装、部署、配置、升级、监控、备份和排障。
- [测试人员](testing/README.md)：测试分层、覆盖矩阵、E2E、真实浏览器测试和迁移账本。
- [架构与治理](architecture/README.md)：系统边界、产品线约束和决策入口。

## 当前权威文档

每个主题只保留一个当前事实来源；入口页只提供适用范围和跳转，不复制正文。

| 主题 | 当前权威来源 |
| --- | --- |
| 用户使用与公开开发 | [前端公开文档站](/zh/docs) |
| 后端架构与 API | [backend/docs/README.md](../backend/docs/README.md) |
| 测试覆盖与迁移 | [coverage-matrix.md](testing/coverage-matrix.md)、[test-migration-ledger.md](testing/test-migration-ledger.md) |
| 权限模型与矩阵 | [permission-model-redesign.md](permission-model-redesign.md)、[permission-matrix.md](permission-matrix.md) |
| 离线产品线治理 | [offline-product-line-governance-plan.md](offline-product-line-governance-plan.md) |
| 离线部署作业 | [禁公网内网离线部署作业指导书](deployment/禁公网内网离线部署作业指导书.md) |
| 当前工程待办 | [backlog.md](backlog.md) |

## 历史证据

已结束的计划、审计、事故复盘和阶段总结进入 [`docs/archive/`](archive/README.md)。历史正文已物理迁移，旧路径不保留跳转桩；评估依据见[文档留存必要性评估](document-retention-assessment.md)。
