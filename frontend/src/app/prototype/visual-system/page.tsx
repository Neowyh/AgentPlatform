"use client";

import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  Bot,
  ChevronDown,
  CircleHelp,
  Command,
  FileText,
  Home,
  Library,
  ListFilter,
  MessageSquare,
  MoreHorizontal,
  Plus,
  Search,
  Settings,
  Sparkles,
  Workflow,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

import "./visual-system.css";

type VariantKey = "A" | "B" | "C";
type PageKey =
  | "overview"
  | "chat"
  | "workflows"
  | "agents"
  | "library"
  | "settings";

const variants: Record<VariantKey, { name: string; note: string }> = {
  A: { name: "暖纸工作台", note: "轻暖底色 + 高密度工作台" },
  B: { name: "琥珀指挥台", note: "深色导航 + 清晰任务态" },
  C: { name: "书房仪表盘", note: "目录、任务流、上下文并置" },
};

const navItems: { key: PageKey; label: string; icon: typeof Home }[] = [
  { key: "overview", label: "总览", icon: Home },
  { key: "chat", label: "对话", icon: MessageSquare },
  { key: "workflows", label: "工作流", icon: Workflow },
  { key: "agents", label: "智能体", icon: Bot },
  { key: "library", label: "资料库", icon: Library },
  { key: "settings", label: "设置", icon: Settings },
];

function updateVariant(next: VariantKey) {
  const url = new URL(window.location.href);
  url.searchParams.set("variant", next);
  window.history.replaceState({}, "", url);
}

function Shell({
  variant,
  page,
  onPageChange,
  children,
}: {
  variant: VariantKey;
  page: PageKey;
  onPageChange: (page: PageKey) => void;
  children: React.ReactNode;
}) {
  return (
    <main className={`prototype prototype-${variant.toLowerCase()}`}>
      <div className="prototype-frame">
        <header className="prototype-topbar">
          <div className="brand-lockup">
            <span className="brand-mark">i</span>
            <span>iDeer</span>
            <span className="brand-divider">/</span>
            <span className="brand-section">工作台</span>
          </div>
          <div className="topbar-actions">
            <button className="search-trigger" type="button">
              <Search size={15} /> <span>搜索任何内容</span> <kbd>⌘ K</kbd>
            </button>
            <button className="icon-button" type="button" aria-label="帮助">
              <CircleHelp size={17} />
            </button>
            <div className="avatar">林</div>
          </div>
        </header>
        <div className="prototype-body">
          <aside className="prototype-sidebar">
            <div className="workspace-switcher">
              <div className="workspace-seal">研</div>
              <div>
                <strong>研究与创作</strong>
                <span>个人工作空间</span>
              </div>
              <ChevronDown size={14} />
            </div>
            <button className="new-button" type="button">
              <Plus size={16} /> 新建任务 <kbd>⌘ N</kbd>
            </button>
            <nav className="primary-nav" aria-label="主导航">
              <span className="nav-caption">工作区</span>
              {navItems.map(({ key, label, icon: Icon }) => (
                <button
                  className={`nav-item ${page === key ? "is-active" : ""}`}
                  key={key}
                  onClick={() => onPageChange(key)}
                  type="button"
                >
                  <Icon size={16} />
                  <span>{label}</span>
                  {key === "chat" && <span className="nav-count">4</span>}
                </button>
              ))}
            </nav>
            <div className="sidebar-footer sidebar-footer-persistent">
              <span className="status-dot" /> 本地模式已连接
            </div>
          </aside>
          <section className="prototype-content">{children}</section>
        </div>
      </div>
      <PrototypeSwitcher variant={variant} />
    </main>
  );
}

function PrototypeSwitcher({ variant }: { variant: VariantKey }) {
  const keys: VariantKey[] = ["A", "B", "C"];
  const index = keys.indexOf(variant);
  const cycle = (step: number) => {
    const next = keys[(index + step + keys.length) % keys.length]!;
    updateVariant(next);
    window.location.reload();
  };

  return (
    <div className="prototype-switcher" aria-label="原型方案切换">
      <span className="prototype-flag">PROTOTYPE</span>
      <button onClick={() => cycle(-1)} type="button" aria-label="上一个方案">
        <ArrowLeft size={15} />
      </button>
      <strong>
        {variant} · {variants[variant].name}
      </strong>
      <button onClick={() => cycle(1)} type="button" aria-label="下一个方案">
        <ArrowRight size={15} />
      </button>
    </div>
  );
}

