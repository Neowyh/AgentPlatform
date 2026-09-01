# iDeer 工作台导航与预装资源同步规格

> 状态：本地规格，待拆分实现任务
> 来源：已确认的工作台导航改造讨论、资源目录核验与运行库诊断
> 发布方式：仅保存在本地，不创建 Issue
> 关联决策：[ADR 0001](../adr/0001-workbench-capability-navigation.md)

## Problem Statement

用户需要从一个稳定、任务导向的工作台进入新任务、回看历史、管理可复用能力、运行工作流和使用资料库。当前左侧导航仍将聊天、智能体、资源、自动化和工作流拆散；Skill 与 MCP 工具配置还散落在设置中，用户必须理解内部模块边界才能找到能力。

新对话中的 Agent Pill 已按场景配置，且仓库已提供对应的预装 Agent、Skill 和 Workflow 资源定义；但运行时资源数据库仍只有旧的一部分资源。智能体页面只读取当前用户可见的资源目录，因此只显示两个旧 Agent，静态 Agent Pill 与真正可调用、可管理的 Agent 资源脱节。

## Solution

将工作台左侧导航固定为“新对话、对话历史、专家-技能-连接器、工作流、资料库”。“专家-技能-连接器”作为一个能力中心，提供专家、技能和连接器三个独立、可深链的资源页签；设置中的技能和工具入口迁入该能力中心，旧入口无感跳转。记忆继续留在设置，管理员系统工具继续留在管理员治理界面。

将预装资源清单作为运行时资源目录的唯一部署输入。首次初始化和已存在数据库升级时，均以幂等方式将清单内全部公开预装 Skill、Agent 与 Workflow 及其版本、依赖关系和可见性写入资源数据库。完成同步后，每个 Agent Pill 都能解析到对应的公开 Agent 资源；能力中心与新对话使用同一资源目录和同一权限判断。

## User Stories

1. As a workbench user, I want to see New conversation first in the sidebar, so that I can start a task without interpreting platform terminology.
2. As a workbench user, I want Conversation history as a separate sidebar destination, so that opening prior work never competes with starting a new task.
3. As a workbench user, I want one Expert-Skill-Connector destination, so that reusable capabilities are not scattered across navigation and Settings.
4. As a workbench user, I want the capability center to open directly on its three user-facing tabs, so that I can switch between Experts, Skills, and Connectors without changing product areas.
5. As a workbench user, I want each capability tab to have a stable deep link, so that I can return to or share the exact capability category.
6. As a workbench user, I want Expert to be the user-facing name for an Agent, so that the navigation uses task-oriented language while runtime semantics stay unchanged.
7. As a workbench user, I want Connector to mean MCP connection configuration, so that I do not confuse an external connection with a Skill or Expert.
8. As a workbench user, I want to browse all resources visible to me in each tab, so that public, department, and my own private resources are discoverable consistently.
9. As an authorized resource owner, I want to create, view, edit, archive/delete, import, export, favorite, use in a conversation, and request a visibility change from the same resource tab, so that I do not need a second management surface.
10. As a user of public built-in resources, I want to favorite, inspect, export, and invoke allowed resources while edit and deletion actions remain unavailable, so that convenient use does not weaken ownership rules.
11. As an administrator, I want Connector configuration actions available in the Connector tab, so that MCP setup is discoverable without exposing write authority to unauthorized users.
12. As a non-administrator, I want to see only Connector actions I am authorized to use, so that the interface does not imply permissions I do not have.
13. As a user starting a task, I want a selected Expert Pill to resolve to the matching catalog Agent, so that its actual Skill closure and resource identity are applied to the conversation.
14. As a user selecting a Task Chip, I want the selected Skill to remain a preferred execution context rather than a guaranteed invocation, so that the existing Scenario Tab → Agent Pill → Task Chip contract remains accurate.
15. As a user, I want a Connector selected for a conversation to authorize or make that connection available to the selected Expert, so that a Connector is not incorrectly presented as a slash-invoked Skill.
16. As a workflow user, I want one Workflow destination instead of separate Automation and Workflow entries, so that the product has one clear automation concept.
17. As a library user, I want Library to remain a separate sidebar destination, so that documents and materials are not mixed with executable capabilities.
18. As a user, I want Memory to remain in Settings, so that personal long-term context is not confused with conversation history or reusable capabilities.
19. As an administrator, I want system-tool governance to remain in the administrative surface, so that user capability management and system governance retain their distinct permission boundaries.
20. As a user following an old Settings action, I want Skill and Tool launches to arrive at the matching capability tab, so that migration does not create broken paths or duplicated pages.
21. As a deployment operator, I want the complete preinstalled resource manifest seeded into a new runtime database, so that a fresh installation exposes all intended Skills, Experts, and Workflows.
22. As a deployment operator upgrading an existing runtime database, I want missing manifest resources created without overwriting locally modified resources by default, so that upgrades restore bundled availability safely.
23. As a deployment operator, I want resource seeding to persist Agent-to-Skill and Workflow-to-Agent dependencies using canonical resource identities, so that execution and visibility checks use one graph.
24. As a deployment operator, I want the seed report to identify created, updated, unchanged, and skipped resources, so that incomplete synchronization is diagnosable.
25. As a user, I want the Expert page to list every public preinstalled Agent after synchronization, so that the page matches the choices offered by Agent Pills.
26. As a user, I want only resources visible to my role to appear in the capability center, so that the navigation does not bypass RBAC or visibility rules.
27. As a maintainer, I want the scenario configuration and resource catalog to agree on every Agent Pill slug, so that a missing Agent cannot silently degrade into a visual-only selector.
28. As a maintainer, I want preinstalled resources to be packaged for offline deployment together with their source content and manifest, so that disconnected installations remain complete.
29. As a tester, I want one user-facing acceptance flow to cover navigation, resource visibility, and Agent Pill resolution, so that the user experience is protected across the frontend/backend boundary.
30. As a tester, I want database-level seed tests for fresh and upgraded catalogs, so that a page-empty regression is caught before release.

