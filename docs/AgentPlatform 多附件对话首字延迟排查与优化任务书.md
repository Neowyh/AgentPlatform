# AgentPlatform 多附件对话首字延迟排查与优化任务

## 1. 任务目标

针对 AgentPlatform `develop` 分支中的“故障归零智能体”对话场景排查并优化以下问题：

> 用户上传较多文件后点击发送，需要等待约 1～2 分钟才出现模型首字；等待期间模型推理服务 GPU 基本无负载，说明主要延迟发生在 LLM 请求发出之前。

本次工作的核心目标是：

1. 明确“点击发送 → LLM 请求发出 → 首 Token 返回”各阶段实际耗时。
2. 找出模型调用前的主要阻塞点。
3. 对高耗时路径实施定向优化。
4. 不改变现有智能体业务功能、附件语义和故障归零工作流程。
5. 给出优化前后量化数据。

原则：

- 先埋点、后优化。
- 以实际代码和测量结果为依据，不凭猜测重构。
- 优先优化首字关键路径。
- 避免大范围架构改造。
- 每完成一项优化均独立测试，确认收益后再继续。
- 不以降低分析质量、漏处理附件或删除必要业务逻辑换取速度。

---

# 2. 第一阶段：完整梳理请求链路

从前端“点击发送”开始，沿调用链一直追踪到真正向 LLM 服务发送 HTTP 请求的位置。

重点回答：

```text
用户选择附件
↓
附件何时上传？
↓
附件何时解析？
↓
是否转换 Markdown？
↓
什么时候创建/恢复 Sandbox？
↓
附件如何进入 Sandbox？
↓
什么时候创建 Agent Run？
↓
什么时候解析 Agent / Skill / Knowledge / Resource？
↓
什么时候执行 Snapshot Freeze？
↓
什么时候拼接 Prompt / Context？
↓
什么时候真正调用 LLM？
↓
什么时候返回首 Token？
```

优先检查但不限于：

```text
frontend/*
backend/app/gateway/routers/uploads.py
backend/app/gateway/run_preparation.py
backend/app/gateway/canonical_agent_run_preparation.py
```

同时全局搜索：

```text
upload
convert_file_to_markdown
update_file
sandbox
prepare_run
snapshot
freeze
knowledge
attachment
invoke
stream
chat
completion
llm
model
```

输出一份实际调用链，例如：

```text
Frontend send()
  ↓
POST /uploads
  ↓
convert_file_to_markdown()
  ↓
sandbox.update_file()
  ↓
POST /runs
  ↓
prepare_run()
  ↓
freeze_snapshot()
  ↓
invoke_agent()
  ↓
LLM client
```

不要仅根据函数名称推断，必须确认真实调用关系。

---

# 3. 第二阶段：加入端到端耗时埋点

在任何性能修改前增加统一 Trace。

每次对话生成：

```text
trace_id
```

至少记录：

```text
T0  用户发送请求进入后端

T1  附件处理开始
T2  附件处理结束

T3  文件转换开始
T4  文件转换结束

T5  Sandbox 准备开始
T6  Sandbox 准备结束

T7  Sandbox 文件同步开始
T8  Sandbox 文件同步结束

T9  Run Preparation 开始
T10 dependency resolution 完成
T11 snapshot freeze 完成
T12 knowledge/resource 准备完成
T13 Run Preparation 完成

T14 Prompt/Context 构造完成

T15 LLM HTTP 请求发送

T16 LLM 返回第一个流式 Token
```

日志至少输出：

```text
trace_id
附件数量
附件总大小
附件类型
每个附件处理耗时

upload_ms
convert_ms
sandbox_prepare_ms
sandbox_sync_ms
dependency_resolution_ms
snapshot_freeze_ms
knowledge_prepare_ms
prompt_build_ms
pre_llm_total_ms
llm_ttft_ms
end_to_end_ttft_ms
```

关键指标定义：

```text
Pre-LLM Latency
= T15 - T0

Model TTFT
= T16 - T15

End-to-End TTFT
= T16 - T0
```

本问题优先优化：

```text
Pre-LLM Latency
```

---

# 4. 第三阶段：建立基线测试

至少测试以下场景：

| 场景 | 文件数 |
|---|---:|
| A | 0 |
| B | 1 |
| C | 5 |
| D | 10 |
| E | 20 |

优先使用实际故障归零场景常见文件：

```text
PDF
DOCX
XLSX
TXT/MD
```

分别记录：

```text
文件总大小
转换时间
Sandbox 同步时间
Run Preparation 时间
Pre-LLM Latency
LLM TTFT
总首字延迟
```

