# 测试 Lane 运行手册

> audience: developers, testers, release maintainers<br>
> status: current<br>
> owner: test maintainers<br>
> last-verified: 2026-09-11<br>
> canonical-path: `docs/testing/test-lane-runbook.md`

`scripts/run-test-lane.sh` 是测试 lane 的唯一权威入口。本手册说明如何
运行、判定和交接跨端 PR 与交付级验证；具体覆盖责任见
[覆盖矩阵](coverage-matrix.md)。

## 选择与运行

| 目标 | 命令 | 包含内容 |
| --- | --- | --- |
| 跨端 PR 验证 | `UV_CACHE_DIR=/tmp/deer-flow-uv-cache bash scripts/run-test-lane.sh pr-standard` | runtime boundary、backend-standard、frontend-standard、frontend-smoke |
| 交付/全量验收 | `UV_CACHE_DIR=/tmp/deer-flow-uv-cache bash scripts/run-test-lane.sh core-full` | runtime boundary、backend-full（含 serial）、frontend-core（coverage + check）、frontend-mock-e2e |

`pr-standard` 是 PR gate；`core-full` 只在明确的交付或完整验收时运行。
后者必须在候选提交上独立执行，不能以历史通过记录代替。

## 受限环境处理

- 受限环境运行后端命令时设置 `UV_CACHE_DIR=/tmp/deer-flow-uv-cache`，避免
  uv 写入只读的用户缓存目录。
- 若网络或 socket 测试在受限沙箱中出现 `PermissionError: [Errno 1]
  Operation not permitted`，将该次结果标为环境受限，保留错误与命令，并在
  允许本地 socket 的环境重新运行同一 lane。不要修改产品代码或测试来绕过
  该环境限制。
- 不得将挂起、超时或尚未输出最终汇总的测试称为通过。交接时记录命令、已
  运行时间和最后一个可见测试；状态为 `incomplete`。

## 判定与交接

以每个子 lane 和父 lane 输出的 `TEST_LANE_DURATION ... status=0` 以及测试
最终汇总为通过依据。单条框架 warning、Vitest 性能建议或 mock 浏览器运行中
不影响断言的代理连接日志不能单独推翻通过结论；仍应在交接中记录，并在与
预期不同或导致测试失败时排查。

交接记录应包含：候选提交、完整命令和环境、每个子 lane 的时长与测试计数、
skip/warning 概要、父 lane exit code，以及任何未运行的 specialty lane（如
blocking-I/O、visual、a11y、real-model）。

## 已验证示例：2026-09-10 PR 标准通道

在允许本地 socket 的环境执行
`UV_CACHE_DIR=/tmp/deer-flow-uv-cache bash scripts/run-test-lane.sh pr-standard`
后，父 lane 以 `status=0` 结束，累计 1,337 秒：

| 子 lane | 结果 | 时长 |
| --- | --- | --- |
| backend-standard | 11,973 passed，19 skipped，379 warnings | 739 秒 |
| frontend-standard | 357 files、9,965 tests passed | 449 秒 |
| frontend-smoke | 21 passed | 149 秒 |

此前在受限沙箱的首次 backend-standard 运行有 17 个 socket 权限失败；在允许
本地 socket 的环境重跑后，设备临时服务与端口分配测试均通过。浏览器 smoke
期间前端代理曾记录 `127.0.0.1:8001` 连接拒绝，但 21 个 mock smoke 断言全部
通过，因此该日志被记录为环境观察，而不是 lane 失败。

本示例只证明该次 `pr-standard` 运行；它不表示本次已运行 `core-full`。
