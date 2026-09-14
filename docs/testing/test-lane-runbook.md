# 测试 Lane 运行手册

> audience: developers, testers, release maintainers<br>
> status: current<br>
> owner: test maintainers<br>
> last-verified: 2026-09-11<br>
> canonical-path: `docs/testing/test-lane-runbook.md`

`scripts/run-test-lane.sh` 是测试 lane 的唯一权威入口。本手册说明如何
运行、判定和交接跨端 PR 与交付级验证；具体覆盖责任见
[覆盖矩阵](coverage-matrix.md)。

新增或移动测试后运行 `python3 scripts/test_inventory.py --collect --json`。它保留
无法导入外部服务测试的静态归属；`collection_status` 为
`static-only` 时表示尚未执行框架收集；外部凭据专项在无法安全导入时保留静态归属。
普通后端测试会复用 pytest 的收集结果，`collection-error`/`not-collected` 会保留在报告中。
运行 lane 前的 preflight 只检查
存在性和可用性，不安装依赖、不打印凭据，也不连接真实业务数据。
CI 或迁移评审可追加 `--baseline <inventory.json>`，输出新增、删除和
lane 归属变化；删除、skip 或范围缩小时必须在迁移账本中记录覆盖迁移依据。

## 选择与运行

| 目标 | 命令 | 包含内容 |
| --- | --- | --- |
| 跨端 PR 验证 | `UV_CACHE_DIR=/tmp/deer-flow-uv-cache bash scripts/run-test-lane.sh pr-standard` | runtime boundary、backend-standard、frontend-standard、frontend-smoke |
| 交付/全量验收 | `UV_CACHE_DIR=/tmp/deer-flow-uv-cache bash scripts/run-test-lane.sh core-full` | runtime boundary、backend-full（含 serial）、frontend-core（coverage + check）、frontend-mock-e2e |
| 后端阻塞 I/O | `bash scripts/run-test-lane.sh backend-blocking-io` | Blockbuster runtime gate |
| 前端专项 | `bash scripts/run-test-lane.sh frontend-visual` / `frontend-a11y` | visual 或 accessibility E2E |
| 前端认证/真实后端 | `bash scripts/run-test-lane.sh frontend-auth` / `frontend-real` | auth-enabled 或已启动隔离后端的 E2E |
| Stagehand 专项 | `bash scripts/run-test-lane.sh frontend-stagehand` | AI 驱动浏览器测试；无显式凭据时标记未执行 |
| LLM 专项 | `bash scripts/run-test-lane.sh backend-llm` | 仅显式凭据，缺凭据时 skip |
| 外部构建专项 | `bash scripts/run-test-lane.sh backend-external` | 扩展安装、网络和本地服务；缺少条件时标记未执行 |

`pr-standard` 是 PR gate；`core-full` 只在明确的交付或完整验收时运行。
后者必须在候选提交上独立执行，不能以历史通过记录代替。

后端 standard 递归收集整个 `backend/tests/`，排除
`tests/blocking_io` 以及 `serial`、`requires_llm`、`live` marker；serial
lane 只运行离线 serial 用例。由于递归集合包含临时服务测试，两个后端
lane 都要求 preflight 先确认本地 socket 可创建。live/LLM、blocking-I/O、
visual、a11y 和 real E2E 必须由各自专项 lane 显式选择。

## 受限环境处理

- 受限环境运行后端命令时设置 `UV_CACHE_DIR=/tmp/deer-flow-uv-cache`，避免
  uv 写入只读的用户缓存目录。
- 前端 lane 使用 `TEST_PNPM_XDG`/`TEST_PNPM_HOME`（默认位于 `/tmp`）隔离
  pnpm 状态，并要求 `frontend/package.json` 的 `packageManager` 版本精确匹配。
 版本切换或签名下载失败时应先修复 Corepack/网络环境，不能用另一版本代替。
 前端 standard/core 只运行 Rstest、Vitest 和静态检查，不启动应用服务；Rstest
 本身会绑定本地 worker 端口，因此这两个 lane 也要求 socket 权限。smoke、mock
 E2E、visual 和 a11y 在启动浏览器 webServer 前同样要求 socket 权限。
- 若网络或 socket 测试在受限沙箱中出现 `PermissionError: [Errno 1]
  Operation not permitted`，将该次结果标为环境受限，保留错误与命令，并在
  允许本地 socket 的环境重新运行同一 lane。不要修改产品代码或测试来绕过
  该环境限制。