function ScenarioSelector() {
  const [scenario, setScenario] = useState("创意设计");
  const [agent, setAgent] = useState<string | null>(null);
  const scenarios = ["日常办公", "创意设计", "专业任务"];
  const agents =
    scenario === "日常办公"
      ? ["会议助理", "文档整理员", "行政秘书"]
      : scenario === "专业任务"
        ? ["数据分析师", "研究助理", "项目顾问"]
        : ["内容编辑", "视觉策划师", "品牌顾问"];
  const tasks = agent
    ? ["先给我一个清晰提纲", "整理成可交付版本", "指出风险和下一步"]
    : [];
  return (
    <div className="scenario-selector">
      <div className="selector-heading">
        <span className="module-guide">
          <span className="guide-question">方向不明？</span>
          <span className="guide-answer">iDeer帮你找对帮手</span>
        </span>
      </div>
      <div className="scenario-tabs">
        {scenarios.map((item) => (
          <button
            className={scenario === item ? "is-active" : ""}
            key={item}
            onClick={() => {
              setScenario(item);
              setAgent(null);
            }}
            type="button"
          >
            {item}
          </button>
        ))}
      </div>
      <div className="selector-row">
        {(agent ? tasks : agents).map((item) => (
          <button
            className={`selector-pill ${agent ? "task-pill" : ""}`}
            key={item}
            onClick={() => (agent ? undefined : setAgent(item))}
            type="button"
          >
            {item}
            {agent ? <ArrowRight size={15} /> : <span>›</span>}
          </button>
        ))}
        {agent && (
          <button
            className="selector-back"
            onClick={() => setAgent(null)}
            type="button"
          >
            更换智能体
          </button>
        )}
      </div>
      <div className="selector-state">
        <span>已选</span>
        <strong>{agent ? `Agent · ${agent}` : `Scenario · ${scenario}`}</strong>
      </div>
    </div>
  );
}

function TaskComposer() {
  return (
    <div className="home-composer">
      <div className="home-placeholder">例如：把访谈整理成一页产品洞察…</div>
      <div className="composer-toolbar">
        <span>
          <Plus size={15} /> 添加资料
        </span>
        <span>
          <Sparkles size={14} /> 调用能力
        </span>
        <span>
          <Command size={14} /> /skill
        </span>
        <span>
          模型：Pro <ChevronDown size={13} />
        </span>
        <button type="button">
          <ArrowRight size={16} />
        </button>
      </div>
    </div>
  );
}

function RecentTaskCards({
  onPageChange,
}: {
  onPageChange: (page: PageKey) => void;
}) {
  return (
    <div className="recent-task-grid">
      <button
        className="recent-task-card task-copper"
        onClick={() => onPageChange("chat")}
        type="button"
      >
        <span className="task-preview">
          “增长机会集中在高复购用户，渠道成本仍需验证…”
        </span>
        <div>
          <strong>二季度市场分析</strong>
          <small>对话 · 12分钟前</small>
        </div>
        <i>继续</i>
      </button>
      <button
        className="recent-task-card task-plum"
        onClick={() => onPageChange("workflows")}
        type="button"
      >
        <span className="task-preview">
          “本周竞品动作已完成归类，等待生成周报…”
        </span>
        <div>
          <strong>竞品周报生成</strong>
          <small>工作流 · 昨天</small>
        </div>
        <i>查看</i>
      </button>
      <button
        className="recent-task-card task-moss"
        onClick={() => onPageChange("library")}
        type="button"
      >
        <span className="task-preview">
          “新增 8 份用户访谈，已建立主题索引…”
        </span>
        <div>
          <strong>产品知识库</strong>
          <small>资料库 · 2天前</small>
        </div>
        <i>打开</i>
      </button>
    </div>
  );
}

