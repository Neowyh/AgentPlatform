/** Short, task-oriented copy for the bundled capability catalog. */
export const RESOURCE_SUMMARIES: Record<string, string> = {
  // Experts
  abaqus: "从建模、材料、网格到结果导出，协助完成可追溯的 Abaqus 仿真任务。",
  "code-dev": "把需求拆成可执行的开发任务，协助编码、调试、评审、测试和交付。",
  "creative-play":
    "当你还没有明确方案时，通过发散、质询和压缩表达帮你找到可行方向。",
  "data-analysis":
    "读取 Excel 或 CSV，完成清洗、统计、透视、关联分析并输出可复用结果。",
  "document-writing":
    "起草、改写和校对正式文书，帮助把零散材料整理成规范文档。",
  "fault-zeroing":
    "根据资料建立故障树、评估底事件和证据链，生成可审查的归零报告。",
  "frontend-design":
    "把产品目标转成可实现的网页界面，兼顾视觉层级、交互和前端规范。",
  "office-docs":
    "读取和制作 Word、PDF 等办公文档，处理结构、格式、内容和文件交付。",
  "paper-review":
    "从方法、贡献、文献定位和表达质量评审论文，并给出建设性修改意见。",
  "ppt-web":
    "根据主题和材料设计演示结构，生成具有视觉层级的 PPT 或网页演示稿。",
  "skill-workshop":
    "通过对话设计、创建和完善 Agent Skill，让 iDeer 学会一类新任务。",
  "srs-writing":
    "依据软件任务书逐项确认需求，生成符合 GJB438C-2021 的 SRS 和追踪矩阵。",
  summarize: "把长文档或对话压缩成重点、结论、行动项和便于复查的结构化摘要。",
  translation: "翻译并润色多语言内容，保持术语、格式、语气和占位符的一致性。",
  "visual-doc": "将文字材料整理成版式清晰、可直接交付的正式文档。",

  // Skills
  "abaqus-bc":
    "定义或检查 Abaqus 位移、转动、对称、温度等边界条件及其作用区域和分析步。",
  "abaqus-dependency-preflight-validator":
    "执行 Abaqus 前检查跨文件模型、区域、分析步、作业和 ODB 标识是否一致。",
  "abaqus-docs": "核对 Abaqus Python API 的符号、参数、模块位置和版本兼容性。",
  "abaqus-export":
    "将 Abaqus 几何、网格、输入文件或只读结果按指定格式导出到可追溯位置。",
  "abaqus-field": "定义或检查应力、温度、孔压、速度等初始条件和预定义场。",
  "abaqus-geometry":
    "创建或审查 Abaqus 零件、草图、装配、分区、集合、表面和 CAD 几何。",
  "abaqus-interaction":
    "定义或检查接触、绑定、耦合、连接器等区域之间的相互作用。",
  "abaqus-load":
    "定义或检查力、力矩、压力、重力、牵引、通量等载荷的方向、区域和激活步。",
  "abaqus-mapped-load-provenance-auditor":
    "审计映射载荷的来源面、摘要、单位、符号和面数量是否满足模型契约。",
  "abaqus-material":
    "定义或检查材料、截面和岩土本构参数，并保留单位与来源依据。",
  "abaqus-mesh":
    "生成或审查单元类型、种子、网格控制、局部细化、质量和接口映射。",
  "abaqus-odb": "只读检查 ODB 的分析步、帧、场输出、历史输出、区域和结果极值。",
  "abaqus-output": "设计场输出或历史输出变量、区域、频率和结果文件大小控制。",
  "abaqus-parametric-project-starter":
    "为多文件 Abaqus Python 自动化项目先建立配置、命名、执行和输出边界。",
  "abaqus-script-debugging-checklist":
    "排查 Abaqus Python 回溯、空区域、缺失标识、作业创建和 ODB 打开失败。",
  "abaqus-shared-naming-manifest-builder":
    "把多个 Abaqus 脚本重复使用的模型、区域、分析步和结果标识集中成命名契约。",
  "abaqus-staged-construction-auditor":
    "审计分阶段激活或停用事件的集合、动作、分析步和冲突状态。",
  "abaqus-step":
    "定义或检查分析步骤、增量控制、非线性设置、稳定化、施工序列和重启动关系。",
  "abaqus-tunnel-local-mesh-rebuilder":
    "修复隧道或地下通道邻域中不对称、过密、难扫掠或映射不一致的土体和衬砌网格。",
  "academic-paper-review":
    "评审上传的论文 PDF，检查方法、贡献、文献定位并生成结构化审稿意见。",
  "anthropic-docx":
    "创建、读取、编辑和校验 Word 文档、模板、目录、页码、批注和修订。",
  "anthropic-pdf": "读取、提取、合并、拆分、OCR、加密和填写 PDF 文件及表单。",
  "anthropic-pptx":
    "创建、读取和编辑 PPTX/POTX 演示文稿、版式、备注、评论和模板。",
  "anthropic-xlsx": "读取、清洗、计算、格式化和分析 Excel、CSV 等表格文件。",
  "ask-matt": "根据当前问题判断最合适的技能或工作流入口，帮你少走选择步骤。",
  bootstrap: "通过几轮对话了解你的偏好和工作方式，生成一份个性化 SOUL.md。",
  caveman:
    "在保留技术准确性的前提下压缩表达；输入 /caveman 或明确要求超短沟通即可使用。",
  "chart-visualization":
    "从数据和目标中选择合适图表，提取参数并生成可交付的图表图片。",
  "chip-software-development-package":
    "从同型号同封装芯片资料中提取带证据引用的嵌入式软件开发知识包。",
  "claude-to-ideer":
    "通过 HTTP API 向 iDeer 发消息、上传文件、查询资源、管理记忆或委托复杂任务。",
  "code-documentation":
    "为代码、API、仓库或软件项目生成 README、参考文档、架构说明和开发指南。",
  "code-review":
    "从规范和需求两个角度审查分支、提交或 PR，并列出需要修复的问题。",
  "codebase-design":
    "用模块、接口、边界和测试缝隙等术语改进代码结构和可维护性。",
  "consulting-analysis":
    "先搭建研究框架和数据需求，再生成市场、行业、品牌或财务分析报告。",
  "data-report":
    "从表格生成自包含 HTML 分析报告，包含 KPI、ECharts 图表和文字洞察。",
  "deep-research": "围绕一个问题开展多角度联网研究，整理高可信来源和证据链。",
  "diagnosing-bugs": "用复现、定位、验证和回归循环诊断复杂故障或性能下降。",
  "domain-modeling": "建立项目术语、领域对象和架构决策记录，减少团队理解偏差。",
  eli5: "把复杂主题讲成小白能懂的单文件图文说明，少术语、多直观例子。",
  "find-skills": "根据你的目标发现、比较并安装适合的技能。",
  "github-deep-research":
    "围绕 GitHub 项目、Issue、PR 和代码资料开展带引用的深度研究。",
  "grill-me": "通过连续追问暴露目标、方案或决策中的假设和薄弱点。",
  "grill-with-docs": "结合已有文档逐条质询方案，指出证据缺口、矛盾和未决决定。",
  grilling: "对计划或想法进行高强度压力测试，直到关键风险和选择被说清楚。",
  "guizang-ppt-skill": "用杂志化网页视觉和预设版式生成有叙事结构的演示文稿。",
  handoff: "整理当前进展、证据、未完成项和下一步，使另一位协作者可以无缝接手。",
  "humanizer-zh": "降低中文文本的机器腔，保留原意、事实和结构，使表达更自然。",
  "image-generation": "根据文字或参考图生成、修改和变体化图片素材。",
  implement: "把已经确认的方案拆成改动、测试和验收步骤并实际落地。",
  "improve-codebase-architecture":
    "发现代码库中可加深的模块边界，提出更易测试和导航的架构改进。",
  "newsletter-generation":
    "把资料整理成适合发布的 newsletter，包含主题、结构、摘要和正文。",
  officecli: "通过命令行处理办公文件，适合批量转换、检查和自动化文档任务。",
  "podcast-generation":
    "把主题和资料转成播客脚本、角色分工、音频提示和生成流程。",
  "ppt-generation": "根据目标和素材生成演示文稿结构、页面内容和视觉建议。",
  "proactive-agent": "帮助设计会主动提醒、记录上下文并持续推进任务的 AI 伙伴。",
  prototype: "快速制作一次性原型，用来验证状态模型、交互逻辑或界面方向。",
  research: "针对问题查阅高可信一手资料，形成带来源的研究结论并记录到仓库。",
  "resolving-merge-conflicts":
    "分析并解决正在进行的 Git merge 或 rebase 冲突，保留双方有效改动。",
  "setup-matt-pocock-skills":
    "检查并接入预装的 Matt Pocock 技能集合，不重复安装或修改主机环境。",
  "skill-creator":
    "从需求出发创建或改进一个结构清晰、可触发、可验证的 Agent Skill。",
  "structured-longform-writing":
    "按模板和质量规则完成提案、报告、博客等长文写作，并控制结构与语气。",
  "surprise-me": "在信息不足时提供有创意的方向、方案或内容灵感。",
  "systematic-literature-review":
    "制定检索和筛选流程，系统整理论文证据并形成文献综述。",
  tdd: "用红灯、最小实现、绿灯和重构循环开发可验证的代码功能。",
  teach: "根据你的基础和目标，把知识拆成循序渐进、带例子的学习路径。",
  "to-questionnaire": "把模糊目标转成一组高价值问题，帮助补齐需求和决策信息。",
  "to-spec": "把讨论结果整理成开发者可直接执行的功能规格说明。",
  "to-tickets": "把方案拆成边界清晰、可验收、可分派的工程任务单。",
  translate: "翻译并润色多语言文本，保持术语、格式、占位符和语气稳定。",
  triage: "按状态机分流 Issue 和 PR，完成分类、验证、追问并形成可执行简报。",
  "vercel-deploy-claimable":
    "把项目部署到 Vercel，并返回预览地址和可认领链接。",
  "video-generation":
    "把视频需求整理成结构化提示词，支持参考图、画面规格和生成流程。",
  "wait-what": "当上一轮表达没有被理解时，暂停并重新用更清楚的方式说明。",
  wayfinder: "把大型目标拆成依赖关系清晰的研究、决策和执行任务地图。",
  "web-design-guidelines":
    "按 Web Interface Guidelines 检查界面可用性、无障碍和交互规范。",
  wizard: "生成引导人完成凭据、后台配置或切换操作的交互式 Bash 向导。",
  "wps-gongwen": "按中文公文规范起草通知、请示、报告、批复等正式文件。",
  "wps-proofread": "检查中文文档的错别字、语病、标点和正式发布前的表达问题。",
  "writing-for-agents":
    "编写让 Agent 更容易触发、理解和执行的 Skill、AGENTS.md 或 CLAUDE.md。",
};

export function getResourceSummary(
  slug: string | null | undefined,
  fallback: string,
): string {
  return (slug && RESOURCE_SUMMARIES[slug]) ?? fallback;
}
