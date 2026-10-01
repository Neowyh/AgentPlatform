# 测试文档

> audience: testers, developers, release maintainers<br>
> status: current<br>
> owner: test maintainers<br>
> last-verified: 2026-10-01<br>
> canonical-path: `docs/testing/README.md`

测试治理按职责分开维护；同一规则只在其权威文档中定义：

- [覆盖矩阵](coverage-matrix.md)：能力与测试层级的责任映射。
- [测试迁移账本](test-migration-ledger.md)：测试移动、删除和等价覆盖的验收依据。
- [测试 Lane 运行手册](test-lane-runbook.md)：PR 与交付级 lane 的运行、判定和交接规则。
- [测试清单](../../scripts/test_inventory.py)：复用文件发现结果，输出文件、节点、lane 归属和收集状态。
- [运行前检查](../../scripts/test_preflight.py)：按 lane 检查工具、锁文件、浏览器、可写目录和 socket 条件。

执行入口：

- [通用测试规范](../testing-guidelines.md)
- [前端 smoke 与工作流 E2E](../../frontend/tests/e2e/)
- [后端测试](../../backend/tests/)

历史测试计划、差距分析和验证记录只作为[归档证据](../archive/README.md)，不能单独授权删除测试或放宽断言。

文档状态使用 `current`、`draft`、`superseded` 和 `archived`。当前候选的验证记录必须写明提交或 diff 指纹、命令、环境、依赖与配置、结果和耗时。历史样例只说明历史运行，不能替代当前候选的验收。测试责任以覆盖矩阵为准，发现和执行归属以测试清单为准，删除或迁移依据以迁移账本为准。
