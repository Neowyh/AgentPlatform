# iDeer 小白用户上手体验优化实施方案

- 日期：2026-08-26
- 状态：已评审（grill-me 访谈收敛），待排期
- 目标用户：首次登录平台的普通使用者（只想用 agent 干活，不创建 agent、不用管理后台）

## 1. 背景与第一性原理

小白用户的完整旅程：**登录 → 面对空输入框 → 不知道能干什么/该找谁 → 发出消息 → 被过程信息淹没 → 得到结果但不知下一步**。

由此识别出三道墙：

| # | 墙 | 本质 |
|---|----|------|
| 1 | 不知道能用它干什么 | 空白输入框 = 零信息；新手需要的不是"全部信息"，而是"下一步该做什么" |
| 2 | 执行过程看不懂 | 用户在执行中只关心一个问题："它现在在干嘛、还要多久" |
| 3 | 术语门槛 | thread/run/workflow 是给系统用的词，不是给用户看的词 |

设计总纲（访谈确认）：

- 首页信息密度高于现状：核心能力一级入口直接可见，高频功能最少步骤直达。
- "展示全面" ≠ 同屏堆砌，而是"需要时能找到"；细节按需展开。
- 三期一次规划、分批实施，每期独立可上线。
- 不做专门埋点验证，靠团队体感迭代。

---

## 2. 第一期：欢迎态升级为工作台首页

### 2.1 方案要点

- **落点**：现有 `/workspace/chats` 欢迎态（登录后默认落地页，见
  `frontend/src/app/workspace/page.tsx` 的 redirect）。不新增路由，用户心智零迁移。
- **三块内容**：
  1. 场景化推荐提问卡片
  2. 智能体精选目录
  3. 最近会话
- **推荐卡片来源**：由 agent 元数据自动生成（`useAgents()` 取可见 agent 的
  `name` + `description`；示例 prompt v1 用通用模板从 description 生成，
  不新增后端接口。管理员配置置顶能力留到后续迭代）。
- **卡片交互**：预填不发送——点击后跳转到对应 agent 的聊天页，示例 prompt
  自动填入输入框、光标就位，用户可直接修改后发送。

### 2.2 技术要点

- 预填机制复用两条既有通路：
  - `frontend/src/components/workspace/chats/use-chat-mode.ts` 已支持根据 URL
    参数设置输入框初始值；
  - `frontend/src/components/workspace/input-box.tsx` 的
    `handleSuggestionClick`（L907）已有 setInput + 光标选中逻辑。
  - 卡片跳转建议携带 `?agent=<slug>&prompt=<encoded>` 类参数进入
    `/workspace/agents/[agent_name]/chats/new` 欢迎态。
- `Agent` 类型（`frontend/src/core/agents/types.ts`）目前无示例问题字段，
  v1 不改类型；若后续需要精细化示例，再扩展可选字段 `example_prompts?`。

### 2.3 任务拆解

| 任务 | 说明 |
|------|------|
| T1.1 新建工作台组件目录 | `frontend/src/components/workspace/workbench/`，含三个子组件与 index |
| T1.2 场景化推荐提问卡片组件 | 数据源 `useAgents()`；每 agent 一卡：名称、一句描述、1 条示例 prompt |
| T1.3 智能体精选目录组件 | 复用 `AgentCard` 展示样式，横向网格 + "查看全部"链接到 `/workspace/agents` |
| T1.4 最近会话卡片化变体 | 从 `recent-chat-list.tsx` 抽出列表项渲染逻辑，提供非 Sidebar 的卡片容器形态 |
| T1.5 欢迎态布局接入 | 在 `[thread_id]/page.tsx` 的 `isWelcomeMode` 分支下，于 InputBox 下方渲染工作台三块；提交后随欢迎态一起隐藏 |
| T1.6 跨页预填 prompt | 扩展 `use-chat-mode.ts` 支持 prompt 参数；落地到输入框初始值并聚焦 |
| T1.7 i18n 文案 | 新增工作台相关 key（区块标题、"查看全部"、空状态等） |
| T1.8 单元测试 | 组件测试镜像放 `frontend/tests/unit/` 对应路径 |

### 2.4 涉及文件清单

**修改：**

- `frontend/src/app/workspace/chats/[thread_id]/page.tsx` — welcome 态布局接入工作台
- `frontend/src/components/workspace/welcome.tsx` — 保留问候语，作为工作台上沿
- `frontend/src/components/workspace/chats/use-chat-mode.ts` — 支持 prompt 预填参数
- `frontend/src/core/i18n/locales/zh-CN.ts`、`en-US.ts`、`types.ts` — 新增文案 key

**新建：**

- `frontend/src/components/workspace/workbench/index.ts`
- `frontend/src/components/workspace/workbench/scene-suggestion-cards.tsx`
- `frontend/src/components/workspace/workbench/agent-showcase.tsx`
- `frontend/src/components/workspace/workbench/recent-chats-card.tsx`

**复用（不改或微调）：**