## Implementation Decisions

- **Navigation order and destinations**: The persistent workbench sidebar presents New conversation, Conversation history, Expert-Skill-Connector, Workflow, and Library in exactly that order. New conversation and Conversation history are distinct destinations; Workflow replaces both user-facing Automation and Workflow entries.
- **Capability center**: Expert-Skill-Connector is one top-level destination with Expert, Skill, and Connector pages. It may retain tab-specific URLs and last-selected-tab behavior, but it must not become three separate primary sidebar items.
- **Terminology**: Use Expert in user-facing capability navigation and resource headings; retain Agent for the canonical runtime resource type, API contracts, Agent Pill vocabulary, and implementation identifiers. Connector means MCP connection configuration; it does not mean generic tool, Skill, or Agent.
- **Settings migration**: Remove Skill and Tool from the Settings section list. Existing callers of those sections must redirect to the Skill or Connector page respectively. Account, Appearance, Notification, Memory, and About remain Settings concerns.
- **Resource actions**: Expert, Skill, and Connector pages provide a common lifecycle/action layout: create, browse, inspect, edit, archive/delete, favorite, conversation use, import, export, and visibility-change request. The action set is authorization-aware: a page may show an unavailable state or omit an action when the actor cannot perform it.
- **Permission preservation**: Consolidating pages changes discoverability, not ownership or RBAC. Public/system-owned resources remain non-editable to ordinary users; resource owners retain permitted lifecycle actions; MCP Connector configuration write actions retain their administrator boundary; administrator system-tool governance stays outside the capability center.
- **Conversation use**: Expert invocation starts an Expert-scoped conversation. Skill invocation uses the established preferred-Skill behavior. Connector use selects or authorizes a connection for a conversation and its Expert; it never creates slash-command semantics.
- **Scenario contract**: Preserve Scenario Tab → Agent Pill → Task Chip. Task Chips cannot exist without an Agent Pill. Selecting an Agent Pill must resolve the catalog Agent by its canonical identity; static Task Chip Skill lists remain a display/fallback aid only until the catalog lookup succeeds.
- **Catalog consistency invariant**: Every configured Agent Pill slug must have one active, visible canonical Agent resource in the seeded public bundle. Every bundled Agent must have valid Agent content and only reference bundled Skills whose visibility permits the dependency. The bundled Workflow must similarly resolve its Agent dependencies by canonical identity.
- **Bundled resource seeding**: Treat the versioned bundled manifest as the complete desired set for preinstalled Skill, Agent, and Workflow resources. The same seeding service is used for a fresh database and an upgrade. It creates missing resources and initial versions, refreshes unmodified bundled content when the manifest changes, records dependency edges, and reports created/updated/unchanged/skipped totals.
- **Upgrade safety**: Default synchronization uses a keep policy for locally modified bundled resources. It must not silently overwrite local changes. An explicit operator policy may override a modified bundled resource, and skipped resources must remain visible in the seed report.
- **Deployment wiring**: Every supported production and offline deployment path must run canonical bundled-resource seeding only after the target database and bundled-resource owner are available. Local development must provide one documented, safe synchronization command; it must not rely on source directories being scanned by the frontend.
- **No new resource type**: Connector configuration remains a Connector-facing adaptation over the existing MCP configuration boundary. The canonical bundled resource types remain Skill, Agent, and Workflow unless a separately approved data-model change introduces Connector as a catalog type.
- **Resource visibility**: The capability center consumes the existing visible-resource query and favorite state. It must not build an independent client-side list that can disagree with the catalog or expose unauthorized resources.

