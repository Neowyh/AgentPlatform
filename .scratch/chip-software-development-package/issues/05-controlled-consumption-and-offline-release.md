# 05: 受控下游消费与离线发布

**What to build:** 已发布的专业 Skill/Expert 在 iDeer 的资源授权、运行快照和离线资产模型内可发现并运行；后续自动化只能消费知识包中 `confirmed` 的结构化条目。

**Blocked by:** 01: 核心知识包提取; 03: 证据状态与人工复核门禁; 04: 嵌入式开发关键知识覆盖.

**Status:** ready-for-agent

- [ ] 专业 Skill/Expert 遵守当前调用者授权、工具组限制、资源版本和运行快照语义。
- [ ] 下游读取入口拒绝 `review_required` 和资料缺口条目，只公开 `confirmed` 条目。
- [ ] 内网打包和新装环境可获得所需的 Skill 资产，不依赖运行时外网下载。
