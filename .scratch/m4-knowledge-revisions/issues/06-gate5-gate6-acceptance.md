# 06: Gate 5／6 真实版本冻结验收

**What to build:** 用隔离 RAGFlow、真实平台运行和版本操作证明旧 Run 不漂移、新 Run 正确选版、PINNED 不变，以及失败和漂移可被用户识别，形成可复核的 M4 验收记录。

**Blocked by:** 04: PINNED 依赖选择与固定版本运行；05: Published Revision 对账与漂移可见性.

**Status:** partial（真实 LLM 运行与浏览器走查未执行，见 docs/knowledge/M4_GATE_ACCEPTANCE.md §4-5）

- [x] 在同一候选版本验证 Rev1 发布→Run A 检索→修改草稿并发布 Rev2→A 仍检索 Rev1→新 Run B 检索 Rev2；证明实际检索数据来源（平台冻结层 + 真实 RAGFlow retrieve；Agent 与 Workflow 的真实 LLM 运行未执行，见验收记录 §4）。
- [x] 新 PINNED Run 仍使用指定 Rev1；profile 变化、worker 重载／恢复和委派不能改变既有快照或扩大权限。
- [x] 草稿修改／删除不破坏旧候选、Published Revision 与旧 Run；发布失败不会切换版本，恢复后可正确发布。
- [ ] 浏览器完成候选查看、发布、版本选择和实际 Run 版本查看（未执行：无模型凭据，交互已由组件单测覆盖）；管理员能观察注入的 provider 漂移，孤立资产不被自动删除（已由真实对账验收覆盖）。
- [x] fresh/existing 隔离数据库迁移保留资源、版本和快照记录；适用数据库后端的通过、失败和跳过分别记录。
- [x] 完成后端标准 lane、适用前端 lane 和 `pr-standard`，按仓库要求记录各子 lane 摘要及父级 TEST_LANE_DURATION；视觉／可访问性按适用 lane 验证，不默认执行 release 级 core-full。
- [x] 验收记录包含候选提交、命令、时间、耗时、退出码与实际结果；真实 provider、真实模型、替身与未执行项分开，模型最终答案正确率不替代版本冻结证据。
- [x] 完成 Patch Ledger 巡检与适用 GitNexus 检查；只清理本轮创建的隔离验收资产，保留正式验收摘要与历史证据。
