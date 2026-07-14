# 本次任务简报：本地启动预检与归零智能体约束补强

## 任务范围

1. 继续执行既有未完成计划，确认 `task_tool` 的 callbacks 兼容性修复已在当前 HEAD 中完成。
2. 补充本地生产模式启动预检脚本 `scripts/start-local.sh`。
3. 强化归零排故智能体的固定执行阶段、资料盘点、故障树 JSON schema 和自检要求。
4. 按计划完成测试校验、影响分析、代码审查和提交。

## 主要变更

- 新增 `scripts/start-local.sh`：从仓库根目录启动本地生产模式，预检 `make`、`python3`、`node`、`pnpm`、`uv`、配置文件和必需环境变量。
- 新增 `backend/tests/test_start_local_script.py`：覆盖脚本语法、正常打印命令、缺失环境变量、非法环境变量名、缺失配置、非法 make target 和异常参数。
- 更新 `README.md`、`CLAUDE.md`：补充本地启动预检脚本说明。
- 更新 `AGENTS.md`、`CLAUDE.md` 中 GitNexus 索引统计：执行 `npx gitnexus analyze` 后自动同步。
- 更新 `docs/fault-zeroing-agent/agent/SOUL.md` 和 `skills/custom/fault-zeroing/SKILL.md`：固定分析阶段、限制反复委托、强化五件套产物和 schema 自检。

## 验证记录

- `npx gitnexus analyze`：通过，索引刷新到 23,959 nodes、43,867 edges、833 clusters、300 flows。
- GitNexus impact：`scripts/start-local.sh` 文件级影响为 LOW，直接调用方 0，受影响流程 0。
- `cd backend && uv run pytest tests/test_start_local_script.py tests/test_task_tool_core_logic.py`：50 passed，1 个第三方依赖 deprecation warning。
- `cd backend && uv run ruff check tests/test_start_local_script.py`：All checks passed。
- `git diff --check`：通过，无空白错误。
- `git diff --cached --check`：通过，无空白错误。
- 提交钩子：ruff lint passed，ruff format passed，frontend eslint/prettier 因无相关文件跳过。

## 审查结论

CodeRabbit CLI 可用，但 `coderabbit auth login --agent` 失败，错误为 `authentication_failed: Failed to start server. Is port 0 in use?`，因此本次未生成 CodeRabbit 审查结果。

已完成一次人工代码审查，重点检查 shell 输入校验、`sh -c` 移除、测试覆盖、文档同步和归零智能体约束一致性，未发现需要继续修复的阻断问题。`shellcheck` 未安装，未能执行该项额外静态检查。

## 提交记录

- `dd2a23f2 fix(startup): add local start preflight`