- `frontend/src/core/agents/hooks.ts` / `api.ts` / `types.ts` — `useAgents()`
- `frontend/src/components/workspace/recent-chat-list.tsx` — 抽取列表项逻辑
- `frontend/src/components/workspace/agents/agent-card.tsx` — 目录卡片样式参考
- `frontend/src/components/workspace/input-box.tsx` — 预填落点（textarea focus）

**测试：**

- `frontend/tests/unit/components/workspace/workbench/*.test.tsx`（新建）
- 回归：`pnpm test`、`pnpm check`；E2E 视情况补一条欢迎态冒烟用例（`pnpm test:e2e`）

---

## 3. 第二期：执行过程可读性

### 3.1 方案要点

- **策略**：人话进度条 + 默认折叠。
  - 执行中仅显示一行人话进度："正在制定计划… → 正在搜索资料 (3/5) → 正在撰写报告…"
  - 中间产物（计划详情、研究步骤、工具调用）全部折叠
  - 完成后默认只展示最终报告，细节逐层按需展开
- **实现范围**：纯前端。将现有消息流中的节点类型（plan/research/report 等）
  映射为人话阶段文案，不需要后端改动。

### 3.2 任务拆解

| 任务 | 说明 |
|------|------|
| T2.1 阶段映射层 | 在 `core/messages/` 增加节点→阶段枚举→人话文案的映射工具函数 |
| T2.2 进度条组件 | 新建 `process-progress.tsx`：单行阶段进度 + 当前步骤计数 + 可展开入口 |
| T2.3 默认折叠改造 | `message-list-item.tsx` / `message-group.tsx`：中间产物默认收起，完成后仅最终报告展开 |
| T2.4 展开交互 | 各折叠段支持逐层展开查看原始细节（计划、子任务、工具调用） |
| T2.5 i18n 文案 | 阶段人话文案（中英） |
| T2.6 测试 | 映射函数单测 + 折叠行为组件测试 |

### 3.3 涉及文件清单

**修改：**

- `frontend/src/components/workspace/messages/message-list.tsx`
- `frontend/src/components/workspace/messages/message-list-item.tsx`
- `frontend/src/components/workspace/messages/message-group.tsx`
- `frontend/src/components/workspace/messages/subtask-card.tsx`
- `frontend/src/core/messages/`（消息处理逻辑）
- `frontend/src/core/i18n/locales/*`

**新建：**

- `frontend/src/components/workspace/messages/process-progress.tsx`
- `frontend/src/core/messages/stage-mapping.ts`（阶段映射）

**测试：**

- `frontend/tests/unit/core/messages/stage-mapping.test.ts`（新建）
- `frontend/tests/unit/components/workspace/messages/*.test.tsx`

---

## 4. 第三期：术语人话化

### 4.1 方案要点

- **范围**：仅 UI 文案层（i18n），不动后端模型、API、数据结构。
- **原则**：用户语言只有日常词——thread→对话、run→执行、workflow→工作流等；
  首次出现的新概念附一句副标题解释。
- **不做**：引导 tour（多数用户会跳过，维护成本高）。
- **风险控制**：老用户心智迁移成本可控；重命名只影响显示层，搜索/路由标识不变。

### 4.2 任务拆解

| 任务 | 说明 |
|------|------|
| T3.1 术语对照表定稿 | 产出中英术语映射表（评审后生效），覆盖 sidebar、面包屑、设置、admin 全部用户可见文案 |
| T3.2 i18n 词条替换 | 按 `types.ts` 结构批量更新 `zh-CN.ts` / `en-US.ts` |
| T3.3 首现解释 | 高频新概念在首次出现处加副标题或 tooltip 一句话解释 |
| T3.4 全量回归 | 截图走查主要页面，确认无漏改、无布局溢出 |

### 4.3 涉及文件清单

**修改：**

- `frontend/src/core/i18n/locales/zh-CN.ts`
- `frontend/src/core/i18n/locales/en-US.ts`
- `frontend/src/core/i18n/locales/types.ts`（如需新增说明类 key）
- 少量硬编码英文文案的组件（T3.1 排查后在任务中列出）

**产出文档：**

- 术语对照表（本目录追加 `2026-MM-DD-term-glossary.md`）

---

## 5. 实施顺序与验收

```
第一期（能力发现）→ 上线 → 团队体感收集
   └─ 第二期（过程可读性）→ 上线
        └─ 第三期（术语人话化）→ 上线
```

- 每期独立 PR，遵循 Conventional Commit（如 `feat(frontend): workbench home ...`）。
- 每期验收命令：`cd frontend && pnpm test && pnpm check`；涉及交互链路时补跑
  `pnpm test:e2e`。
- 第一期验收标准（体感口径）：新用户登录后无需任何说明，能通过首页卡片在
  两次点击内发出一条针对具体能力的消息。

## 6. 开放项（后续迭代候选）

- 推荐卡片的管理员配置/置顶能力
- Agent 元数据扩展 `example_prompts` 字段（需后端配合）
- 新用户首日激活埋点（若未来需要数据驱动决策再启用）
