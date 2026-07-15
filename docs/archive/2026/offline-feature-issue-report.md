# offline_feature 分支问题检查报告

> status: archived; current product-line authority: `docs/offline-product-line-governance-plan.md`

**检查日期**: 2026-06-23
**分支**: offline_feature (vs main)
**检查范围**: 代码审查、单元测试、编译检查、安全审查

## 概述

- 总提交数：15
- 文件变更：1011 files changed, 54440 insertions, 6388 deletions
- 前端测试：7061/7061 通过
- 后端测试：58 个测试因 admin.py bug 全部失败（已修复）
- 发现问题总数：35+

## 问题汇总

### 已修复问题

| ID | 严重程度 | 文件 | 问题 | 修复状态 |
|----|----------|------|------|----------|
| FIX-1 | CRITICAL | admin.py:67-68 | Field() 应为 Query()，导致 58 个后端测试全部失败 | ✅ 已修复 |

### CRITICAL 问题

| ID | 文件 | 问题 | 描述 |
|----|------|------|------|
| C-1 | frontend/src/app/workspace/admin/ | 无客户端角色检查 | 所有 admin 页面缺少客户端 RBAC 检查，任何认证用户可访问管理功能 |

### HIGH 问题

| ID | 文件 | 问题 | 描述 |
|----|------|------|------|
| H-1 | admin.py:119-163 | TOCTOU 竞态 | last-super_admin 降级检查存在竞态，可能导致零 super_admin |
| H-2 | executor.py:55-62 | 无限递归 | and/or 链式表达式可导致 RecursionError |
| H-3 | store.py:130-156 | 并发写入无保护 | save_run_state 无乐观锁，last-write-wins |
| H-4 | workflows/api.ts | extractError 使用不一致 | await extractError() 导致死代码 |
| H-5 | admin/api.ts:127-132 | AdminStats 位置错误 | 类型定义应在 types.ts |

### MEDIUM 问题

| ID | 文件 | 问题 | 描述 |
|----|------|------|------|
| M-1 | authz.py:250-254 | 测试绕过属性检查 | 非 Request 对象的 _ideer_test_bypass_auth 可绕过认证 |
| M-2 | authz.py:203 | 权限映射过宽 | 非 viewer 用户获得所有权限 |
| M-3 | admin.py:214-217 | 缺少 @require_role | list_departments 端点无角色限制 |
| M-4 | executor.py:65-76 | 运算符 in 匹配字符串 | 操作符检查可能匹配字符串值 |
| M-5 | executor.py:120-131 | goto 无环检测 | 可能导致无限循环 |
| M-6 | template.py:96-103 | getattr 允许属性遍历 | 非 dunder 属性可被访问 |
| M-7 | human_step.py:47-74 | 轮询竞态 | 超时与 API 提交存在竞态 |
| M-8 | users/page.tsx | 无自我禁用保护 | 用户可禁用自己 |
| M-9 | users/page.tsx | 无自我降级保护 | super_admin 可降级自己 |
| M-10 | workflows/validate.ts | YAML 验证过于简单 | 基于字符串包含而非解析 |
| M-11 | workflows/api.ts | 无类型请求负载 | Record<string, unknown> 无编译时检查 |
| M-12 | tools/page.tsx | 测试输入无大小限制 | 可发送超大 JSON |
| M-13 | workflows/types.ts | status 类型未定义 | 应使用联合类型 |
| M-14 | threads.py | 缺少 @require_permission | create_thread 和 search_threads 无权限装饰器 |
| M-15 | auth.py | 速率限制不跨 worker | 进程内字典不共享 |

### LOW 问题

| ID | 文件 | 问题 | 描述 |
|----|------|------|------|
| L-1 | authz.py:596-653 | SQLite 竞态 | 初始 admin 引导存在竞态 |
| L-2 | executor.py:194 | jitter 范围窄 | 0-1s vs 5s backoff |
| L-3 | store.py:272-286 | bytes 序列化 | str(obj) 可能不是预期格式 |
| L-4 | store.py:352-359 | 单例非线程安全 | 当前架构安全 |
| L-5 | template.py:122 | Exception 捕获过宽 | 应捕获具体异常 |
| L-6 | human_step.py:35 | 硬编码超时 | 1 小时默认超时 |
| L-7 | registry.py:34 | 静默覆盖工具 | 同名工具注册被覆盖 |
| L-8 | users/page.tsx | 无加载状态 | 角色切换无 loading |
| L-9 | admin/types.ts | 可选字段不一致 | department_name vs department_id |
| L-10 | workflows/hooks.ts | 非空断言 | name! 可能为 undefined |
| L-11 | admin/api.ts | AdminStats 组织 | 类型定义位置 |
| L-12 | data_analyzer/tools.py | 路径泄露 | 错误响应包含用户路径 |
| L-13 | doc_reader vs data_analyzer | 路径验证不一致 | 不同的解析方法 |
| L-14 | authz.py | 测试绕过机制 | 生产代码中的测试便利 |
| L-15 | internal_auth.py:45 | token 截断 | 43 字符 vs 64 字符 |
| L-16 | auth.py:347 | _client_ip 未定义 | 运行时 NameError |
| L-17 | auth_middleware.py:20 | 未使用导入 | 2 个未使用的导入 |

## 修复优先级建议

### 立即修复（阻塞测试/运行时错误）
1. FIX-1 ✅ admin.py Field→Query（已完成）
2. L-16 auth.py _client_ip 未定义
3. L-17 auth_middleware.py 未使用导入

### 高优先级（安全/数据完整性）
4. C-1 admin 页面客户端角色检查
5. H-1 admin.py TOCTOU 竞态
6. H-2 executor.py 无限递归
7. H-3 store.py 并发写入
8. M-1 authz.py 测试绕过

### 中优先级（功能/安全改进）
9. H-4, H-5 前端 API 问题
10. M-2 到 M-15 各种中等问题

### 低优先级（代码质量）
11. L-1 到 L-15 各种低等问题
