# 02: 文档集身份与资料缺口校验

**What to build:** 使用者提交混合型号、混合封装或不完整的 Chip software source set 时，知识包清楚说明接受与拒绝的资料、覆盖范围及资料缺口，绝不将不一致内容补猜为目标芯片事实。

**Blocked by:** 01: 核心知识包提取.

**Status:** ready-for-agent

- [ ] 资料集验证目标型号、封装和原厂资料类别，并在不一致时阻止错误合并。
- [ ] 缺少 datasheet、Reference/Programming Manual 或适用 errata 时，简报列出可用范围和资料缺口。
- [ ] 脱敏样本覆盖完整资料集、缺 Reference Manual 和多封装混入，断言外部报告而非内部解析细节。
