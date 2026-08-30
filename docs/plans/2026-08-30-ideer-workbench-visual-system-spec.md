# iDeer 工作台视觉系统落地规格

> 状态：本地规格，待拆分实现任务
> 来源：已确认的暖纸工作台视觉原型与设计讨论
> 发布方式：仅保存在本地，不创建 Issue

## Problem Statement

当前 iDeer 的前端页面在视觉语言、信息层级和空间利用上缺少统一系统。首页的快捷入口曾经过于醒目，欢迎语、场景选择、任务输入和最近任务之间的主次关系不够清晰；部分页面字号偏小，不利于稍高龄用户；同时，偏平面的杂志化排版占用较多屏幕空间，降低了工作效率。

用户需要在一个连续的工作台中完成“理解工作方向—选择合适帮手—描述任务—回到最近工作”的过程。普通用户不应被迫理解 Agent、Skill、Connector 等平台概念，专业用户又需要能够继续使用精确的能力调用方式。当前页面需要在两类用户之间提供同一套、可渐进展开的工作体验。

## Solution

建立一套贯穿前端工作区的“暖纸工作台”视觉系统，并将已确认的视觉原型作为生产实现的参考基准。

工作台使用统一的页面 Shell、常驻左侧导航、内容容器、字号层级、暖纸色彩、卡片和控件样式。首页以固定品牌标题“iDeer，落地你的idea”为第一视觉焦点，随后按以下顺序组织入口：

1. 场景导向的快捷入口
2. Scenario Tab → Agent Pill → Task Chip 选择器
3. 任务输入框
4. 最近任务

场景选择、任务输入和最近任务模块各使用一条问题—回答式引导语作为模块标签：

- 方向不明？iDeer帮你找对帮手
- 目标明确？iDeer帮你落地实现
- 工作复盘？iDeer带你回到过去

引导语中的问题使用低强调色，回答使用产品强调色，并保持单行显示。页面保留足够的信息密度，但删除重复标题、冗余说明和与当前任务无关的装饰。

## User Stories

1. As an ordinary user, I want to see a clear welcome and a small set of task-oriented shortcuts, so that I can start without understanding platform terminology.
2. As an ordinary user, I want to choose a work scenario before describing a task, so that I receive relevant starting directions.
3. As an ordinary user, I want the shortcut entries to look like helpful suggestions rather than competing primary actions, so that I know the task input remains available.
4. As a professional user, I want to continue using the same workbench as ordinary users, so that I do not need to learn a separate product surface.
5. As a professional user, I want advanced Agent, Skill, and Connector options to remain discoverable from navigation and task input, so that I can make precise capability choices when needed.
6. As a user, I want the three fixed Scenario Tabs to be visible and recognizable, so that I can choose a broad direction quickly.
7. As a user, I want Agent Pills to appear under the selected Scenario Tab, so that I can choose a suitable helper without browsing the full capability catalogue.
8. As a user, I want Task Chips to appear only after selecting an Agent Pill, so that each concrete task has an understandable execution context.
9. As a user, I want to select no level, one level, or a more specific level of the scenario hierarchy, so that the platform can control model input with the precision I need.
10. As a user, I want the selector to preserve one stable lower row when moving from Agent Pills to Task Chips, so that the page does not become visually confusing or vertically unstable.
11. As a user, I want the task input to remain the strongest action after I understand the available direction, so that I can directly express a clear goal.
12. As a user, I want the input box to retain a plain-language placeholder, attachment controls, capability invocation, slash-style Skill invocation, model selection, and send action, so that both novice and expert workflows remain supported.
13. As a user, I want recent tasks to show enough name, type, time/status, and conversation summary, so that I can recognize the right previous task quickly.
14. As a user, I want recent tasks to be presented as visually distinct but restrained cards, so that visual recognition is faster without turning the page into a decorative card wall.
15. As a user, I want the recent-task module to align with the scenario and input modules, so that the page reads as one coherent work sequence.
16. As a user with lower visual acuity, I want the welcome title and module guidance to be visibly readable, so that I do not need to zoom or inspect small labels.
17. As a user, I want the page to use no more than three effective font sizes, so that the hierarchy is easy to learn and scan.
18. As a user, I want all page text to use a consistent sans-serif family, so that reading remains comfortable across work areas.
19. As a user, I want the left navigation to remain available while moving between work areas, so that I can switch context without losing the workbench frame.
20. As a user, I want the navigation model to remain conceptually consistent across viewport sizes, so that device changes do not require learning a second information architecture.
21. As a user, I want the home page to avoid a separate activity action and persistent task-progress banner in the welcome state, so that the first visual moment stays focused on starting work.
22. As a user, I want capability management to remain in Agent, Skill, and Connector navigation surfaces, so that the home page stays task-first.
23. As a user, I want Connector to represent an external system or data-source connection, such as MCP, a database, a file system, or a third-party API, so that it is not confused with an Agent or Skill.
24. As a user, I want the page to use screen space efficiently, so that more useful work context is visible without sacrificing readable spacing.
25. As a maintainer, I want shared visual primitives to carry the workbench language across pages, so that future visual changes do not require independent restyling of every screen.
26. As a maintainer, I want existing business logic, API contracts, permission behavior, and resource semantics preserved, so that the visual migration does not introduce unrelated product changes.
27. As a tester, I want route-level tests to verify visible behavior through stable user-facing selectors, so that the acceptance suite protects the experience rather than CSS implementation details.
28. As a tester, I want desktop and mobile visual baselines for core work areas, so that density and responsive regressions are visible before release.