重点观察：

```text
延迟是否随文件数量近似线性增长
延迟是否随文件大小增长
PDF/DOCX 是否明显慢于 TXT
第二轮对话是否仍重复发生大量准备工作
同一个 Agent 多轮对话是否重复 Freeze Snapshot
```

---

# 5. 第四阶段：重点排查七类问题

## 5.1 附件是否在点击发送后才上传

检查前端：

```text
选择文件时是否立即调用上传接口
```

还是：

```text
选择文件
↓
仅保存在浏览器
↓
点击发送
↓
才开始上传
```

如果属于后者，将大量附件上传完全计入首字延迟。

优先优化为：

```text
选择文件
↓
立即上传
↓
后台解析/转换
↓
显示 Ready
↓
点击发送时直接引用 file_id / artifact_id
```

---

## 5.2 多文件是否串行处理

重点检查：

```python
for file in files:
    await xxx(file)
```

尤其关注：

```text
文件读取
磁盘写入
格式转换
Markdown 生成
Sandbox 上传
```

统计是否形成：

```text
Ttotal ≈ T1 + T2 + T3 + ... + TN
```

如各文件之间不存在依赖，考虑改为有界并发：

```python
Semaphore
+
asyncio.gather()
```

建议：

```text
普通 I/O：4～8 并发
CPU/文档解析：2～4 并发
```

禁止无上限并发。

---

## 5.3 是否存在同步阻塞 I/O

重点搜索：

```python
read_bytes()
write_bytes()
open(...)
shutil.*
subprocess.*
```

是否直接运行在 async 请求路径中。

如存在明显的大文件同步 I/O：

优先考虑：

```text
aiofiles
asyncio.to_thread()
线程池
进程池
```

文档解析如果是 CPU 密集型，不要简单放大量 asyncio task，应考虑受控线程池/进程池。

---

## 5.4 Sandbox 是否重复复制文件

检查附件链路是否类似：

```text
用户文件
↓
Gateway 本地磁盘
↓
读取
↓
复制至 Sandbox

转换后的 Markdown
↓
Gateway 本地磁盘
↓
再次读取
↓
再次复制至 Sandbox
```

重点回答：

```text
原始文件是否必须在首字前进入 Sandbox？
Markdown 是否已经足够供第一轮 Agent 分析？
Sandbox 与 Gateway 是否可以使用共享挂载？
能否通过路径/URI/reference 引用，而不是重新复制？
```

优化优先级：

```text
共享挂载 / reference
>
减少重复复制
>
有界并发复制
>
当前逐文件串行复制
```

如原始文件仅在后续工具调用中才需要，可考虑：

```text
Markdown / metadata 首先 Ready
原始文件按需懒加载
```

不得删除后续确实需要访问原文件的能力。

---

## 5.5 Run Preparation / Snapshot Freeze 是否重复执行

重点分析：

```text
prepare_run
dependency resolution
snapshot freeze
Agent version
Skill version
Knowledge version
Resource version
Tool configuration
```

测试：

```text
同一 Agent
同一会话
第二轮、第三轮对话
```

是否仍然重复执行：

```text
完整 dependency resolve
完整 KB 查询
完整 snapshot freeze
完整 runtime skill 构建
```

如果输入版本没有变化，可考虑缓存。

建议 Cache Key：

```text
agent_version
+
skill_versions
+
knowledge_revision
+
resource_revision
+
tool_config_revision
```

例如：

```text
snapshot_cache[
  hash(agent_version,
       skills,
       knowledge,
       resources,
       tools)
]
```

要求：

```text
版本发生改变 → 必须失效
未改变 → 允许复用
```

不要通过取消 Snapshot 一致性机制来优化。

---

## 5.6 Knowledge Base / DB 查询是否存在 N+1

重点检查 Run Preparation 中：

```text
Agent → Skill
Agent → Knowledge Base
Knowledge Base → Documents
Resource → Version
```

是否出现：

```python
for item in items:
    await db.query(...)
```

检查 SQL 日志或 ORM 调用次数。

如存在：

```text
N 个资源
→ N 次数据库查询
```

优先改为：

```text
batch query
IN (...)
join/selectinload
并行独立查询
```

同时检查：

```text
数据库事务是否持续过长
commit 是否阻塞
是否存在锁等待
```

---

## 5.7 是否把大量附件全文直接拼入 Prompt

检查 LLM 请求发送前：

```text
prompt/context build
```

是否将所有附件完整内容一次性展开。

统计：

```text
Prompt token 数
附件解析文本长度
构建 Prompt 耗时
序列化耗时
HTTP payload 大小
```

