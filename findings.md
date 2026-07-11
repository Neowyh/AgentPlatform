# Findings & Decisions: 测试体系完整化重构

## Requirements

- 继续执行当前测试体系完整化计划，直到计划中的验收条件全部满足。
- 结构目标、覆盖率目标、完整验证、artifact 清理和 review 视角都属于完成定义。
- 不能用结构迁移完成替代整体目标完成。

## Current Findings

- 后端根目录 `backend/tests/test_*.py` 已清空。
- 前端根目录 `frontend/tests/*.spec.ts(x)` 已清空。
- `docs/testing/coverage-matrix.md` 已记录按能力域划分的测试矩阵。
- `docs/testing/test-migration-ledger.md` 已记录迁移、重命名、删除和 false positive 说明。
- 前端当前 statement coverage 为 `96.90%`，最大缺口集中在：
  - `src/components/ai-elements/prompt-input.tsx`
  - `src/components/workspace/settings/tool-settings-page.tsx`
  - `src/app/workspace/admin/users/page.tsx`
  - `src/core/threads/hooks.ts`
  - `src/components/ui/magic-bento.tsx`
  - `src/app/workspace/admin/departments/page.tsx`
  - `src/app/workspace/admin/visibility-applications/page.tsx`
  - `src/core/api/api-client.ts`
- 后端当前 coverage 为 `97%`，旧 `coverage.json` 显示最大缺口集中在 gateway routers、client 和 storage 相关模块；但已有一批新增测试，后端需要重新生成全量 coverage 后再按真实缺口补。
- 当前仍存在 generated artifacts，需要在最终收口阶段清理。

## Decisions

| Decision | Rationale |
| --- | --- |
| 先补前端 coverage | 前端 coverage 缺口已精确到 JSON，能快速推进到 98%。 |
| 后端先重新跑 full coverage 再补 | 旧后端缺口数据未包含最新 SkillStorage 等测试，直接按旧数据补会浪费。 |
| 优先补真实行为测试 | 防止新增覆盖率测试又退化成 `coverage/boost/gaps` 风格。 |
| 暂不清理 artifacts | 完整验证还会重新生成 artifacts，最终统一清理更稳。 |

## Risks

- Playwright 全项目执行可能暴露环境依赖或服务启动问题。
- 大量 staged rename 和 untracked 新测试混在一起，最终需要仔细整理 review 视角。
- `AGENTS.md`、`CLAUDE.md` 等非测试文件已有改动，最终需要确认是否属于本轮任务。
