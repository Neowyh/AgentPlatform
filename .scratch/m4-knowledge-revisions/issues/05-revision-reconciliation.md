# 05: Published Revision 对账与漂移可见性

**What to build:** 管理员可按需或通过定期检查获知已发布知识与 provider 是否一致，定位缺失、漂移和 orphan，使异常不会被静默当成健康知识版本。

**Blocked by:** 02: 发布不可变 Knowledge Revision.

**Status:** done

- [x] 定期／按需对账检查 Published Dataset 存在性、文档集合与 provider 可核验的内容 hash，结果经授权 API 和管理视图可见。
- [x] 区分 HEALTHY、MISSING_PROVIDER_DATASET、MISSING_DOCUMENT、HASH_MISMATCH 与 ORPHAN_PROVIDER_RESOURCE；provider 暂不可达或无法核验的项目不误报 HEALTHY 或确认缺失。
- [x] 已确认内容漂移的 Revision 明确标记 DRIFTED，并在关联 KB／版本状态呈现；阻止该版本被当作有效的发布或 PINNED 依据。
- [x] 对账不自动修改 provider 内容、删除 orphan、重写 manifest 或替换运行快照；异常处理需要显式维护操作。
- [x] 检查记录保留时间、结论与可追查关联；普通用户响应与指标标签不泄漏内部地址、凭据或 raw provider 标识。
- [x] 聚焦测试以可控 provider 覆盖健康、缺失、篡改、orphan 和连接失败，并覆盖管理员权限及异常视图。

本票无需等待 03／04 的运行能力；遵守总方案串行安排，不据此自动并行实施。