如果故障归零智能体拥有文件读取/检索能力，优先考虑：

```text
附件 Manifest
+
摘要/索引
+
按需读取
```

而不是：

```text
所有附件全文
↓
一次性放进上下文
```

但不得擅自改变当前智能体分析语义，应确认现有工具链能够支持按需读取后再调整。

---

# 6. 第五阶段：按照收益优先级实施优化

建议按以下顺序进行，每一步独立 Benchmark。

### P0：可观测性

必须首先完成：

```text
端到端 Trace
阶段耗时日志
单文件耗时日志
```

---

### P1：附件预处理前移

如果附件当前在点击发送后才上传/转换：

改为：

```text
选择附件
→ 上传
→ 转换
→ Ready

点击发送
→ 直接使用已准备的附件
```

这是最高优先级优化。

---

### P2：多文件有界并发

将彼此独立的：

```text
上传
读取
转换
Sandbox 同步
```

从不必要的串行改为有界并发。

要求：

```text
限制并发数量
异常隔离
单文件失败不能导致状态丢失
保持原有结果顺序或正确映射
```

---

### P3：减少 Sandbox 重复搬运

优先尝试：

```text
共享挂载
reference/path
只传首轮必要产物
原始文件 lazy load
```

避免：

```text
raw 文件复制一次
Markdown 又复制一次
```

全部阻塞在首字之前。

---

### P4：优化 Snapshot / Dependency Preparation

对于版本没有变化的资源：

```text
缓存 dependency closure
缓存 snapshot
缓存 runtime metadata
```

必须有正确的失效机制。

---

### P5：优化数据库访问

处理：

```text
N+1
重复查询
串行独立查询
不必要事务
```

---

### P6：渐进式附件披露

如果当前架构允许：

```text
大量附件
↓
Manifest / metadata / index
↓
Agent 首次推理
↓
按需调用文件工具
↓
读取真正相关内容
```

作为后续结构性优化。

---

# 7. 明确禁止的“伪优化”

除非测量证明相关，否则不要优先修改：

```text
LLM quantization
GPU 参数
KV Cache
模型 batch size
模型上下文长度
temperature
生成参数
```

因为当前现象为：

```text
等待期间 GPU 未开始推理
```

所以首先解决模型调用之前的问题。

也禁止：

```text
直接跳过附件解析
直接删除 Snapshot Freeze
跳过知识库初始化
少读取文件以假装变快
修改业务结果
大规模重构整个 AgentPlatform
```

---

# 8. 验收标准

优化后必须输出优化前后对比表：

| 指标 | 优化前 | 优化后 | 改善 |
|---|---:|---:|---:|
| 1 文件 Pre-LLM | | | |
| 5 文件 Pre-LLM | | | |
| 10 文件 Pre-LLM | | | |
| 20 文件 Pre-LLM | | | |
| Snapshot Freeze | | | |
| Sandbox Sync | | | |
| LLM TTFT | | | |
| End-to-End TTFT | | | |

重点目标：

```text
1. 模型调用前耗时有明确阶段归因。
2. 多附件耗时不再因不必要串行处理近似线性恶化。
3. 同一 Agent 多轮对话不重复执行不必要的重准备。
4. 附件处理尽量移出“点击发送 → 首 Token”的关键路径。
5. 所有原有功能、附件可访问性、Agent 行为保持正常。
```

不要人为承诺固定毫秒指标，应根据当前基线评估实际收益。

---

# 9. Codex 最终交付内容

完成后输出：

## A. 根因分析

按实际耗时从高到低列出：

```text
根因
代码位置
触发条件
实际耗时
为什么慢
```

---

## B. 修改清单

每项说明：

```text
修改文件
修改函数
原逻辑
新逻辑
优化原因
可能风险
```

---

## C. 性能数据

提供：

```text
优化前
优化后
附件数量
文件大小
各阶段耗时
总首字时间
```

---

## D. 未修改项

列出发现但本轮没有处理的问题及原因，例如：

```text
收益较低
风险较高
需要架构级改造
需要额外基础设施
```

---

# 10. 执行策略

按照以下循环工作，不要一次性进行大量修改：

```text
建立基线
↓
加入 Trace
↓
找到最大耗时阶段
↓
修改一个主要瓶颈
↓
测试
↓
确认收益和正确性
↓
处理下一个瓶颈
```

最终目标不是“代码看起来更异步”，而是：

> 用实际 Trace 数据证明，从用户点击发送到 LLM 真正收到请求之间的等待时间明显下降，并保持故障归零智能体原有功能和分析质量不变。