# 测试执行日志

> 按批次记录测试→修复→审查→回归的完整过程。

---

## B1b: Config/Admin/启动 — ✅ 一次性通过

| 阶段 | 状态 | 详情 |
|------|------|------|
| **测试** | ✅ 通过 | 759 passed, 0 failed, 1 skipped (37.28s) |
| **修复** | ⏭️ 跳过 | 无失败用例，无需修复 |
| **审查** | ⏭️ 跳过 | 无代码变更，无需审查 |
| **回归** | ⏭️ 跳过 | 无代码变更，无需回归 |

**命令:** `uv run pytest tests/ -v -k "app_config or admin_router or setup or ensure or reset or initialize or config_version or extensions or acp or dev_entrypoint"`

**备注:** 7 个非关键警告（RuntimeWarning: unawaited coroutine, DeprecationWarning: starlette cookie）

---

## B1d: 数据库迁移 — ✅ 一次性通过

| 阶段 | 状态 | 详情 |
|------|------|------|
| **测试** | ✅ 通过 | 19 passed, 0 failed, 0 skipped (15.40s) |
| **修复** | ⏭️ 跳过 | 无失败用例，无需修复 |
| **审查** | ⏭️ 跳过 | 无代码变更，无需审查 |
| **回归** | ⏭️ 跳过 | 无代码变更，无需回归 |

**命令:** `uv run pytest tests/test_alembic_migrations.py -v`

**备注:** 1 个非关键警告（LangChainPendingDeprecationWarning）