## Implementation Decisions

- **Visual direction**: Adopt the warm paper workbench as the lead production direction. Warmth comes from paper-toned surfaces, restrained copper/plum/moss accents, measured borders and shadows, and clear spacing; it must still feel like productive software rather than a magazine spread.
- **Role surface**: Ordinary and professional users share one workbench. Shortcuts provide novice-friendly entry; navigation and input menus expose advanced capability operations progressively.
- **Home hierarchy**: The fixed title “iDeer，落地你的idea” is the largest text. Module guidance is the second level. Input text, recent-task card text, and supporting controls use the smallest functional level. The effective system contains no more than three sizes: 32px title, 16px module guidance, and 14px operational/content text, subject to responsive adjustment while preserving the same hierarchy.
- **Typography**: Use one sans-serif family throughout the workbench. Weight, color, spacing, and grouping carry hierarchy; serif and monospace display treatments are not part of this direction.
- **Welcome content**: The home welcome has no separate subtitle, “工作台” label, activity module, or persistent progress element. The fixed brand title is followed by the task-start sequence.
- **Module labels**: “选择一个场景”, “开始任务”, and “最近任务” are redundant headings and are removed. The one-line question—answer guidance is the functional label for each corresponding module.
- **Home order**: The user-facing sequence is welcome title → scenario-oriented quick entries → Scenario selector → task input → recent tasks. Agent, Skill, and Connector browsing/configuration remains in persistent capability navigation.
- **Quick entries**: Quick entries are restrained, visually unified, and subordinate to the main task input. They communicate common task directions in plain language and do not promise a guaranteed Skill invocation.
- **Scenario model**: Keep three fixed Scenario Tabs: “日常办公”, “创意设计”, and “专业任务”; “创意设计” remains the default entry group.
- **Selection model**: Preserve the three-level Scenario Tab → Agent Pill → Task Chip vocabulary and interaction. Users may leave the selector unselected, choose only a Scenario Tab, or select an Agent Pill and then its Task Chips. A Task Chip cannot appear or exist independently of an Agent Pill.
- **Selector layout**: Scenario Tabs remain the top group. The lower selector position alternates between the selected Scenario's Agent Pills and the selected Agent's Task Chips rather than displaying all levels at once. The selected state remains understandable at every allowed granularity.
- **Input capabilities**: Keep plain-language task entry, attachments, capability invocation, slash-style Skill invocation, model selection, and send action. The input does not receive duplicated upper-left or upper-right helper descriptions.
- **Recent tasks**: Use visually recognizable cards containing task name, task type, time or status, and one meaningful recent-conversation summary. Recent tasks are content on the home surface, not a duplicate task-navigation section.
- **Navigation**: Keep the left navigation persistent as the workbench frame. It provides the path to Agent, Skill, Connector, Workflow, library, and settings surfaces while avoiding a second recent-task navigation tree.
- **Connector semantics**: Connector means an external system or data-source connection made available to iDeer work, including MCP, database, file-system, or third-party API connections.
- **Shared visual layer**: Extract or reuse shared Shell, navigation, page container, heading, guidance, input, card, button, color, spacing, and typography primitives at the highest existing component seam. Page-specific composition should consume these primitives rather than copy visual rules.
- **Production boundary**: The visual prototype is the primary design reference for composition and hierarchy, not a production implementation to copy wholesale. Existing API, state, permissions, routing, localization, and runtime behavior remain authoritative unless a separate ticket explicitly changes them.
- **Responsive behavior**: Preserve the same information architecture and interaction meaning across desktop and smaller viewports. Reflow, stacking, and density adjustments are allowed; hiding essential navigation or changing the task order is not.
- **Accessibility**: Preserve visible keyboard focus, semantic controls, readable contrast, touch-sized selection targets, and screen-reader names for icon-only actions. Do not use color as the only distinction between question and answer or between task types.
- **Primary testing seam**: Use route-level Playwright acceptance against stable mocked API data as the highest seam. Shared component behavior may be tested at its public user-facing seam when route coverage cannot isolate a rule, but internal CSS selectors and implementation details are not the contract.

