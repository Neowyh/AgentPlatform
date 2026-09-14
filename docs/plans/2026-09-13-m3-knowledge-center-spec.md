# M3：文档管理与 Knowledge Center

> 日期：2026-09-13
> 类型：功能规格（to-spec）
> 状态：测试边界已由用户确认；已发布至项目本地任务跟踪器，标记 `ready-for-agent`。
> 实施状态：BLOCKED；M3 开工基线当前为 UNVERIFIED。规格就绪不等于准许实施或前置验收通过。

## Problem Statement

用户已经拥有受治理的 KnowledgeBase Resource，Agent 和 Workflow 也能在 Effective Knowledge Scope 内检索。但用户仍不能在平台内完成创建知识库、上传资料、观察解析索引状态、恢复失败和删除草稿文档的完整过程。现有 Library 的知识库与文档列表包含静态示例，不能证明真实知识状态。

依赖维护者直接操作 RAGFlow 会让普通用户接触 dataset、凭据等基础设施细节，也会绕开平台已有的资源授权和审计边界。用户需要知道资料是否可检索、失败后如何继续，以及当前操作是否在自己的权限范围内。

## Solution

在既有工作台 Library 入口下提供 Knowledge Center，以真实的 canonical KnowledgeBase 列表和详情承载文档管理。用户通过平台创建知识库并上传资料，平台负责权限校验、文件安全校验、hash、原始文件保存、provider 上传和解析索引状态同步。用户能够查看进度、读取脱敏失败摘要、重试处理、重建索引和删除草稿文档。

知识进入 READY 后，由已有 `knowledge_search` 在 Effective Knowledge Scope 内检索。管理写操作由 Knowledge Service 承担，Agent Runtime 保持只读。M3 交付可用的草稿知识管理闭环；不可变 Knowledge Revision、完整 Retrieval Receipt 与检索评测分别留给 M4、M5、M6。

## User Stories

1. As an 已登录用户, I want 浏览我有权查看的真实 KnowledgeBase, so that 我能找到可使用的知识。
2. As an 已登录用户, I want 看见明确的加载、空列表和失败状态, so that 我不会把示例数据或服务异常误认为真实知识状态。
3. As an 知识库创建者, I want 输入名称和描述即可创建 KnowledgeBase, so that 我无需理解 RAGFlow dataset 或填写基础设施凭据。
4. As an KnowledgeBase owner, I want 沿用已有可见性申请和审批流程, so that 知识共享符合资源治理规则。
5. As an 已登录用户, I want 查看知识库的 owner、department、visibility、状态和文档数量, so that 我能判断资料的归属与可用性。
6. As an KnowledgeBase owner, I want 在知识库详情上传支持的文件, so that 我能自行维护业务资料。
7. As an 上传者, I want 在提交前了解允许的文件类型与大小限制, so that 我能准备可接受的文件。
8. As an 上传者, I want 非法文件名、路径、类型或超限文件被明确拒绝, so that 无效输入不会造成不安全写入或误导性成功。
9. As an 上传者, I want 分清上传完成与解析索引完成, so that 我知道何时可以实际检索资料。
10. As an 上传者, I want 页面刷新后仍能看到处理状态, so that 长任务不依赖浏览器一直打开。
11. As an KnowledgeBase owner, I want 查看文档名称、大小、来源、状态和更新时间, so that 我能识别并管理每份资料。
12. As an KnowledgeBase owner, I want 维护文档标题和业务 metadata, so that 团队可以理解资料内容与用途。
13. As an 上传者, I want 看到脱敏且可采取行动的失败提示, so that 我能决定重试还是联系维护者。
14. As an KnowledgeBase owner, I want 对失败文档重试处理, so that 暂时的 provider 故障不要求重新创建知识库。
15. As an KnowledgeBase owner, I want 请求重建文档索引并看到实际状态, so that 我能恢复已有资料的检索能力。
16. As an KnowledgeBase owner, I want 重复点击或超时后重试不会留下重复逻辑文档和失控 provider 任务, so that 恢复操作可预测。
17. As an KnowledgeBase owner, I want 删除草稿文档并看到删除结果或清理待完成状态, so that 不需要的资料能够退出后续检索。
18. As an 非 owner 使用者, I want 只看到自己获准的内容与操作, so that 共享使用不会赋予修改权。
19. As an 无权用户, I want 平台拒绝通过 KB 或文档标识猜测进行读取和操作, so that 他人的知识保持隔离。
20. As an Agent 调用者, I want 检索到自己获准知识库中已就绪的资料, so that 回答能够使用本次任务允许的知识。
21. As an 共享 Agent 调用者, I want 检索以我的权限执行, so that 共享 Agent 不会借用 owner 的知识权限。
22. As an Workflow 调用者, I want Agent 步骤和 Sub-Agent 保持原有知识范围限制, so that 委派不会扩大访问范围。
23. As an Agent 调用者, I want 模型只接收预算内的授权检索片段, so that 大量结果不会淹没上下文。
24. As an Agent 调用者, I want 区分无匹配内容、无检索权限和 provider 暂时不可用, so that 我能理解任务为何没有得到知识结果。
25. As an 已登录用户, I want 知识功能关闭或 provider 不可达时看到一致的能力状态, so that 我不会反复触发必然失败的操作。
26. As an 平台管理员, I want 上传、删除、重建索引与拒绝操作留下可关联的审计记录, so that 我能追查问题且不依赖 provider 控制台。
27. As an 平台维护者, I want 原始文件、逻辑文档、内容 hash 和 provider 映射可对应, so that provider 索引不会成为唯一文件归档。
28. As an 平台维护者, I want 通过低基数指标观察摄取失败、检索延迟和零命中, so that 我能发现问题而不把敏感内容写入指标标签。
29. As an 内网部署维护者, I want 文档处理沿用现有内网 provider 配置, so that 本功能不隐含新增公网服务依赖。
30. As an 产品维护者, I want 用真实创建、上传、索引、检索和删除的结果验收 M3, so that UI 出现页面或 mock 测试通过不会被误报为完整交付。