function GuidedHome({
  onPageChange,
}: {
  onPageChange: (page: PageKey) => void;
}) {
  return (
    <>
      <div className="page-heading welcome-heading">
        <div>
          <h1>iDeer，落地你的idea</h1>
        </div>
      </div>
      <ScenarioSelector />
      <div className="home-input-section">
        <div className="module-heading">
          <p>
            <span className="guide-question">目标明确？</span>
            <span className="guide-answer">iDeer帮你落地实现</span>
          </p>
        </div>
        <TaskComposer />
      </div>
      <div className="recent-heading section-heading">
        <div>
          <p>
            <span className="guide-question">工作复盘？</span>
            <span className="guide-answer">iDeer带你回到过去</span>
          </p>
        </div>
        <button
          className="text-button"
          onClick={() => onPageChange("chat")}
          type="button"
        >
          全部 <ArrowRight size={14} />
        </button>
      </div>
      <RecentTaskCards onPageChange={onPageChange} />
    </>
  );
}

function CockpitHome({
  onPageChange,
}: {
  onPageChange: (page: PageKey) => void;
}) {
  return (
    <div className="cockpit-home">
      <div className="page-heading welcome-heading">
        <div>
          <h1>iDeer，落地你的idea</h1>
        </div>
      </div>
      <div className="cockpit-columns">
        <div className="cockpit-main">
          <ScenarioSelector />
          <div className="home-input-section">
            <div className="module-heading">
              <p>
                <span className="guide-question">目标明确？</span>
                <span className="guide-answer">iDeer帮你落地实现</span>
              </p>
            </div>
            <TaskComposer />
          </div>
          <div className="recent-heading section-heading">
            <div>
              <p>
                <span className="guide-question">工作复盘？</span>
                <span className="guide-answer">iDeer带你回到过去</span>
              </p>
            </div>
            <span className="muted">按状态</span>
          </div>
          <RecentTaskCards onPageChange={onPageChange} />
        </div>
        <aside className="cockpit-rail">
          <span className="eyebrow">今日状态</span>
          <strong>12</strong>
          <span>项待处理</span>
          <div className="rail-stat">
            <span>运行中</span>
            <b>06</b>
          </div>
          <div className="rail-stat">
            <span>待输入</span>
            <b>02</b>
          </div>
          <div className="rail-stat">
            <span>本周完成</span>
            <b>28</b>
          </div>
          <button className="text-button" type="button">
            全部状态 <ArrowRight size={14} />
          </button>
        </aside>
      </div>
    </div>
  );
}

function EditorHome({
  onPageChange,
}: {
  onPageChange: (page: PageKey) => void;
}) {
  return (
    <div className="editor-home">
      <div className="editor-welcome">
        <h1>iDeer，落地你的idea</h1>
      </div>
      <div className="editor-selector">
        <ScenarioSelector />
      </div>
      <div className="editor-canvas">
        <div className="module-heading">
          <p>
            <span className="guide-question">目标明确？</span>
            <span className="guide-answer">iDeer帮你落地实现</span>
          </p>
        </div>
        <TaskComposer />
        <div className="editor-shortcuts">
          <button type="button">
            整理资料 <ArrowRight size={14} />
          </button>
          <button type="button">
            形成观点 <ArrowRight size={14} />
          </button>
          <button type="button">
            推进项目 <ArrowRight size={14} />
          </button>
        </div>
      </div>
      <div className="editor-recent">
        <div className="section-heading">
          <div>
            <p>
              <span className="guide-question">工作复盘？</span>
              <span className="guide-answer">iDeer带你回到过去</span>
            </p>
          </div>
          <button
            className="text-button"
            onClick={() => onPageChange("chat")}
            type="button"
          >
            全部 <ArrowRight size={14} />
          </button>
        </div>
        <RecentTaskCards onPageChange={onPageChange} />
      </div>
    </div>
  );
}

