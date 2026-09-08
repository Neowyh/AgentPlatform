# 上游前端与 develop 前端的合并原则

> 制定背景：deerflow-main 0f7d8709 合并收尾中发现了三类「路由在但入口不可见 /
> 前端调用但后端未挂载」的静默丢失（侧边栏 capabilities+library、4 组孤调用
> API、品牌残留）。本文档将这些教训固化为可执行的合并原则与自动化门禁。
> 生成：2026-09-08。配套脚本：`scripts/check-frontend-entry-parity.sh`。

## 一、合并原则（六条）

### P1 超集原则
合并结果 = develop 原有入口 ∪ 上游新增入口 − 双方明确同意删除的入口。
任何一侧的入口都不允许在无记录的情况下消失。删除必须显式登记
（`BASELINE_NAV_REMOVALS` 白名单或采用矩阵的「有意排除」行）。

### P2 入口三件套原则
一个「入口」= 路由文件 + 可见导航链接 + i18n 文案，三者缺一即视为丢失。
只验证路由文件是不够的（capabilities/library 教训）；只验证链接也
不够（scheduled-tasks 教训：链接在、后端路由未挂载）。

### P3 API 契约闭环原则
前端发起的每一个 `/api` 调用，必须能解析到已挂载的后端路由。
上游带入的前端页面所依赖的上游 router，随前端一并挂载；除外的 router
（如 `/api/agents`——非 canonical 资源源的有意排除）必须登记在采用矩阵。

### P4 修复放置原则
- iDeer 导航项与上游导航项并存时，结果取**并集**，iDeer 原排序优先、
  上游新增项追加其后；
- 上游页面替换 iDeer 同功能页面时，必须保留 iDeer 原入口路径（redirect）；
- 重型页面进入共享 bundle 必须走 `dynamic()`，由 bundle 边界守卫测试钉住。

### P5 品牌通过原则
上游 UI 文案必须经过 i18n locale 文件的单点映射进入产品，禁止把
上游品牌字符串（DeerFlow 等）直接留在组件里；每次合并后对
`frontend/src` 做上游品牌字符串扫描。

### P6 测试钉住原则
每一类入口必须有自动化守卫，合并后自动报警而不是人工核对：
- 侧边栏导航项集合 → `workspace-nav-chat-list.test.tsx`（六项形态）；
- 入口对齐四层检查 → `scripts/check-frontend-entry-parity.sh`（本文档脚本）；
- bundle 边界 → `lazy-panels.test.ts`；
- API 挂载 → 各 router 的生命周期测试（如 scheduled-task lifecycle）。

## 二、合并时如何执行（操作序列）

```bash
# 合并冲突解决完成后、提交前运行：
bash scripts/check-frontend-entry-parity.sh <基线commit> HEAD
# BASELINE_NAV_REMOVALS="/api/agents /workspace/xxx" 处理有意删除
# 四层全 OK → 允许提交；任一 LOST/ORPHAN → 先修复或显式登记
```

四层检查内容：
| 层 | 检查 | 教训来源 |
|---|---|---|
| 1 路由文件 | 基线 page 路由 ⊆ HEAD | — |
| 2 可见导航 | 基线侧边栏链接 ⊆ HEAD（+白名单） | capabilities/library 丢失 |
| 3 i18n 键 | sidebar 键无丢失 | 品牌残留 |
| 4 API 孤引用 | 前端调用 ⊆ create_app() 实际路由 | scheduled-tasks 404 |

## 三、本轮 35 项页面入口的核对结果

合并前 35 个页面路由（+9 layout）全部保留；侧边栏 6 项（4 基线含修复 +
2 上游新增）；底部 admin 菜单 7 项逐一相同；设置分区 5 → 9（新增
channels/integrations/skills/tools，无丢失）。逐项表格见会话记录与
`BASELINE_REPORT.md` 2026-09-08 增补。

## 四、局限与后续

- 静态检查不覆盖「页面渲染是否报错」——由 mock-e2e 套件覆盖（356 文件）；
- 动态拼接的 API 路径（模板字符串）按静态前缀近似匹配，特殊路径需人工复核；
- 建议将本脚本纳入 `pr-standard` lane 的前端阶段（工作待排）。