## Testing Decisions

- The highest primary seam is a cross-stack user-facing acceptance flow: seed a deterministic catalog, authenticate a role, visit the workbench, navigate to the capability center, and assert visible resources and allowed actions. This verifies behavior rather than page composition.
- Reuse the existing resource seeding service tests as the database seam. Extend them to assert the complete repository manifest, idempotent fresh seeding, upgrade seeding of a partially populated catalog, stable Agent-to-Skill dependencies, and the expected Agent count.
- Add a regression test whose fixture represents the current failure: a database with only the legacy bundled Agents and Skills is upgraded using the complete manifest, then exposes every configured Agent Pill as a canonical Agent resource.
- Reuse existing resource API and RBAC tests for visible-resource filtering, resource lifecycle permissions, favorites, visibility applications, imports, exports, and archived resources. Assertions must cover public, private, department, owner, ordinary-user, and administrator cases.
- Reuse existing workspace navigation, settings, resource-management, scenario-cascade, Agent gallery, and conversation tests. Assert accessible labels, destination URLs, active navigation state, Settings migration redirects, and absence of duplicate Skill/Tool Settings entries.
- Add route-level behavior tests for Expert-Skill-Connector tabs: deep-link selection, resource listing, create/import affordances, ownership-aware action availability, conversation invocation, and Connector-specific authorization behavior.
- Add a route-level scenario test that selects every configured Agent Pill against seeded resources and asserts a resolved Agent resource identity plus the expected Skill closure. Do not assert component-private state or DOM nesting.
- Add deployment/intranet script tests that prove the bundle contains the manifest and source assets, invokes canonical seeding after the Gateway is ready, fails closed when seeding fails, and reports the result without credentials.
- Good tests assert user-observable behavior, persisted catalog state, and published resource dependencies. They do not assert CSS classes, internal hook calls, implementation-specific component trees, or raw static configuration shape when an API or user flow can express the contract.
- During implementation, run focused frontend and backend tests for each vertical slice; then run the applicable frontend/backend standard lanes and `pr-standard` because the change crosses navigation, resources, RBAC, and runtime selection. Treat hung or sandbox-blocked tests as incomplete, not passing.

## Out of Scope

- Changing the existing Scenario Tab, Agent Pill, or Task Chip terminology and selection granularity.
- Making Task Chip selection a guarantee that a Skill or Connector will execute.
- Moving Memory into Conversation history or the capability center.
- Moving administrator system-tool governance into the ordinary-user capability center.
- Granting ordinary users MCP configuration write access or relaxing resource ownership, visibility, approval, and RBAC rules.
- Introducing a new canonical Connector resource type, credential export, secret migration, or a Connector marketplace.
- Replacing the current Agent/Skill/Workflow canonical resource model or changing its API semantics beyond the explicit catalog-consistency and migration needs above.
- Changing unrelated landing, authentication, visual-system, or workflow-runtime behavior.
- Automatically mutating an operator's local runtime database as part of this specification; synchronization is an explicit deployment or maintenance action with observable reporting.
- Publishing this local specification or follow-up work to a remote issue tracker.

## Further Notes

- Repository source currently defines a complete 72-resource bundled manifest: 15 Agents, 56 Skills, and 1 Workflow. The observed local runtime database contains an older partial set, including only 2 Agent resources; the required upgrade path is therefore a real acceptance case, not a hypothetical migration.
- The navigation and capability-center decisions are recorded in ADR 0001 and the domain glossary. This specification operationalizes those decisions together with the resource-catalog correction required for Agent Pill integrity.
- The resource count is a manifest-derived acceptance value. If the manifest changes in a future release, tests should derive expected totals and Agent Pill coverage from the manifest rather than hard-coding stale numbers, while retaining an explicit test that all configured Agent Pill slugs resolve.