function ChatPage() {
  return (
    <>
      <div className="page-heading compact">
        <div>
          <span className="eyebrow">对话 · 最近活动</span>
          <h1>二季度市场分析</h1>
        </div>
        <div className="heading-actions">
          <button className="quiet-button" type="button">
            <ArrowDownToLine size={15} /> 导出
          </button>
          <button className="icon-button" type="button">
            <MoreHorizontal size={17} />
          </button>
        </div>
      </div>
      <div className="chat-layout">
        <div className="chat-main">
          <div className="date-rule">
            <span>今天 14:28</span>
          </div>
          <div className="message user-message">
            <div className="avatar small">林</div>
            <div>
              <span className="message-author">你</span>
              <p>请把三份市场材料整理成一页结论，突出增长机会和风险。</p>
            </div>
          </div>
          <div className="message agent-message">
            <div className="agent-avatar">
              <Sparkles size={16} />
            </div>
            <div>
              <span className="message-author">
                研究助理 <i>正在工作</i>
              </span>
              <p>我已经提取了 42 个关键事实，正在交叉验证增长率和渠道数据。</p>
              <div className="progress-card">
                <div>
                  <span className="status-dot" /> 分析材料{" "}
                  <strong>3 / 3</strong>
                </div>
                <div className="progress-line">
                  <i />
                </div>
                <small>预计还需 1 分钟</small>
              </div>
            </div>
          </div>
          <div className="composer">
            <div className="composer-tags">
              <span>
                研究助理 <X size={12} />
              </span>
              <span>
                二季度材料 <X size={12} />
              </span>
            </div>
            <div className="composer-placeholder">
              继续告诉研究助理你想知道什么…
            </div>
            <div className="composer-toolbar">
              <span>
                <Plus size={15} /> 添加资料
              </span>
              <span>
                <Command size={14} /> 快捷指令
              </span>
              <button type="button">
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </div>
        <aside className="context-panel">
          <span className="eyebrow">当前上下文</span>
          <h3>二季度材料</h3>
          <p>3 个文件 · 已全部读取</p>
          <div className="context-file">
            <FileText size={14} />
            <span>市场部季度复盘.pdf</span>
            <b>已读</b>
          </div>
          <div className="context-file">
            <FileText size={14} />
            <span>渠道数据明细.xlsx</span>
            <b>已读</b>
          </div>
          <div className="context-file">
            <FileText size={14} />
            <span>用户访谈摘录.docx</span>
            <b>已读</b>
          </div>
          <button className="text-button" type="button">
            管理上下文 <ArrowRight size={14} />
          </button>
        </aside>
      </div>
    </>
  );
}

function ListPage({ kind }: { kind: "workflows" | "agents" | "library" }) {
  const content = {
    workflows: {
      eyebrow: "工作流 · 可复用流程",
      title: "工作流",
      action: "新建工作流",
      icon: Workflow,
      rows: ["竞品周报生成", "会议纪要归档", "研究资料速览", "客户反馈分类"],
    },
    agents: {
      eyebrow: "智能体 · 专业助手",
      title: "智能体",
      action: "创建智能体",
      icon: Bot,
      rows: ["研究助理", "内容编辑", "数据分析师", "知识库管理员"],
    },
    library: {
      eyebrow: "资料库 · 统一资料入口",
      title: "资料库",
      action: "上传资料",
      icon: Library,
      rows: ["产品知识库", "市场研究", "品牌资产", "待整理资料"],
    },
  }[kind];
  const Icon = content.icon;
  return (
    <>
      <div className="page-heading compact">
        <div>
          <span className="eyebrow">{content.eyebrow}</span>
          <h1>{content.title}</h1>
          <p>把常用内容收在手边，下一步始终清楚。</p>
        </div>
        <button className="primary-button" type="button">
          <Plus size={15} /> {content.action}
        </button>
      </div>
      <div className="list-toolbar">
        <div className="filter-search">
          <Search size={15} />
          <span>搜索{content.title}</span>
        </div>
        <button className="filter-button" type="button">
          <ListFilter size={15} /> 筛选 <ChevronDown size={14} />
        </button>
        <span className="toolbar-count">{content.rows.length} 个项目</span>
      </div>
      <div className="resource-table">
        {content.rows.map((row, index) => (
          <div className="resource-row" key={row}>
            <span className={`resource-icon tone-${index + 1}`}>
              <Icon size={17} />
            </span>
            <div className="resource-name">
              <strong>{row}</strong>
              <span>
                {kind === "library"
                  ? `${index + 3} 个文件 · 最近更新 ${index + 1} 天前`
                  : `最近运行 ${index + 1} 小时前 · 由林老师创建`}
              </span>
            </div>
            <span className="row-status">
              <i /> {index === 0 ? "活跃" : "已保存"}
            </span>
            <MoreHorizontal size={17} className="row-more" />
          </div>
        ))}
      </div>
    </>
  );
}