## Implementation Decisions

1. **资源身份与职责。** KnowledgeBase 继续是第四类 Resource，UUID 是企业身份；ResourceService 负责现有 owner、visibility、lifecycle 和调用者授权。Knowledge Service 编排文档管理；Provider 负责解析、索引和检索状态；DeerFlow 负责只读工具执行。企业知识模块与扩展适配层沿用现有分层，不新增第二套资源目录或 RBAC。
2. **创建体验。** 首版仅支持部署配置的 RAGFlow。创建流程由服务端建立或接续受控 provider binding；普通用户不填写 dataset ID、URL 或 API key。资源目录已创建而 provider 初始化失败时保留明确失败／未绑定状态，可恢复，不显示为可上传或可检索成功。
3. **API。** 沿用 `/api/resources` 创建和读取 KnowledgeBase；以 KB UUID 下的 documents 子资源提供列表、详情、上传、metadata 更新、删除、重试和重建索引操作。扩展 `/api/features` 提供知识功能启用与 provider 可用状态。保留已有 knowledge binding 接口的含义；前端不直连 RAGFlow。
4. **文档记录。** 引入 KnowledgeDocument，关联 canonical KB UUID，并保留稳定逻辑文档标识、原始文件名、内容 hash、大小、MIME、原始存储引用、UPLOAD 来源、metadata、provider document 映射、处理状态和时间。provider 映射只留在管理边界内。metadata 不成为新的 ACL 真源。
5. **摄取顺序。** 调用者授权→文件名／类型／大小校验与 hash→原始文件安全存储→文档记录→provider 上传→解析／索引→状态同步→READY。复用平台现有文件安全和存储能力；生命周期独立于 Thread 临时附件，不能因聊天清理而丢失 KB 原始文件。
6. **持久化与恢复。** 上传接受不等于 READY。文档状态由服务器持久化，刷新页面不丢失；平台呈现上传、校验、解析、索引、就绪和失败阶段，provider 无法区分的处理中阶段不伪造进度。处理采用可恢复异步编排，首版以服务器轮询同步 provider 状态；不引入新通用任务平台或同时建设回调路径。
7. **失败处理。** 存储、数据库与 provider 不假设跨系统原子事务。保存足以恢复与清理的状态，重试复用同一逻辑文档和可复用的 provider 映射；重复操作不能创建无界任务。返回稳定错误类别与已有请求关联信息，不外泄内部地址、凭据、堆栈或 raw provider ID。
8. **草稿删除。** M3 只处理草稿文档删除。删除需要管理授权，并处理平台记录、原始文件和 provider 索引的一致性；清理失败保留可恢复状态。删除完成必须证明文档不再参与后续检索，不能仅隐藏列表。历史 Tool Receipt 保留，不承诺删除前知识状态可重放。
9. **阶段边界。** 文档 READY、Resource 内容发布与 Knowledge Revision 发布是不同概念。M3 不创建不可变 Revision 或宣称运行中的知识内容永不漂移；正式版本发布和引用保留策略由 M4 接管。当前 UI 不展示虚构的 Revision、Eval 或完整 Retrieval Receipt。
10. **知识中心。** 复用现有 Library 入口与工作台组件，提供真实 KB 列表、详情、文档操作和状态；入口与按钮遵循已获授权及 feature availability。权限／依赖管理复用已有 Resource 能力，不重建管理体系。正文与控制遵循可读密度，文档操作以列表为主。
11. **运行授权和预算。** 保持 M2 的 Effective Knowledge Scope、原始 dataset 注入拒绝和委派不扩权。检索结果沿用已配置的超时、片段与字符预算，必要时补齐约束；授权检索片段可以进入模型上下文，基础设施凭据与整份原始文档不得无界注入。失败与空命中保持可区分。
12. **配置与边界值。** 文件类型、单文件／请求限制优先复用已有配置契约，并受实际 provider 支持范围约束；配置限制需要同时在服务器强制、前端展示和测试覆盖。未裁决的单 KB 总配额不在本规格中凭空给值，也不建设独立配额计费系统；若实施前仍缺必要部署参数，将其作为参数前置记录。
13. **审计和观测。** 复用平台 audit、request correlation 和 Tool Receipt。补充上传、删除、重试、重建索引及拒绝事件与本阶段摄取／检索指标；query、用户或文档标识不作 metrics label。不在 M3 建设 M5 的知识回执表和证据面板。