- `frontend-visual` 的 Chromium 预检若报告 `Target page, context or
  browser has been closed`，应检查浏览器 stderr 是否包含
  `sandbox_host_linux.cc ... Operation not permitted`。这表示执行沙箱阻止
  了 Chromium host process；即使追加 `--no-sandbox` 也可能失败。应改用
  允许 Chromium 子进程和 loopback bind 的宿主机、CI runner 或 Playwright
  容器安全配置，并复跑同一预检命令：
  `python3 scripts/test_preflight.py frontend-visual`。
- 只有同时看到 `Chromium launch: ready`、`local socket bind` 和
  `lane=frontend-visual status=ready` 才能开始视觉测试；环境探针失败时
  不得更新截图基线。
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

## 当前候选复验：2026-09-12

在允许本地 socket 的环境中，`test-preflight pr-standard`、`make doctor`、
测试契约和 runner 契约均通过。最近一次 `pr-standard` 完整复验耗时 1,471
秒，后端子 lane 为 25,648 passed、106 failed、144 skipped、816 warnings，
前端 standard 为 9,965 passed，smoke 为 29 passed；父 lane 以 `status=1`
结束。失败属于当前候选代码或测试装配契约，不能标记为环境通过；允许 socket
的 preflight 和所有环境检查均为 ready。迁移、资源治理、SQLite 配置、工作区
变更、运行查询和脚本调用等受影响集合已分别复验通过。Stagehand 因缺少显式
模型凭据按约定报告 `unexecuted`。

随后执行的 `core-full` 也在允许本地 socket 的环境启动并完成了后端与前端
core 子 lane：backend-full 为 25,660 passed、94 failed、144 skipped，
frontend-core 为 9,965 passed，均保留各自退出状态。frontend-mock-e2e 运行
到 220 passed、2 failed、1 interrupted、19 skipped 后停止，日志显示仍有
未覆盖请求连接 `127.0.0.1:8001`；父 lane 为 `status=130`。这证明组合 runner
会继续执行子 lane，同时明确记录 mock E2E 的服务装配缺口，不能将该次 core-full
标记为通过。

随后补齐 mock Gateway shell 请求并收紧移动端选择器后，thread-history、subtask
card 和 mobile sidebar 三个代表用例在允许浏览器权限的环境中均为 **3 passed**；
完整 348 用例集合随后复验为 **328 passed、1 failed、19 skipped**；剩余失败是
线程删除错误路径下的导航契约，未归因于环境或依赖。

修复 mock fixture 的线程状态隔离并将 mock lane 限定到根功能、smoke 和
workflows 目录后，`frontend-mock-e2e` 在允许本地 socket 的环境中收集
326 项并以 **326 passed、status=0** 结束（约 480 秒）。auth、real、visual、
a11y 和 Stagehand 目录由各自专项 lane 负责，不再混入该通道。

随后修复了授权路由、线程事件参数、非法线程 ID、异常响应 envelope、开发入口
同步、部署 extras 传播、MCP/subagent 路由挂载、健康检查契约和通知 trace
上下文，并重新执行 backend-standard。最近一次完整运行结果为 25,754
passed、0 failed、144 skipped、817 warnings，耗时约 900 秒；该次运行的父
lane 以 `status=0` 结束。该次运行已包含认证 envelope、严格线程准入、旧线程删除、SSE 心跳、事件查询兼容、bootstrap schema parity、subagent 管理、OpenViking MCP、身份上下文、lease 续期、并发内存事实、OIDC seam、canonical agent HTTP、上传事件循环和 sandbox retention 修复。日志仍可能显示可选 memory 更新尝试连接外部模型并失败；该后台更新不会改变测试结果，离线通道也不会把它当作业务调用成功。

本轮 `pr-standard` 组合复验中，backend-standard 为 25,754 passed、0 failed、
144 skipped，父子退出状态均保留；frontend-standard 的 Rstest 为 120 files /
755 tests passed。Vitest 完整运行 357 files / 9,965 tests 通过（约 353 秒），frontend-smoke 29 项通过；父 lane `pr-standard` 最终以 `status=0` 结束（约 1,516 秒）。运行中仍会显示 jsdom navigation warning，但不影响退出状态。