function SettingsPage() {
  return (
    <>
      <div className="page-heading compact">
        <div>
          <span className="eyebrow">工作台 · 偏好设置</span>
          <h1>设置</h1>
          <p>调整你的工作方式，让每次进入都更顺手。</p>
        </div>
      </div>
      <div className="settings-layout">
        <nav className="settings-nav">
          <button className="is-active" type="button">
            外观与布局
          </button>
          <button type="button">模型与能力</button>
          <button type="button">通知</button>
          <button type="button">账户与权限</button>
        </nav>
        <div className="settings-content">
          <section className="settings-section">
            <div>
              <h3>界面密度</h3>
              <p>选择列表、消息和工作区的显示节奏。</p>
            </div>
            <div className="density-options">
              <button className="density-option" type="button">
                <span className="density-preview airy" />
                <strong>舒展</strong>
                <small>适合阅读</small>
              </button>
              <button className="density-option is-selected" type="button">
                <span className="density-preview balanced" />
                <strong>平衡</strong>
                <small>推荐设置</small>
              </button>
              <button className="density-option" type="button">
                <span className="density-preview dense" />
                <strong>紧凑</strong>
                <small>更多信息</small>
              </button>
            </div>
          </section>
          <section className="settings-section">
            <div>
              <h3>主题色</h3>
              <p>用一处温暖的色彩，标记你的工作路径。</p>
            </div>
            <div className="swatches">
              <button
                className="swatch copper is-selected"
                type="button"
                aria-label="铜金色"
              />
              <button
                className="swatch plum"
                type="button"
                aria-label="梅子色"
              />
              <button
                className="swatch moss"
                type="button"
                aria-label="苔绿色"
              />
              <button
                className="swatch blue"
                type="button"
                aria-label="靛蓝色"
              />
            </div>
          </section>
        </div>
      </div>
    </>
  );
}

export default function VisualSystemPrototype() {
  const [variant, setVariant] = useState<VariantKey>("A");
  const [page, setPage] = useState<PageKey>("overview");

  useEffect(() => {
    const value = new URLSearchParams(window.location.search).get("variant");
    if (value === "B" || value === "C") setVariant(value);
    const onKeyDown = (event: KeyboardEvent) => {
      if (
        ["INPUT", "TEXTAREA"].includes(
          (event.target as HTMLElement)?.tagName,
        ) ||
        (event.target as HTMLElement)?.isContentEditable
      )
        return;
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        const keys: VariantKey[] = ["A", "B", "C"];
        const index = keys.indexOf(variant);
        const next =
          keys[
            (index + (event.key === "ArrowRight" ? 1 : -1) + keys.length) %
              keys.length
          ]!;
        setVariant(next);
        updateVariant(next);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [variant]);

  const pageContent =
    page === "overview" ? (
      variant === "A" ? (
        <GuidedHome onPageChange={setPage} />
      ) : variant === "B" ? (
        <CockpitHome onPageChange={setPage} />
      ) : (
        <EditorHome onPageChange={setPage} />
      )
    ) : page === "chat" ? (
      <ChatPage />
    ) : page === "settings" ? (
      <SettingsPage />
    ) : (
      <ListPage kind={page} />
    );
  return (
    <Shell onPageChange={setPage} page={page} variant={variant}>
      {pageContent}
    </Shell>
  );
}