## Testing Decisions

用户已确认采用以下测试边界：canonical Resource／文档 API 为主，Knowledge Center 浏览器闭环和少量真实 RAGFlow 验收为辅，底层函数只补必要安全测试。

1. **主边界：canonical API 的可观察行为。** 使用已认证调用者访问 Resource／documents API，以真实测试数据库和隔离存储断言授权、持久化状态与检索可用性；Provider 边界用可控替身模拟处理中、超时、失败与重试。少量真实 RAGFlow 契约验收证明替身与实际 provider 一致。
2. **测试质量。** 测用户可观察的结果与安全不变量，不镜像内部函数、不绑定私有方法调用次序。复用已有 ResourceService、资源路由和知识 scope 的测试基建；仅对路径逃逸、大小边界、hash 和重试安全补必要低层测试。
3. **Gate 4。** 经平台 API 创建 KB→上传真实资料→等待 READY→通过已授权 Agent 的 `knowledge_search` 命中→删除草稿→新检索不再命中。模型最终答案正确率不替代文档检索验收。
4. **权限矩阵。** 两 KB×两用户覆盖 owner 管理、非 owner 读取／禁止修改、隐藏 KB、跨 KB 文档标识混用、猜测 provider ID、共享 Agent caller/owner 交叉、Workflow 和 Sub-Agent 不扩权。权限拒绝发生在副作用前。
5. **恢复与安全矩阵。** 覆盖非法路径／类型、大小临界值与超限、provider 不可达、解析失败、索引失败、重复重试、刷新后状态恢复、删除清理失败、敏感错误脱敏及预算上限。以确定性等待和可控 provider 状态测试异步过程，不依赖固定长 sleep。
6. **前端。** 复用现有 canonical Resource API mocking、组件交互和浏览器测试模式；验证真实状态映射、空／错／加载、按钮授权、上传反馈、重试／删除和 feature availability。以一条 Knowledge Center 浏览器闭环覆盖主要交互，不对每层实现写重复测试。
7. **验证 lane。** 每个行为切片按仓库要求 RED→GREEN，并运行最窄 lint/typecheck。新增／移动测试后执行 inventory；完成候选运行后端标准 lane、适用的前端 lane 和 `pr-standard`。视觉与可访问性验收使用对应 lane。记录所有子 lane 摘要和父 lane duration/status；不默认运行 release 的 `core-full`。
8. **证据口径。** 单元替身、真实 provider、真实模型、浏览器和环境受限项分别报告。跳过、失败、超时或无环境不能记为通过。采用隔离账户、KB、dataset 和文件，只清理本轮创建的验收资产。

## Out of Scope

- M4 的不可变 Knowledge Revision、manifest 发布门禁、Run 版本冻结与 provider drift 对账。
- M5 的完整 Retrieval Receipt 数据模型和 Evidence Panel，M6 的 Retrieval Test 页、A/B Eval 与质量指标体系。
- Local Knowledge、Workflow ExecutionTarget、M9 的 Local MCP／Secrets／Tray，以及设备线新能力。
- Knowledge Routing、多 provider 产品支持、企业来源 connector、语义缓存、document-level ACL 和自动知识写入。
- 全新导航系统、独立存储平台、通用队列平台、配额计费、Windows installer 和真实断网发行包交付。
- 将本次规格编写当成 M3 实施授权，或顺带修复收口报告中的全部缺口。

## Further Notes

- 依据：2026-09-08 后续工作总方案 M3 任务卡、知识专项文档的文档管理与 Gate 4，以及资源治理 V2、知识双层真源 ADR；使用项目 CONTEXT 术语。发生阶段编号冲突时采用总方案 M 编号。
- 当前收口报告结论为 UNVERIFIED。它已追加后端标准 lane 和 `pr-standard` 通过记录，但仍留有早期“需要重跑”措辞；实施前按同一候选的最新有效证据整理剩余项，不能重复把已通过项列为失败，也不能因此把真实环境缺口视为消失。
- M3 的实施前置是 M0-T0.1、M1/M2 适用 Gate 和所需合并验证闭合。M7/M8 独立缺口不自动阻塞知识线；共享授权、持久化或运行链路缺陷需单独判定影响。
- 规格发布沿用项目 `.scratch` 本地任务跟踪惯例；发布记录链接本规格，标签为 `ready-for-agent`，另列前置阻塞。该标签表示规格可用于后续切票，不覆盖 UNVERIFIED，也不自动启动实现。
- 测试边界已确认，本次 to-spec 已完成本地发布；M3 实施仍等待明确确认，后续可用 to-tickets 拆成有阻塞关系的纵向切片。
