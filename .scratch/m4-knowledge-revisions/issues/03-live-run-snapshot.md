# 03: LIVE 依赖在 Run 启动时冻结

**What to build:** Agent／Workflow 的 LIVE 知识依赖在新 Run 启动时解析为当时的 Published Revision；用户可以查看实际使用版本，同一 Run 后续检索持续使用该版本。

**Blocked by:** 02: 发布不可变 Knowledge Revision.

**Status:** ready-for-agent

- [ ] 在 Run 入队或发生执行副作用前，冻结 KB UUID、Resource Version、Knowledge Revision、manifest hash、provider binding 和检索／embedding profile 的实际值或可解析不可变引用。
- [ ] Agent 与 Workflow 均消费运行快照；worker 重载、恢复及后续检索不重新读取 mutable latest 或草稿 binding。
- [ ] Run A 启于 Rev1；发布 Rev2 后 A 仍检索 Rev1，新 Run B 使用 Rev2。profile 后续变化同样不影响 A。
- [ ] 保留 Effective Knowledge Scope、调用者授权、Workflow 约束和 Sub-Agent 不扩权；没有可用 Published Revision 时明确拒绝，不退回草稿检索。
- [ ] 用户可经已有运行详情能力查看 KB 与实际 Revision 信息，内部 provider 标识仍只保留在后端；不建设 M5 完整证据面板。
- [ ] 快照迁移遵循 forward-only 原则并保留既有 Run 记录；没有历史知识快照的旧 Run 不被伪装为可复现，也不为其猜测当前版本。
- [ ] API／运行行为测试覆盖版本切换、并发启动、重载恢复、冻结配置与委派限制，验证实际检索绑定而不只检查字段存在。