## Testing Decisions

- Tests should assert externally observable behavior: visible hierarchy, presence or absence of redundant labels, navigation reachability, selection transitions, input affordances, recent-task recognition data, responsive layout, and accessibility properties.
- Tests should not assert private component structure, exact class names, internal CSS declarations, or a particular DOM nesting when the same user-facing behavior can be verified through role, accessible name, text, or stable test identifiers.
- Extend the existing route-level visual screenshot coverage for the workbench shell and core pages. Use deterministic mocked API responses so screenshot changes represent intentional product changes rather than live-data drift.
- Add or extend visual baselines for the warm-paper home, conversation/thread, Agent/Skill/Connector surfaces, Workflow, library, and settings. Cover the agreed desktop and mobile viewports; include dark mode only where the product surface supports it as a real requirement.
- Add behavior coverage for the home flow: quick entry remains subordinate to the task input; each module has one single-line guidance sentence; redundant module headings are absent; the fixed welcome title is present; and recent tasks align conceptually with the entry stack.
- Add behavior coverage for Scenario Tab → Agent Pill → Task Chip: no selection, Scenario-only selection, Agent selection, Task Chip visibility only after Agent selection, and preservation of the existing selection granularity rules.
- Add behavior coverage for task input capabilities: attachment affordance, capability menu, slash-style Skill invocation, model choice, and send action remain reachable without introducing duplicate helper descriptions.
- Add behavior coverage for recent tasks: each card exposes recognizable task information and routes to the correct work surface.
- Add accessibility checks for heading order, accessible names, keyboard focus, keyboard operation of selector controls, contrast of question/answer guidance, and touch target sizing.
- Reuse prior art from the existing workspace visual screenshot tests, workspace smoke tests, cascade interaction tests, chat/input tests, resource-management tests, workflow tests, and accessibility suite.
- Run the narrowest affected frontend tests during each implementation slice. Run the standard frontend lane after all slices, then run the cross-stack PR lane when the change crosses shared frontend/backend contracts or is prepared for review.
- Visual failures must be classified as intentional baseline changes, layout regressions, content regressions, runtime failures, or environment failures before updating snapshots.

## Out of Scope

- Replacing or redesigning backend APIs, Agent/Skill/Connector data models, permission rules, resource visibility, or runtime execution behavior.
- Introducing database-backed Scenario configuration, admin CRUD, dynamic scenario authoring, or a new capability registry as part of the visual migration.
- Changing the established Scenario Tab → Agent Pill → Task Chip semantics, including allowing independent Task Chips.
- Making the home page a complete Agent, Skill, or Connector catalogue.
- Adding a persistent activity module, global progress dashboard, task-navigation tree, or unrelated gamification surface to the welcome state.
- Replacing the existing direct input, slash-style Skill invocation, or capability menu with a new invocation protocol.
- Creating separate ordinary-user and professional-user products or separate navigation architectures.
- Pixel-perfect reproduction of WorkBuddy branding or assets.
- Redesigning landing, authentication, or administrative governance surfaces unless they are explicitly added to a later scope decision.
- Publishing this specification or its follow-up tasks to GitHub; this document is intentionally local.

## Further Notes

- This document supersedes earlier visual drafts where they conflict with the latest confirmed prototype decisions, especially the fixed title, removal of welcome subtitle and redundant module headings, single-line guidance copy, and three-level type hierarchy.
- The existing prototype remains a useful visual reference for comparison among A/B/C layout directions. Production work should select the warm paper direction as the default while retaining only structural alternatives that improve a concrete user need.
- The next planning step is to split this specification into tracer-bullet implementation tasks with explicit blocking edges. A sensible first ticket is the shared workbench visual foundation, followed by the home entry flow and then the remaining work areas.
