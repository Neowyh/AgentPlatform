# 归零智能体工具链切片 — Spec

- date: 2026-09-30
- status: ready-for-agent
- base: develop @ 93131a40d（统一内核合并后）
- 前序：docs/plans/2026-09-29-fault-zeroing-unified-kernel-spec.md（已合并交付）

## Problem Statement

统一内核合并后，归零智能体的代码证据分析仍存在「声明与实现不符」与能力空白：静态分析工具被提示词引用但不存在、GBK 编码支持是空头支票、代码证据上下文中间件默认不生效、扫描器二进制未部署、固件/编译产物类证据被拒收且无读法；同时 workflow 节点提示词内联重复规则、前端专家会话技能快捷入口被一刀切禁用。

## Solution

以新建 `code` 工具组为载体：接线 `analyze_code_evidence`（修复扫描库四缺陷、按语言分发 C/C++ 与 Python 扫描）、注册 `code_interpreter` 与 `data_analyzer`、部署扫描器二进制；实现 GB18030 编码嗅探兑现提示词承诺；代码证据管道改二进制白名单并配套 `read_binary_hex` 查看器；Scanner Status 进入 Result Contract 披露门；收敛节点提示词重复规则并恢复前端技能入口。

## 决策记录（grill 会话 2026-09-29/30）

1. 基线：先合并统一内核分支，从合并后 develop 开本切片。
2. 范围：全部剩余问题一个批次。
3. Scanner Status：入 Result Contract——code 侧证据存在时必须有 analysis/scanner_status.json，允许显式披露 `scanners_unavailable`，不允许缺失；纯文档 Run 不要求。
4. `analyze_code_evidence`：新建 `code` 工具组承载。
5. code_interpreter：现在启用（code 组，沿用模块既有三重上限：300s/20k 字符/1MB），深度加固单独立项。
6. Python 静态分析：并入 `analyze_code_evidence` 按语言分发（C/C++→clang-tidy+cppcheck；Python→ruff+bandit 只读），Finding Confidence 语义同效。
7. OCR/PDF：维持现状——PDF 照常接收，扫描件转换失败走「待验证」披露，OCR 需求关闭。
8. 二进制证据：白名单放行（单文件 ≤10MB）+ 新增只读 `read_binary_hex`（限代码包内路径，hex+可打印字符串视图）。

## User Stories

1. As a 归零 Analyst, I want 对代码证据包调用静态扫描并获得结构化告警, so that 底事件判定有机器扫描证据而非纯人工阅读。
2. As a 归零 Analyst, I want 扫描器不可用时得到如实的状态记录, so that 「没扫」不会被伪装成「扫过无发现」。
3. As a 归零 Analyst, I want AI 能正确读取 GBK 编码的源码与日志, so that 中文注释与日志证据不再因编码报错丢失。
4. As a 归零 Analyst, I want 固件/编译产物随代码包进入系统并可用十六进制视图检查, so that 固件版本类排查点可落地。
5. As a 归零 Analyst, I want AI 能运行验证脚本, so that 验证计划从纸面变成可执行。
6. As a 质量工程师, I want 未通过扫描披露门的 Run 不被标记完成, so that 完成判定持续可信。
7. As a 平台开发者, I want 节点提示词引用统一规则源, so that 枚举漂移不再有重发条件。
8. As a 专业用户, I want 在专家会话中直接斜杠调用技能, so that 能力触达不再被入口禁用。

## Implementation Decisions

- 工具注册遵循工单 04 建立的 config.example.yaml 声明先例；新 `code` 组。
- 扫描库修复：cppcheck stdout(XML)/stderr(进度) 分离解析；每个扫描器记录 scanner_status（available/version/exit_code/timed_out）；超时按源文件数分档（≤200 文件 120s，否则 600s）；捕获 OSError；`compilation_configuration_verified=false` 时跳过 clang-tidy 只跑 cppcheck 并记录跳过原因。
- 产物落 `<package>/analysis/`（inventory.json + findings.json + scanner_status.json）；工具内部自带包根约束，不经 FilesystemScopeMiddleware。
- read_file/grep 编码嗅探顺序 UTF-8 → UTF-8 BOM → GB18030；GB 命中输出加 `[encoding: GB18030]` 前缀。
- code_evidence 管道二进制后缀改白名单放行（单文件 ≤10MB，manifest 记录），`read_binary_hex` 大小与路径双守卫。
- 契约校验（canonical 与打包副本同步）增加 scanner_status 披露门；evidence_collection 节点消费 findings+status。
- backend/Dockerfile 安装并 pin clang-tidy、cppcheck。
- CONTEXT.md 增补「Scanner Status」词条。

## Testing Decisions

- 接缝：工具边界（直调）、code_evidence 管道单元、read_file/grep 编码 fixture（GBK/GB18030/BOM/ASCII/非法字节）、契约单元（披露门三态）、打包副本 parity、worker 运行时端到端（scanner_status 驱动完成判定）。
- 先例：test_code_analysis.py、test_code_evidence、test_zeroing_run_tools、test_fault_zeroing_packaged_validator、worker runtime 集成。
- 验证门：每票聚焦 + lint；票末全量后端；收口 pr-standard。

## Out of Scope

OCR/tesseract（决策 7 关闭）；code_interpreter 深度安全加固（单独立项）；视觉模型；通用「聊天→任意工作流」互操作；本地 git-ignored config.yaml 的 custom_agents 清理（运维动作，列入收口清单）。

## Further Notes

已安装环境需重新发布归零资源获得新定义；Dockerfile 变更需重建镜像后扫描器才实际可用（未重建前 scanner_status 应如实披露 scanners_unavailable——这正是披露门的设计场景）。
